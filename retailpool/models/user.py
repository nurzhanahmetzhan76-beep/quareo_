"""
ORM model for platform users (authentication & authorization).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Platform user account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(256), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(512), nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(256), nullable=False
    )
    company_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    plan: Mapped[str] = mapped_column(
        String(32), default="free",
        comment="Subscription plan: free / start / business / unlimited"
    )
    scans_used: Mapped[int] = mapped_column(
        Integer, default=0
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<User {self.email} plan={self.plan}>"
