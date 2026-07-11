"""
ORM models for the Kaspi auto-repricing system.

RepricingRule  — per-product configuration (min_price, step, ON/OFF toggle).
RepricingLog   — audit trail of every price change made by the bot.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Float, Integer, Boolean, DateTime,
    ForeignKey, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RepricingRule(Base):
    """A single product tracked by the repricing bot."""

    __tablename__ = "repricing_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )

    # Owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=False, index=True
    )

    # Product identification
    product_name: Mapped[str] = mapped_column(
        String(512), nullable=False,
        comment="Human-readable product name"
    )
    kaspi_sku: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="Kaspi product SKU / masterSku for Seller API"
    )
    product_url: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Full Kaspi product page URL for scraping competitors"
    )
    my_merchant_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="Name of user's Kaspi store (to exclude from competitor list)"
    )

    # Pricing
    my_current_price: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Current price set on Kaspi"
    )
    min_price: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Floor price — bot will NEVER go below this"
    )
    base_price: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Original/desired price to return to when no competitors"
    )
    step_kzt: Mapped[int] = mapped_column(
        Integer, default=5,
        comment="Undercut step in KZT (max 5). Always exactly this much below competitor"
    )

    # Toggle — user manually enables/disables
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="Bot is OFF by default. User explicitly turns it ON."
    )

    # Monitoring state
    last_competitor_price: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Last observed lowest competitor price"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    logs: Mapped[list[RepricingLog]] = relationship(
        "RepricingLog", back_populates="rule", lazy="selectin",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        status = "ON" if self.is_active else "OFF"
        return f"<RepricingRule {self.product_name[:30]} [{status}] price={self.my_current_price}>"


class RepricingLog(Base):
    """Audit log entry for a single price change event."""

    __tablename__ = "repricing_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("repricing_rules.id"), nullable=False, index=True
    )

    old_price: Mapped[float] = mapped_column(Float, nullable=False)
    new_price: Mapped[float] = mapped_column(Float, nullable=False)
    competitor_price: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="The competitor price that triggered this change"
    )
    action: Mapped[str] = mapped_column(
        String(32), default="undercut",
        comment="undercut | floor_hit | raise_back | alert_only"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    rule: Mapped[RepricingRule] = relationship(
        "RepricingRule", back_populates="logs"
    )

    def __repr__(self) -> str:
        return f"<RepricingLog {self.old_price} -> {self.new_price} ({self.action})>"
