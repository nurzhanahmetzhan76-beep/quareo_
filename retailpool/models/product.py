"""
ORM models for scraped products and niche analysis results.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailpool.models.base import Base, UUIDType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    """A product card scraped from Kaspi marketplace."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    kaspi_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, comment="Kaspi internal product ID"
    )
    title: Mapped[str] = mapped_column(String(512))
    category_slug: Mapped[str] = mapped_column(
        String(128), index=True, comment="Category slug, e.g. air-humidifiers"
    )
    url: Mapped[str] = mapped_column(Text)
    price_min: Mapped[float] = mapped_column(Float, nullable=True)
    price_max: Mapped[float] = mapped_column(Float, nullable=True)

    # Card quality metrics (visual audit)
    photo_count: Mapped[int] = mapped_column(Integer, default=0)
    has_infographics: Mapped[bool] = mapped_column(Boolean, default=False)
    description_length: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    # Seller info
    seller_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    seller_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="Number of sellers offering this product"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationship to niche analysis
    niche_analyses: Mapped[list[NicheAnalysis]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product {self.kaspi_id} — {self.title[:40]}>"


class NicheAnalysis(Base):
    """Stores per-category niche analysis results (monopolization & vulnerability)."""

    __tablename__ = "niche_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("products.id", ondelete="CASCADE")
    )
    category_slug: Mapped[str] = mapped_column(String(128), index=True)

    # Monopolization index = demand_score / seller_count
    demand_score: Mapped[float] = mapped_column(
        Float, default=0.0, comment="Proxy for demand (e.g. review volume, search rank)"
    )
    seller_count_in_category: Mapped[int] = mapped_column(Integer, default=0)
    monopolization_index: Mapped[float] = mapped_column(Float, default=0.0)

    # Visual weakness score (0.0 = strong, 1.0 = very weak)
    visual_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_vulnerable: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True,
        comment="True if >50% of top-10 cards in the category are weak",
    )

    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    product: Mapped[Product] = relationship(back_populates="niche_analyses")

    def __repr__(self) -> str:
        return f"<NicheAnalysis category={self.category_slug} vulnerable={self.is_vulnerable}>"
