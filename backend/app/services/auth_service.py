import logging
import time
from typing import Dict, Any, Optional, Tuple
from app.core.jwt import create_access_token, generate_opaque_refresh_token
from app.core.security import hash_token
from app.core.config import settings
from app.core.redis_client import redis_service

logger = logging.getLogger("rolesync.auth")


class RefreshTokenRevokedException(Exception):
    pass


class InvalidRefreshTokenException(Exception):
    pass


class TokenManager:
    """
    Manages opaque refresh tokens with immediate invalidation on rotation
    and automated reuse detection (token theft defense).
    Uses Redis 7.2 distributed storage with in-memory fallback.
    """
    def __init__(self, redis_client: Any = None):
        self.redis = redis_client
        # In-memory store fallback for test environments or standalone execution
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._user_tokens: Dict[str, set] = {}

    def _get_redis(self):
        if self.redis is not None:
            return self.redis
        try:
            self.redis = redis_service.get_sync_client()
        except Exception:
            pass
        return self.redis

    def issue_token_pair(self, user_id: str, email: str, tier: str, device_fingerprint: str) -> Dict[str, Any]:
        """Issues an RS256 access token and a high-entropy refresh token."""
        access_token = create_access_token({
            "sub": str(user_id),
            "email": email,
            "role": "authenticated_user",
            "tier": tier
        })
        refresh_token = generate_opaque_refresh_token()
        token_hash = hash_token(refresh_token)
        ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400

        self._save_token(token_hash, user_id, device_fingerprint, ttl)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    def rotate_refresh_token(
        self,
        raw_refresh_token: str,
        device_fingerprint: str,
        email: str,
        tier: str
    ) -> Dict[str, Any]:
        """
        Executes Refresh Token Rotation (RTR):
        1. Checks validity and fingerprint binding.
        2. Invalidates the token immediately upon consumption.
        3. Issues a fresh token pair.
        4. If an already-consumed token is presented (reuse anomaly), REVOKES ALL TOKENS for that user.
        """
        token_hash = hash_token(raw_refresh_token)
        record = self._get_token(token_hash)

        if not record:
            # Token does not exist or was already rotated and purged
            raise InvalidRefreshTokenException("Refresh token is invalid or expired.")

        if record.get("revoked", False):
            # REUSE ANOMALY DETECTED: A revoked token is being replayed!
            user_id = record["user_id"]
            self.revoke_all_user_sessions(user_id)
            raise RefreshTokenRevokedException("Token reuse detected. All active sessions have been revoked for security.")

        # Verify device fingerprint match
        if record["device_fingerprint"] != device_fingerprint:
            raise InvalidRefreshTokenException("Device fingerprint mismatch.")

        # Invalidate the current token immediately (mark as revoked)
        user_id = record["user_id"]
        self._mark_revoked(token_hash)

        # Issue new pair
        return self.issue_token_pair(user_id, email, tier, device_fingerprint)

    def revoke_all_user_sessions(self, user_id: str) -> None:
        """Revokes every refresh token linked to the user across Redis and memory."""
        r = self._get_redis()
        user_key = str(user_id)
        if r is not None:
            try:
                set_key = f"rolesync:user_tokens:{user_key}"
                token_hashes = r.smembers(set_key) or []
                for th in token_hashes:
                    r.hset(f"rolesync:token:{th}", "revoked", "true")
                r.delete(set_key)
            except Exception as e:
                logger.warning(f"Error revoking user sessions in Redis: {e}")

        tokens = self._user_tokens.get(user_key, set())
        for th in list(tokens):
            if th in self._memory_store:
                self._memory_store[th]["revoked"] = True
        self._user_tokens[user_key] = set()

    def _save_token(self, token_hash: str, user_id: str, device_fingerprint: str, ttl: int) -> None:
        user_key = str(user_id)
        expires_at = time.time() + ttl

        # Primary: Distributed Redis Store
        r = self._get_redis()
        if r is not None:
            try:
                token_key = f"rolesync:token:{token_hash}"
                r.hset(token_key, mapping={
                    "user_id": user_key,
                    "device_fingerprint": str(device_fingerprint),
                    "expires_at": str(expires_at),
                    "revoked": "false"
                })
                r.expire(token_key, ttl)

                set_key = f"rolesync:user_tokens:{user_key}"
                r.sadd(set_key, token_hash)
                r.expire(set_key, ttl)
            except Exception as e:
                logger.warning(f"Error saving refresh token to Redis: {e}")

        # Local fallback mirror
        if user_key not in self._user_tokens:
            self._user_tokens[user_key] = set()
        self._user_tokens[user_key].add(token_hash)
        self._memory_store[token_hash] = {
            "user_id": user_key,
            "device_fingerprint": device_fingerprint,
            "expires_at": expires_at,
            "revoked": False
        }

    def _get_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        # Primary: Distributed Redis Store
        r = self._get_redis()
        if r is not None:
            try:
                token_key = f"rolesync:token:{token_hash}"
                data = r.hgetall(token_key)
                if data and "user_id" in data:
                    expires_at = float(data.get("expires_at", 0))
                    if time.time() > expires_at:
                        r.delete(token_key)
                        return None
                    return {
                        "user_id": data.get("user_id"),
                        "device_fingerprint": data.get("device_fingerprint"),
                        "expires_at": expires_at,
                        "revoked": data.get("revoked", "false").lower() == "true"
                    }
            except Exception as e:
                logger.warning(f"Error retrieving refresh token from Redis: {e}")

        # Local fallback mirror
        record = self._memory_store.get(token_hash)
        if not record:
            return None
        if time.time() > record["expires_at"]:
            del self._memory_store[token_hash]
            return None
        return record

    def _mark_revoked(self, token_hash: str) -> None:
        r = self._get_redis()
        if r is not None:
            try:
                token_key = f"rolesync:token:{token_hash}"
                r.hset(token_key, "revoked", "true")
            except Exception as e:
                logger.warning(f"Error marking token revoked in Redis: {e}")

        if token_hash in self._memory_store:
            self._memory_store[token_hash]["revoked"] = True


auth_token_manager = TokenManager()


