"""
Pydantic schemas for scraped product cards and niche analysis results.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProductCard(BaseModel):
    """Validated representation of a scraped Kaspi product card."""

    kaspi_id: str = Field(..., min_length=1, description="Kaspi internal product ID")
    title: str = Field(..., min_length=1, max_length=512)
    category_slug: str
    url: str
    price_min: float | None = None
    price_max: float | None = None

    # Visual audit fields
    photo_count: int = Field(default=0, ge=0)
    has_infographics: bool = False
    description_length: int = Field(default=0, ge=0)
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    review_count: int = Field(default=0, ge=0)

    # Seller
    seller_name: str | None = None
    seller_count: int = Field(default=0, ge=0)

    model_config = {"from_attributes": True}


class NicheScoreOut(BaseModel):
    """Output schema for niche vulnerability analysis."""

    id: uuid.UUID
    product_id: uuid.UUID
    category_slug: str

    demand_score: float
    seller_count_in_category: int
    monopolization_index: float

    visual_score: float
    is_vulnerable: bool

    analyzed_at: datetime

    model_config = {"from_attributes": True}


class CategoryScanResult(BaseModel):
    """Aggregated result of scanning a single Kaspi category."""

    category_slug: str
    category_name: str
    products_scraped: int
    vulnerable_products: int
    vulnerability_ratio: float = Field(
        ..., ge=0.0, le=1.0,
        description="Fraction of top products that are 'weak'"
    )
    is_niche_vulnerable: bool
    monopolization_index_avg: float
    top_opportunities: list[ProductCard] = []
