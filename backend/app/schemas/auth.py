from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class GoogleAuthRequest(BaseModel):
    id_token: str
    device_fingerprint: str


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Candidate account password")
    full_name: str = Field(..., min_length=2, description="Candidate full name")
    device_fingerprint: Optional[str] = "browser_client"


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_fingerprint: Optional[str] = "browser_client"


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
