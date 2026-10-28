from typing import Optional
from pydantic import BaseModel, EmailStr


class GoogleAuthRequest(BaseModel):
    id_token: str
    device_fingerprint: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str
    device_fingerprint: str
    email: Optional[EmailStr] = None
    tier: Optional[str] = "FREE"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    plan_tier: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Optional[UserResponse] = None

