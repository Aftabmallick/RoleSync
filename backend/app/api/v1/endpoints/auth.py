import uuid
from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import GoogleAuthRequest, TokenRefreshRequest, TokenResponse, UserResponse
from app.services.auth_service import (
    auth_token_manager,
    InvalidRefreshTokenException,
    RefreshTokenRevokedException,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google", response_model=TokenResponse)
async def authenticate_google(payload: GoogleAuthRequest):
    """
    Exchanges Google ID token for short-lived RS256 JWT access token and rotating refresh token.
    In local dev / testing, accepts mock valid tokens.
    """
    if not payload.id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token is required."
        )

    # In production: verify with google.oauth2.id_token.verify_oauth2_token
    # Mock / extract identity claims
    mock_user_id = str(uuid.uuid4())
    mock_email = "candidate@example.com"
    mock_name = "Candidate Dev"
    mock_tier = "FREE"

    tokens = auth_token_manager.issue_token_pair(
        user_id=mock_user_id,
        email=mock_email,
        tier=mock_tier,
        device_fingerprint=payload.device_fingerprint
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
        user=UserResponse(
            id=mock_user_id,
            email=mock_email,
            full_name=mock_name,
            plan_tier=mock_tier,
            is_active=True
        )
    )


@router.post("/refresh", response_model=TokenResponse)
async def rotate_refresh_token(payload: TokenRefreshRequest):
    """
    Rotates refresh token and issues a new RS256 access token.
    Immediately invalidates old refresh token.
    Detects reuse anomalies and revokes all user sessions if a compromised token is replayed.
    """
    try:
        new_tokens = auth_token_manager.rotate_refresh_token(
            raw_refresh_token=payload.refresh_token,
            device_fingerprint=payload.device_fingerprint,
            email=payload.email or "candidate@example.com",
            tier=payload.tier or "FREE"
        )
        return TokenResponse(**new_tokens)
    except RefreshTokenRevokedException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except InvalidRefreshTokenException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

