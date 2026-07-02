"""
Pydantic schemas for subscription API.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr


class SubscriptionCreate(BaseModel):
    """Input schema for creating a subscription request."""
    contact_name: str = Field(..., min_length=1, max_length=256)
    contact_email: str = Field(..., min_length=3, max_length=256)
    contact_phone: str | None = Field(None, max_length=64)
    plan_name: str = Field(..., min_length=1, max_length=128)
    plan_price: float = Field(..., gt=0)
    payment_method: str = Field(default="card", pattern="^(card|kaspi_transfer)$")


class SubscriptionOut(BaseModel):
    """Output schema for subscription."""
    id: uuid.UUID
    contact_name: str
    contact_email: str
    contact_phone: str | None
    plan_name: str
    plan_price: float
    payment_method: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
