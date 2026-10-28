import time
from typing import Dict, Any, Optional, Tuple
from app.core.jwt import create_access_token, generate_opaque_refresh_token
from app.core.security import hash_token
from app.core.config import settings


class RefreshTokenRevokedException(Exception):
    pass


class InvalidRefreshTokenException(Exception):
    pass


class TokenManager:
    """
    Manages opaque refresh tokens with immediate invalidation on rotation
    and automated reuse detection (token theft defense).
    """
    def __init__(self, redis_client: Any = None):
        self.redis = redis_client
        # In-memory store fallback for test environments or standalone execution
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._user_tokens: Dict[str, set] = {}

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
        """Revokes every refresh token linked to the user."""
        tokens = self._user_tokens.get(str(user_id), set())
        for th in list(tokens):
            if th in self._memory_store:
                self._memory_store[th]["revoked"] = True
        self._user_tokens[str(user_id)] = set()

    def _save_token(self, token_hash: str, user_id: str, device_fingerprint: str, ttl: int) -> None:
        user_key = str(user_id)
        if user_key not in self._user_tokens:
            self._user_tokens[user_key] = set()
        self._user_tokens[user_key].add(token_hash)

        self._memory_store[token_hash] = {
            "user_id": user_key,
            "device_fingerprint": device_fingerprint,
            "expires_at": time.time() + ttl,
            "revoked": False
        }

    def _get_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        record = self._memory_store.get(token_hash)
        if not record:
            return None
        if time.time() > record["expires_at"]:
            del self._memory_store[token_hash]
            return None
        return record

    def _mark_revoked(self, token_hash: str) -> None:
        if token_hash in self._memory_store:
            self._memory_store[token_hash]["revoked"] = True


auth_token_manager = TokenManager()

