"""
ORM models for co-buying pools and their participants.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PoolStatus(str, enum.Enum):
    """Lifecycle states for a co-buying pool."""

    OPEN = "open"
    CLOSED = "closed"          # Quorum reached, awaiting payment
    COMPLETED = "completed"    # Payment confirmed, order placed
    EXPIRED = "expired"        # Deadline passed without quorum
    CANCELLED = "cancelled"


class PoolType(str, enum.Enum):
    """How the pool sources its product."""

    LINK = "link"      # Initiator provides a direct marketplace URL
    TENDER = "tender"  # Syndicate posts an RFQ for suppliers to bid on


class Pool(Base):
    """A co-buying pool opened for a specific product."""

    __tablename__ = "pools"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    product_name: Mapped[str] = mapped_column(String(255), default="")
    supplier_name: Mapped[str] = mapped_column(String(255), default="")

    # ── New: sourcing fields ──────────────────────────────────────
    pool_type: Mapped[str] = mapped_column(
        String(20), default=PoolType.LINK.value,
        comment="link or tender"
    )
    source_url: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Direct URL to the product on 1688 / Alibaba / Kaspi etc."
    )
    image_url: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Product image URL (auto-fetched or manual)"
    )
    category: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Product category for filtering"
    )
    unit_price: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Unit price in KZT"
    )
    weight_per_unit_kg: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Approximate weight per unit in kg (for logistics calc)"
    )
    created_by: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Email or user ID of the pool creator"
    )

    # Targets for quorum
    target_quantity: Mapped[int] = mapped_column(
        Integer, comment="Minimum total units required for wholesale order"
    )
    target_amount: Mapped[float] = mapped_column(
        Float, comment="Minimum total amount (KZT) to qualify for wholesale pricing"
    )

    # Current aggregates (updated on each join)
    current_quantity: Mapped[int] = mapped_column(Integer, default=0)
    current_amount: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[PoolStatus] = mapped_column(
        SAEnum(PoolStatus, name="pool_status"),
        default=PoolStatus.OPEN,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="Deadline for reaching quorum",
    )

    participants: Mapped[list[PoolParticipant]] = relationship(
        back_populates="pool", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Pool {self.id} status={self.status.value}>"


class PoolParticipant(Base):
    """A user who has joined a co-buying pool."""

    __tablename__ = "pool_participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    pool_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("pools.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(128), index=True, comment="External user identifier"
    )
    quantity: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float, comment="Individual contribution (KZT)")

    # ── New: delivery info ────────────────────────────────────────
    delivery_city: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="Алматы",
        comment="City for last-mile delivery"
    )
    delivery_method: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default="pickup",
        comment="pickup / sdek / kazpost"
    )

    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    pool: Mapped[Pool] = relationship(back_populates="participants")

    def __repr__(self) -> str:
        return f"<PoolParticipant user={self.user_id} pool={self.pool_id}>"
