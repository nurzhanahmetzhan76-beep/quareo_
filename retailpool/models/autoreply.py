"""
ORM models for AI auto-reply feature:
- AutoReplySettings: per-user tone/language/instructions preferences
- AutoReplyHistory: Q&A log for learning seller's style
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutoReplySettings(Base):
    """Per-user auto-reply preferences (persisted in DB)."""

    __tablename__ = "autoreply_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, index=True, nullable=False,
        comment="Owner of these settings"
    )
    tone: Mapped[str] = mapped_column(
        String(32), default="friendly",
        comment="friendly / formal / casual"
    )
    auto_send: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="Auto-send replies without confirmation"
    )
    language: Mapped[str] = mapped_column(
        String(8), default="ru",
        comment="ru / kz"
    )
    store_description: Mapped[str] = mapped_column(
        Text, default="",
        comment="Brief store/product description for AI context"
    )
    custom_instructions: Mapped[str] = mapped_column(
        Text, default="",
        comment="Extra instructions for AI generation"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<AutoReplySettings user={self.user_id} tone={self.tone}>"


class AutoReplyHistory(Base):
    """Stored Q&A pairs for learning the seller's reply style."""

    __tablename__ = "autoreply_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    question: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Customer's original question"
    )
    answer: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="AI-generated or manually-provided answer"
    )
    product_name: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Product the question was about"
    )
    question_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Kaspi-side question ID for dedup"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    def __repr__(self) -> str:
        return f"<AutoReplyHistory user={self.user_id} q={self.question[:30]}>"
