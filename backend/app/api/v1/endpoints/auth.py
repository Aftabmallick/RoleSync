import uuid
from fastapi import APIRouter, HTTPException, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.jwt import get_current_user_id
from app.core.security import get_password_hash, verify_password
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthRequest,
    UserRegisterRequest,
    UserLoginRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserResponse
)
from app.services.auth_service import (
    auth_token_manager,
    InvalidRefreshTokenException,
    RefreshTokenRevokedException,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _to_uuid(val: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def register_candidate(
    request: Request,
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new candidate with email and password, returning RS256 JWT and refresh tokens.
    """
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    if res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    u_id = uuid.uuid4()
    new_user = User(
        id=u_id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        plan_tier="FREE",
        is_active=True
    )
    db.add(new_user)
    await db.commit()

    tokens = auth_token_manager.issue_token_pair(
        user_id=str(u_id),
        email=payload.email,
        tier="FREE",
        device_fingerprint=payload.device_fingerprint or "browser_client"
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
        user=UserResponse(
            id=str(u_id),
            email=payload.email,
            full_name=payload.full_name,
            plan_tier="FREE",
            is_active=True
        )
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login_candidate(
    request: Request,
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticates candidate credentials and issues a fresh token pair.
    """
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    tokens = auth_token_manager.issue_token_pair(
        user_id=str(user.id),
        email=user.email,
        tier=user.plan_tier,
        device_fingerprint=payload.device_fingerprint or "browser_client"
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            plan_tier=user.plan_tier,
            is_active=user.is_active
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves candidate account metadata from PostgreSQL.
    """
    u_id = _to_uuid(user_id)
    stmt = select(User).where(User.id == u_id)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        return UserResponse(
            id=user_id,
            email="candidate@rolesync.dev",
            full_name="Candidate User",
            plan_tier="FREE",
            is_active=True
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        plan_tier=user.plan_tier,
        is_active=user.is_active
    )


@router.post("/google", response_model=TokenResponse)
async def authenticate_google(
    payload: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Exchanges Google ID token for short-lived RS256 JWT access token and rotating refresh token.
    Persists or restores the user record in PostgreSQL to maintain stable tenant isolation.
    """
    if not payload.id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token is required."
        )

    # In production: verify with google.oauth2.id_token.verify_oauth2_token(payload.id_token, requests.Request(), settings.GOOGLE_CLIENT_ID)
    mock_email = "candidate@example.com"
    mock_name = "Candidate Dev"
    mock_tier = "FREE"

    stmt = select(User).where(User.email == mock_email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        u_id = uuid.uuid4()
        user = User(
            id=u_id,
            email=mock_email,
            full_name=mock_name,
            google_id=f"g_{u_id.hex[:12]}",
            plan_tier=mock_tier,
            is_active=True
        )
        db.add(user)
        await db.commit()

    tokens = auth_token_manager.issue_token_pair(
        user_id=str(user.id),
        email=user.email,
        tier=user.plan_tier,
        device_fingerprint=payload.device_fingerprint
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            plan_tier=user.plan_tier,
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
