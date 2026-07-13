"""
Google OAuth login — verifies Google ID token and issues our own JWT.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.config import settings
from retailpool.database import get_db
from retailpool.models.user import User
from retailpool.schemas.auth import TokenResponse, UserOut
from retailpool.services.auth_service import create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


class GoogleLoginRequest(BaseModel):
    credential: str  # Google ID token from the frontend button


@router.post("/google", response_model=TokenResponse, summary="Login via Google")
async def google_login(
    data: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # 1. Verify the token with Google
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": data.credential},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )
    info = resp.json()

    # 2. Check the token was issued for OUR app
    if info.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token audience mismatch",
        )

    email = info.get("email")
    if not email or info.get("email_verified") not in ("true", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email not verified",
        )

    google_id = info.get("sub")
    full_name = info.get("name") or email.split("@")[0]

    # 3. Find or create the user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            hashed_password=None,      # Google users have no password
            full_name=full_name,
            google_id=google_id,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info("New user via Google: %s", email)
    else:
        if user.google_id is None:
            user.google_id = google_id
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )
        logger.info("User logged in via Google: %s", email)

    await db.flush()

    # 4. Issue OUR JWT — same as normal login
    token = create_access_token(user_id=str(user.id), email=user.email)
    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )
