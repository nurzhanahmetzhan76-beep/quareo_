"""
Pool Router — REST API for co-buying pool management.

Endpoints:
  POST /pools/create       — open a new pool
  POST /pools/{id}/join    — join an existing pool
  GET  /pools/{id}/status  — get pool status + quorum progress
  GET  /pools/open         — list all open pools
  GET  /pools/list         — list all pools (paginated)
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import get_db
from retailpool.models.pool import Pool, PoolStatus
from retailpool.schemas.pool import PoolCreate, PoolJoin, PoolOut, PoolStatusOut
from retailpool.services.pool_service import PoolService

router = APIRouter(prefix="/pools", tags=["Co-Buying Pools"])


def _get_pool_service(db: AsyncSession = Depends(get_db)) -> PoolService:
    """FastAPI Dependency Injection for PoolService."""
    return PoolService(db=db)


# ── List endpoints ───────────────────────────────────────────────────────

@router.get(
    "/open",
    response_model=list[PoolOut],
    summary="List all open pools (for bot marketplace)",
)
async def list_open_pools(
    db: AsyncSession = Depends(get_db),
) -> list[PoolOut]:
    """
    Return all pools with OPEN status, ordered by creation date (newest first).
    Used by the Telegram bot to display the pool marketplace.
    """
    stmt = (
        select(Pool)
        .where(Pool.status == PoolStatus.OPEN)
        .order_by(Pool.created_at.desc())
    )
    result = await db.execute(stmt)
    pools = result.scalars().all()
    return [PoolOut.model_validate(p) for p in pools]


@router.get(
    "/list",
    response_model=list[PoolOut],
    summary="List all pools (paginated)",
)
async def list_all_pools(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[PoolOut]:
    """
    Return all pools with optional status filter and pagination.
    """
    stmt = select(Pool).order_by(Pool.created_at.desc())

    if status_filter:
        try:
            status_enum = PoolStatus(status_filter)
            stmt = stmt.where(Pool.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status_filter}. "
                       f"Valid: {[s.value for s in PoolStatus]}",
            )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    pools = result.scalars().all()
    return [PoolOut.model_validate(p) for p in pools]


# ── CRUD endpoints ───────────────────────────────────────────────────────

@router.post(
    "/create",
    response_model=PoolOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new co-buying pool",
)
async def create_pool(
    data: PoolCreate,
    svc: PoolService = Depends(_get_pool_service),
) -> PoolOut:
    """
    Create a co-buying pool for a product found by the niche scanner.
    The pool stays OPEN until quorum is reached or expiration.
    """
    try:
        return await svc.create_pool(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/{pool_id}/join",
    response_model=PoolStatusOut,
    summary="Join an existing pool",
)
async def join_pool(
    pool_id: uuid.UUID,
    data: PoolJoin,
    svc: PoolService = Depends(_get_pool_service),
) -> PoolStatusOut:
    """
    Add a participant to the pool. Automatically closes the pool
    when both quantity and amount targets are met.
    """
    try:
        return await svc.join_pool(pool_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/{pool_id}/status",
    response_model=PoolStatusOut,
    summary="Get pool status and quorum progress",
)
async def get_pool_status(
    pool_id: uuid.UUID,
    svc: PoolService = Depends(_get_pool_service),
) -> PoolStatusOut:
    """
    Returns pool info, participant list, and quorum completion
    percentage (quantity & amount).
    """
    try:
        return await svc.get_pool_status(pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

