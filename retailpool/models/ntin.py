"""
NTIN (National Trade Item Number) models for Kaspi marketplace compliance.

Each Kaspi seller must register products in the National Catalog (НКТ)
to obtain NTIN codes — required for ЭСФ and receipts since 2026.

Architecture:
  - Each user stores THEIR OWN API keys (Kaspi Seller + НКТ)
  - Keys are per-user, encrypted at rest
  - No single hardcoded credential
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NtinStatus(str, PyEnum):
    """NTIN processing status — mirrors НКТ statuses."""
    DRAFT = "draft"                # Черновик — ещё не заполнен
    AI_FILLED = "ai_filled"        # ИИ заполнил атрибуты
    READY = "ready"                # Готов к отправке
    SUBMITTED = "submitted"        # На модерации в НКТ
    REVISION = "revision"          # На доработку (НКТ вернул)
    APPROVED = "approved"          # NTIN привязан ✓
    REJECTED = "rejected"          # Отклонено
    REVOKED = "revoked"            # Отозвано


class NtinProduct(Base):
    """A product card prepared for NTIN registration in НКТ."""

    __tablename__ = "ntin_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True,
        comment="Owner — each user manages their own products"
    )

    # ── Product identification ───────────────────────────────────
    barcode: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
        comment="EAN-13 / UPC barcode if available"
    )
    kaspi_sku: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Kaspi product SKU (from seller cabinet)"
    )
    ntin_code: Mapped[str | None] = mapped_column(
        String(13), nullable=True, index=True,
        comment="13-digit NTIN code (prefix 02), assigned by НКТ"
    )

    # ── Product details (RU) ─────────────────────────────────────
    title_ru: Mapped[str] = mapped_column(
        String(512), comment="Product name in Russian"
    )
    description_ru: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Description in Russian"
    )

    # ── Product details (KZ) — required by НКТ ───────────────────
    title_kz: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Product name in Kazakh (auto-translated)"
    )
    description_kz: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Description in Kazakh (auto-translated)"
    )

    # ── Classification ───────────────────────────────────────────
    tn_ved_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="ТН ВЭД ЕАЭС code (10-digit), e.g. 0102.21.10.00"
    )
    tn_ved_name: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Human-readable ТН ВЭД description"
    )
    okpd2_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="ОКПД2 / ОКТРУ code"
    )
    oktru_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="ОКТРУ category code for НКТ, e.g. 1106-0001-0001-100011943"
    )
    nkt_request_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="ID of the request (заявка) in НКТ API — used for status tracking"
    )

    # ── Product attributes ───────────────────────────────────────
    country_of_origin: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="Китай"
    )
    brand: Mapped[str | None] = mapped_column(String(256), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="шт",
        comment="Unit: шт, кг, л, м, etc."
    )
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Status ───────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), default=NtinStatus.DRAFT, index=True
    )
    revision_comment: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="НКТ moderator's comment when status = revision/rejected"
    )

    # ── Price (for reference) ────────────────────────────────────
    price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the card was submitted to НКТ"
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When NTIN was assigned"
    )

    # ── Relationships ────────────────────────────────────────────
    submissions: Mapped[list[NtinSubmission]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<NtinProduct {self.title_ru[:40]} status={self.status}>"


class NtinSubmission(Base):
    """History of submissions to НКТ for a given product."""

    __tablename__ = "ntin_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("ntin_products.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20))
    nkt_response: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Raw response from НКТ API"
    )
    comment: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Moderator comment or error"
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    product: Mapped[NtinProduct] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"<NtinSubmission product={self.product_id} status={self.status}>"


class UserSellerSettings(Base):
    """Per-user API keys and seller settings.

    SECURITY: Each user stores THEIR OWN keys.
    Keys are never shared between users.
    The platform owner does NOT have a hardcoded master key.
    """

    __tablename__ = "user_seller_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, index=True,
    )

    # ── Kaspi Seller API ─────────────────────────────────────────
    kaspi_api_key: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="User's personal Kaspi Seller API key (encrypted)"
    )
    kaspi_merchant_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Kaspi merchant ID from seller cabinet"
    )
    kaspi_shop_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="Store name on Kaspi"
    )

    # ── НКТ (National Catalog) API ───────────────────────────────
    nkt_api_key: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="User's НКТ API key from nationalcatalog.kz"
    )

    # ── Timestamps ───────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<UserSellerSettings user={self.user_id}>"
