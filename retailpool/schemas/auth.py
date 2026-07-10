"""
Pydantic schemas for user authentication and registration.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr


class UserRegister(BaseModel):
    """Schema for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., min_length=6, max_length=128,
        description="Plain-text password (will be hashed)"
    )
    full_name: str = Field(
        ..., min_length=1, max_length=256,
        description="Full name of the user"
    )
    company_name: str | None = Field(
        default=None, max_length=256,
        description="Company or store name"
    )
    phone: str | None = Field(
        default=None, max_length=32,
        description="Phone number"
    )


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT token response returned after login/register."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserOut(BaseModel):
    """Public user profile (no password)."""

    id: uuid.UUID | str | None = None
    email: str | None = None
    full_name: str | None = None
    company_name: str | None = None
    phone: str | None = None
    plan: str | None = "free"
    is_active: bool | None = True
    created_at: datetime | str | None = None

    model_config = {"from_attributes": True}


# Fix forward reference — TokenResponse uses UserOut
TokenResponse.model_rebuild()
