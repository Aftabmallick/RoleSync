import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt
from app.core.config import settings

# Generate or load RSA keys for RS256
_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_public_key = _private_key.public_key()

PRIVATE_PEM = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode("utf-8")

PUBLIC_PEM = _public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates a short-lived, RS256-signed stateless JWT Access Token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "https://api.rolesync.io",
        "aud": "https://app.rolesync.io"
    })
    
    return jwt.encode(to_encode, PRIVATE_PEM, algorithm="RS256")


def verify_access_token(token: str) -> Dict[str, Any]:
    """Decodes and verifies RS256 signature and token expiry."""
    try:
        payload = jwt.decode(
            token,
            PUBLIC_PEM,
            algorithms=["RS256"],
            audience="https://app.rolesync.io",
            issuer="https://api.rolesync.io"
        )
        return payload
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid or expired access token: {str(e)}")


def generate_opaque_refresh_token() -> str:
    """Generates a high-entropy opaque UUIDv4 refresh token."""
    return f"rst_{uuid.uuid4().hex}{uuid.uuid4().hex}"


from fastapi import Header


def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Dependency to resolve the authenticated user ID.
    If valid Bearer token is provided, extracts 'sub'. Otherwise defaults to mock tenant ID.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = verify_access_token(token)
            return payload.get("sub", "tenant_user_001")
        except Exception:
            return "tenant_user_001"
    return "tenant_user_001"


