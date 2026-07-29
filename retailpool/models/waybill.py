"""Persistence models for Smart Print waybill processing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProcessedWaybill(Base):
    """A waybill that has already been included in a generated PDF."""

    __tablename__ = "processed_waybills"
    __table_args__ = (
        UniqueConstraint("user_id", "waybill_id", name="uq_processed_waybill_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    waybill_id: Mapped[str] = mapped_column(String(256), nullable=False)
    store_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )


class WaybillUploadHistory(Base):
    """A concise audit entry for every uploaded waybill archive."""

    __tablename__ = "waybill_upload_history"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    already_processed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
