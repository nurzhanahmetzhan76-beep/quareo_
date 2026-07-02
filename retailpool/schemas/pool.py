"""
Pydantic schemas for co-buying pools.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PoolCreate(BaseModel):
    """Schema for creating a new co-buying pool."""

    product_id: uuid.UUID = Field(..., description="ID of the product from the scanner")
    product_name: str = Field(..., description="Name of the product")
    supplier_name: str = Field(..., description="Name of the supplier or seller")
    target_quantity: int = Field(
        ..., gt=0, description="Minimum total units for wholesale"
    )
    target_amount: float = Field(
        ..., gt=0, description="Minimum total amount (KZT) for wholesale pricing"
    )
    expires_in_hours: int = Field(
        default=72, gt=0, le=720,
        description="Pool lifetime in hours before expiration",
    )


class PoolJoin(BaseModel):
    """Schema for joining an existing pool."""

    user_id: str = Field(
        ..., min_length=1, max_length=128,
        description="External user identifier (Telegram ID, phone, etc.)",
    )
    quantity: int = Field(..., gt=0, description="Units this participant wants to buy")
    amount: float = Field(
        ..., gt=0, description="Individual contribution amount (KZT)"
    )


class ParticipantOut(BaseModel):
    """Participant info returned in pool status."""

    id: uuid.UUID
    user_id: str
    quantity: int
    amount: float
    joined_at: datetime

    model_config = {"from_attributes": True}


class PoolOut(BaseModel):
    """Schema for a pool response (without participants list)."""

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    supplier_name: str
    target_quantity: int
    target_amount: float
    current_quantity: int
    current_amount: float
    status: str
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class PoolStatusOut(BaseModel):
    """Full pool status including quorum calculation and participants."""

    pool: PoolOut
    participants: list[ParticipantOut]

    # Quorum metrics
    quantity_progress_percent: float = Field(
        ..., ge=0.0,
        description="Percentage of target quantity reached",
    )
    amount_progress_percent: float = Field(
        ..., ge=0.0,
        description="Percentage of target amount reached",
    )
    is_quorum_reached: bool = Field(
        ..., description="True when BOTH quantity and amount targets are met",
    )
