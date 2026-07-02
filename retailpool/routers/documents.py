"""
Documents Router — REST API for invoice generation.

Endpoints:
  GET /pools/{pool_id}/invoice — get finalized invoice payload for a closed pool
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from retailpool.database import get_db
from retailpool.models.pool import Pool, PoolStatus
from retailpool.models.product import Product
from retailpool.schemas.document import InvoicePayload
from retailpool.schemas.pool import PoolOut, PoolStatusOut, ParticipantOut
from retailpool.services.document_service import KaspiDocumentService

router = APIRouter(tags=["Documents & Invoices"])


def _get_document_service() -> KaspiDocumentService:
    """FastAPI Dependency Injection for KaspiDocumentService."""
    return KaspiDocumentService()


@router.get(
    "/pools/{pool_id}/invoice",
    response_model=InvoicePayload,
    summary="Get finalized invoice JSON for a closed pool",
)
async def get_pool_invoice(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    doc_svc: KaspiDocumentService = Depends(_get_document_service),
) -> InvoicePayload:
    """
    Generate and return a complete invoice payload for a closed co-buying pool.

    This JSON is designed to be consumed by the Telegram Bot worker
    for PDF invoice generation and Kaspi Pay integration.

    Only pools with status CLOSED (quorum reached) can generate invoices.
    """
    # Load pool with participants
    pool = await db.get(
        Pool, pool_id, options=[selectinload(Pool.participants)]
    )
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool {pool_id} not found",
        )

    if pool.status != PoolStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pool is not closed (status={pool.status.value}). "
                   f"Invoice can only be generated for pools with quorum reached.",
        )

    # Load the associated product for name and price
    product = await db.get(Product, pool.product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {pool.product_id} not found for pool {pool_id}",
        )

    # Build PoolStatusOut from the ORM object
    qty_pct = (pool.current_quantity / pool.target_quantity * 100
               if pool.target_quantity > 0 else 0.0)
    amt_pct = (pool.current_amount / pool.target_amount * 100
               if pool.target_amount > 0 else 0.0)

    pool_status = PoolStatusOut(
        pool=PoolOut.model_validate(pool),
        participants=[
            ParticipantOut.model_validate(p) for p in pool.participants
        ],
        quantity_progress_percent=round(qty_pct, 2),
        amount_progress_percent=round(amt_pct, 2),
        is_quorum_reached=True,
    )

    # Use the product's min price as unit price (wholesale entry)
    unit_price = product.price_min or product.price_max or 0.0

    payload = doc_svc.prepare_invoice_payload(
        pool_status=pool_status,
        product_name=product.title,
        unit_price=unit_price,
    )

    return payload
