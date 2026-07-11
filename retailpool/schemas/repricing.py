"""
Pydantic schemas for the repricing API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# ── Rule schemas ─────────────────────────────────────────────

class RepricingRuleCreate(BaseModel):
    """Input schema for creating a repricing rule."""
    product_name: str = Field(..., min_length=1, max_length=512)
    kaspi_sku: str = Field(..., min_length=1, max_length=128)
    product_url: str | None = Field(None, max_length=2048)
    my_merchant_name: str | None = Field(None, max_length=256)
    my_current_price: float = Field(..., gt=0)
    min_price: float = Field(..., gt=0)
    base_price: float | None = Field(None, gt=0)
    step_kzt: int = Field(default=5, ge=1, le=5, description="Undercut step (max 5 KZT)")
    is_active: bool = Field(default=False, description="Bot OFF by default")


class RepricingRuleUpdate(BaseModel):
    """Partial update schema for a repricing rule."""
    product_name: str | None = Field(None, min_length=1, max_length=512)
    product_url: str | None = None
    my_merchant_name: str | None = None
    my_current_price: float | None = Field(None, gt=0)
    min_price: float | None = Field(None, gt=0)
    base_price: float | None = Field(None, gt=0)
    step_kzt: int | None = Field(None, ge=1, le=5)
    is_active: bool | None = None


class RepricingRuleOut(BaseModel):
    """Output schema for a repricing rule."""
    id: uuid.UUID
    user_id: uuid.UUID
    product_name: str
    kaspi_sku: str
    product_url: str | None
    my_merchant_name: str | None
    my_current_price: float
    min_price: float
    base_price: float | None
    step_kzt: int
    is_active: bool
    last_competitor_price: float | None
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Toggle schema ────────────────────────────────────────────

class RepricingToggle(BaseModel):
    """Toggle ON/OFF for a specific rule."""
    is_active: bool


# ── Log schemas ──────────────────────────────────────────────

class RepricingLogOut(BaseModel):
    """Output schema for a repricing log entry."""
    id: uuid.UUID
    rule_id: uuid.UUID
    old_price: float
    new_price: float
    competitor_price: float
    action: str
    created_at: datetime

    model_config = {"from_attributes": True}
