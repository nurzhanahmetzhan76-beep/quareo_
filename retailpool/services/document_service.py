"""
Document Service — abstract base + Kaspi implementation.
Prepares JSON invoice payloads for the Telegram Bot worker.
Includes Success Fee (3-5%) calculation.
"""

from __future__ import annotations

import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from retailpool.config import settings
from retailpool.schemas.document import (
    InvoicePayload, InvoiceItem, ParticipantInvoiceInfo,
    SuccessFeeConfig, KaspiPayDetails,
)
from retailpool.schemas.pool import PoolStatusOut

logger = logging.getLogger(__name__)


class AbstractDocumentService(ABC):
    """Interface for invoice/document generation services."""

    @abstractmethod
    def prepare_invoice_payload(
        self,
        pool_status: PoolStatusOut,
        product_name: str,
        unit_price: float,
    ) -> InvoicePayload:
        """Build a complete invoice payload from a closed pool."""
        ...

    @abstractmethod
    def calculate_success_fee(
        self, total_amount: float, fee_percent: float | None = None
    ) -> float:
        """Calculate the platform's commission."""
        ...


class KaspiDocumentService(AbstractDocumentService):
    """
    Concrete implementation for Kaspi-based co-buying invoices.
    Generates JSON payload consumed by the Telegram Bot worker
    for PDF/ZIP generation and delivery via Kaspi Pay.
    """

    def __init__(self, fee_percent: float | None = None) -> None:
        self._fee_percent = fee_percent or settings.SUCCESS_FEE_PERCENT

    def calculate_success_fee(
        self, total_amount: float, fee_percent: float | None = None
    ) -> float:
        """
        Calculate Success Fee: commission for organizing the co-buy.
        Fee is 3-5% of the deal subtotal.
        """
        pct = fee_percent or self._fee_percent
        fee = Decimal(str(total_amount)) * Decimal(str(pct)) / Decimal("100")
        return float(fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def prepare_invoice_payload(
        self,
        pool_status: PoolStatusOut,
        product_name: str,
        unit_price: float,
    ) -> InvoicePayload:
        """
        Build JSON payload for the Telegram Bot worker.

        The bot will:
          1. Receive this payload via FastAPI endpoint
          2. Generate PDF invoices per participant
          3. Send them via Telegram with Kaspi Pay payment links
        """
        pool = pool_status.pool

        # Build line items (one per participant contribution)
        items: list[InvoiceItem] = []
        participants_info: list[ParticipantInvoiceInfo] = []

        for p in pool_status.participants:
            items.append(InvoiceItem(
                product_name=product_name,
                quantity=p.quantity,
                unit_price=unit_price,
                total=round(p.quantity * unit_price, 2),
            ))
            participants_info.append(ParticipantInvoiceInfo(
                user_id=p.user_id,
                quantity=p.quantity,
                amount=p.amount,
            ))

        subtotal = round(sum(item.total for item in items), 2)
        fee_amount = self.calculate_success_fee(subtotal)
        grand_total = round(subtotal + fee_amount, 2)

        # Generate invoice number
        inv_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        payload = InvoicePayload(
            invoice_number=inv_number,
            pool_id=pool.id,
            generated_at=datetime.now(timezone.utc),
            items=items,
            participants=participants_info,
            subtotal=subtotal,
            success_fee=SuccessFeeConfig(
                min_percent=3.0,
                max_percent=5.0,
                applied_percent=self._fee_percent,
            ),
            success_fee_amount=fee_amount,
            grand_total=grand_total,
            payment_details=KaspiPayDetails(),
        )

        logger.info(
            "Invoice %s generated: subtotal=%.2f, fee=%.2f, total=%.2f",
            inv_number, subtotal, fee_amount, grand_total,
        )
        return payload
