from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
import jwt
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    Token,
    TokenPayload,
)
from app.schemas.organization import OrganizationRead
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Provision Organization and Admin Account",
)
async def register_tenant(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Token:
    """
    Atomic multi-tenant onboarding transaction:
    1. Validates organization slug uniqueness.
    2. Provisions Organization.
    3. Provisions root User with ADMIN privileges.
    4. Records membership mapping.
    5. Issues access and refresh JWT pair.
    """
    # Check if slug exists
    slug_check = await db.execute(
        select(Organization).where(Organization.slug == payload.organization_slug.lower().strip())
    )
    if slug_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists",
        )

    # Create Organization
    org = Organization(
        name=payload.organization_name.strip(),
        slug=payload.organization_slug.lower().strip(),
        status="ACTIVE",
    )
    db.add(org)
    await db.flush()

    # Create Admin User
    user = User(
        organization_id=org.id,
        email=payload.email.lower().strip(),
        password_hash=get_password_hash(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        role="ADMIN",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create Membership
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="ADMIN",
    )
    db.add(membership)
    await db.flush()

    # Issue JWT tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/login", response_model=Token, summary="Authenticate User")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Token:
    """Verifies credentials using Argon2 and updates last login timestamp."""
    stmt = select(User).where(User.email == payload.email.lower().strip())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Record last login time
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    await db.flush()

    return Token(
        access_token=create_access_token(subject=user.id),
        refresh_token=create_refresh_token(subject=user.id),
        token_type="bearer",
    )


@router.post("/refresh", response_model=Token, summary="Rotate Access Token")
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Token:
    """Validates refresh token and issues a fresh access/refresh token pair."""
    try:
        decoded = jwt.decode(
            payload.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**decoded)
        if token_data.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: expected refresh token",
            )
        user_id = uuid.UUID(token_data.sub)
    except (jwt.PyJWTError, ValidationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or does not exist",
        )

    return Token(
        access_token=create_access_token(subject=user.id),
        refresh_token=create_refresh_token(subject=user.id),
        token_type="bearer",
    )


@router.get("/me", response_model=CurrentUserResponse, summary="Get Current Tenant & User Profile")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUserResponse:
    """Returns the authenticated user entity and current organization profile."""
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one()

    return CurrentUserResponse(
        user=UserRead.model_validate(current_user),
        organization=OrganizationRead.model_validate(org),
    )