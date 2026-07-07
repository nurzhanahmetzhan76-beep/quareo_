"""
Auth Router — user registration, login, and profile endpoints.

Endpoints:
  POST /auth/register  — create a new account
  POST /auth/login     — authenticate and receive JWT
  GET  /auth/me        — get current user profile (requires JWT)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from retailpool.database import get_db
from retailpool.models.user import User
from retailpool.schemas.auth import (
    UserRegister, UserLogin, TokenResponse, UserOut,
)
from pydantic import BaseModel

class TelegramLinkRequest(BaseModel):
    telegram_id: int

from retailpool.services.auth_service import (
    hash_password, verify_password, create_access_token, get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit("3/minute")
async def register(
    request: Request,  
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a new user and return a JWT access token."""
    # Check if email already exists
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        company_name=data.company_name,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(user_id=str(user.id), email=user.email)
    logger.info("User registered: %s", user.email)

    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT token",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email/password and receive a JWT."""
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(user_id=str(user.id), email=user.email)
    logger.info("User logged in: %s", user.email)

    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    """Return the profile of the currently authenticated user."""
    return UserOut.model_validate(current_user)


@router.post(
    "/telegram-link",
    summary="Link Telegram Chat ID to the current user",
)
async def link_telegram(
    data: TelegramLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Link user's Telegram ID for VIP notifications."""
    current_user.telegram_id = data.telegram_id
    await db.commit()
    return {"status": "ok", "telegram_id": data.telegram_id}
