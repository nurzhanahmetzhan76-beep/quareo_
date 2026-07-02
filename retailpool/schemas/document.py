"""
Pydantic schemas for invoice/document generation and Success Fee calculation.
These payloads are consumed by the Telegram Bot worker.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class InvoiceItem(BaseModel):
    """A single line item in an invoice."""

    product_name: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    total: float = Field(..., gt=0)


class ParticipantInvoiceInfo(BaseModel):
    """Participant data included in the invoice payload."""

    user_id: str
    quantity: int
    amount: float


class SuccessFeeConfig(BaseModel):
    """Configuration for the Success Fee (commission) calculation."""

    min_percent: float = Field(default=3.0, ge=0.0, le=100.0)
    max_percent: float = Field(default=5.0, ge=0.0, le=100.0)
    applied_percent: float = Field(
        ..., ge=0.0, le=100.0,
        description="Actual fee percentage applied to this deal",
    )


class KaspiPayDetails(BaseModel):
    """Payment details for Kaspi Pay integration."""

    recipient_name: str = "RetailPool AI"
    recipient_iin: str = ""
    kaspi_gold_number: str = ""
    payment_purpose: str = "Оплата совместной закупки"


class InvoicePayload(BaseModel):
    """
    Complete JSON payload for invoice generation.
    Sent to the Telegram Bot worker for PDF rendering and delivery.
    """

    invoice_number: str = Field(
        ..., description="Unique invoice identifier, e.g. INV-2026-00042"
    )
    pool_id: uuid.UUID
    generated_at: datetime

    # Line items
    items: list[InvoiceItem]
    participants: list[ParticipantInvoiceInfo]

    # Financial summary
    subtotal: float = Field(..., ge=0)
    success_fee: SuccessFeeConfig
    success_fee_amount: float = Field(
        ..., ge=0,
        description="Calculated fee: subtotal * applied_percent / 100",
    )
    grand_total: float = Field(
        ..., ge=0,
        description="subtotal + success_fee_amount",
    )

    # Payment
    payment_details: KaspiPayDetails = KaspiPayDetails()
