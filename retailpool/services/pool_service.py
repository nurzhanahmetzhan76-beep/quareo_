"""
Pool Service — business logic for co-buying pools.
Injected via FastAPI Depends().
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta, timezone


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime (for cross-DB compat)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_naive(dt: datetime) -> datetime:
    """Strip timezone info for safe comparison (SQLite compat)."""
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from retailpool.models.pool import Pool, PoolParticipant, PoolStatus
from retailpool.schemas.pool import (
    PoolCreate, PoolJoin, PoolOut, PoolStatusOut, ParticipantOut,
)

logger = logging.getLogger(__name__)


class PoolService:
    """Handles pool CRUD, participant management, and quorum checks."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_pool(self, data: PoolCreate) -> PoolOut:
        """Open a new co-buying pool."""
        pool = Pool(
            product_id=data.product_id,
            product_name=data.product_name,
            supplier_name=data.supplier_name,
            target_quantity=data.target_quantity,
            target_amount=data.target_amount,
            current_quantity=0,
            current_amount=0.0,
            status=PoolStatus.OPEN,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=data.expires_in_hours),
        )
        self._db.add(pool)
        await self._db.flush()
        await self._db.refresh(pool)
        logger.info("Pool created: %s for product %s", pool.id, data.product_id)
        return PoolOut.model_validate(pool)

    async def join_pool(self, pool_id: uuid.UUID, data: PoolJoin) -> PoolStatusOut:
        """Add a participant to a pool and recalculate quorum."""
        pool = await self._db.get(
            Pool, pool_id, options=[selectinload(Pool.participants)]
        )
        if pool is None:
            raise ValueError(f"Pool {pool_id} not found")
        if pool.status != PoolStatus.OPEN:
            raise ValueError(f"Pool {pool_id} is not open (status={pool.status.value})")
        if _ensure_naive(pool.expires_at) < _utcnow_naive():
            pool.status = PoolStatus.EXPIRED
            raise ValueError(f"Pool {pool_id} has expired")

        # Check duplicate participation
        for p in pool.participants:
            if p.user_id == data.user_id:
                raise ValueError(f"User {data.user_id} already joined pool {pool_id}")

        participant = PoolParticipant(
            pool_id=pool_id,
            user_id=data.user_id,
            quantity=data.quantity,
            amount=data.amount,
        )
        self._db.add(participant)

        pool.current_quantity += data.quantity
        pool.current_amount += data.amount

        # Auto-close if quorum reached
        if (pool.current_quantity >= pool.target_quantity
                and pool.current_amount >= pool.target_amount):
            pool.status = PoolStatus.CLOSED
            logger.info("Pool %s reached quorum — auto-closed.", pool_id)

        await self._db.flush()
        await self._db.refresh(pool)

        return self._build_status(pool)

    async def get_pool_status(self, pool_id: uuid.UUID) -> PoolStatusOut:
        """Get full pool status with quorum progress."""
        pool = await self._db.get(
            Pool, pool_id, options=[selectinload(Pool.participants)]
        )
        if pool is None:
            raise ValueError(f"Pool {pool_id} not found")

        # Check expiration
        if (pool.status == PoolStatus.OPEN
                and _ensure_naive(pool.expires_at) < _utcnow_naive()):
            pool.status = PoolStatus.EXPIRED
            await self._db.flush()

        return self._build_status(pool)

    @staticmethod
    def _build_status(pool: Pool) -> PoolStatusOut:
        qty_pct = (pool.current_quantity / pool.target_quantity * 100
                   if pool.target_quantity > 0 else 0.0)
        amt_pct = (pool.current_amount / pool.target_amount * 100
                   if pool.target_amount > 0 else 0.0)

        return PoolStatusOut(
            pool=PoolOut.model_validate(pool),
            participants=[
                ParticipantOut.model_validate(p) for p in pool.participants
            ],
            quantity_progress_percent=round(qty_pct, 2),
            amount_progress_percent=round(amt_pct, 2),
            is_quorum_reached=(
                pool.current_quantity >= pool.target_quantity
                and pool.current_amount >= pool.target_amount
            ),
        )
