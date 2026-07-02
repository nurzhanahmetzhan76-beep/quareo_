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

    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    pool: Mapped[Pool] = relationship(back_populates="participants")

    def __repr__(self) -> str:
        return f"<PoolParticipant user={self.user_id} pool={self.pool_id}>"
