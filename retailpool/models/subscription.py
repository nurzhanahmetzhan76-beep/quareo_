"""
ORM model for subscription requests (payment intents).
"""

from __future__ import annotations

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Subscription(Base):
    """A subscription request / payment intent."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    # Contact info
    contact_name: Mapped[str] = mapped_column(String(256))
    contact_email: Mapped[str] = mapped_column(String(256))
    contact_phone: Mapped[str] = mapped_column(String(64), nullable=True)

    # Plan info
    plan_name: Mapped[str] = mapped_column(String(128))
    plan_price: Mapped[float] = mapped_column(Float)

    # Payment
    payment_method: Mapped[str] = mapped_column(
        String(64), default="card",
        comment="card or kaspi_transfer"
    )
    status: Mapped[str] = mapped_column(
        String(32), default=SubscriptionStatus.PENDING.value
    )

    # Linked user (if logged in)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.id} plan={self.plan_name} status={self.status}>"
