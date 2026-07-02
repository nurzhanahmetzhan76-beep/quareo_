"""
ORM models for Telegram bot — user tracking and alert subscriptions.

These models extend the existing RetailPool database with
bot-specific tables for persistent alert storage.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    Float,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlertType(str, enum.Enum):
    """Types of alert subscriptions."""
    DUMPING = "dumping"
    STOCK_OUT = "stock_out"
    BOTH = "both"


class TelegramUser(Base):
    """
    Telegram user who has interacted with the bot.
    Tracks subscription tier and registration.
    """
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True,
        comment="Telegram user ID (from Telegram API)",
    )
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), default="")
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_tier: Mapped[str] = mapped_column(
        String(32), default="free",
        comment="Subscription tier: free, premium",
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
    )

    # Relationships
    alert_subscriptions: Mapped[list["AlertSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TelegramUser {self.id} @{self.username}>"


class AlertSubscription(Base):
    """
    A user's subscription to monitor a specific niche for changes.
    The alert_worker checks these periodically and sends notifications.
    """
    __tablename__ = "alert_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        index=True,
    )
    query: Mapped[str] = mapped_column(
        String(255),
        comment="Search query or category to monitor",
    )
    alert_type: Mapped[AlertType] = mapped_column(
        SAEnum(AlertType, name="alert_type_enum"),
        default=AlertType.BOTH,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Last known state for comparison
    last_snapshot: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Last scraped data snapshot for diff detection",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow,
    )

    # Relationships
    user: Mapped["TelegramUser"] = relationship(
        back_populates="alert_subscriptions",
    )

    def __repr__(self) -> str:
        return (
            f"<AlertSubscription {self.id} "
            f"user={self.user_id} query='{self.query}'>"
        )
