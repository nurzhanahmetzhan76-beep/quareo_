"""
Subscriptions Router — REST API for subscription management.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import get_db
from retailpool.models.subscription import Subscription
from retailpool.models.user import User
from retailpool.schemas.subscription import SubscriptionCreate, SubscriptionOut
from retailpool.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


@router.post(
    "",
    response_model=SubscriptionOut,
    status_code=201,
    summary="Create a subscription request",
)
async def create_subscription(
    data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    """Create a new subscription request and persist it to the database."""
    sub = Subscription(
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        plan_name=data.plan_name,
        plan_price=data.plan_price,
        payment_method=data.payment_method,
    )
    db.add(sub)
    await db.flush()
    await db.refresh(sub)

    logger.info(
        "Subscription created: %s | plan=%s | email=%s",
        sub.id, sub.plan_name, sub.contact_email,
    )

    return SubscriptionOut.model_validate(sub)


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionOut,
    summary="Get subscription status",
)
async def get_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    """Retrieve a subscription by ID."""
    sub = await db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return SubscriptionOut.model_validate(sub)


@router.get(
    "",
    response_model=list[SubscriptionOut],
    summary="List all subscriptions (admin)",
)
async def list_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubscriptionOut]:
    """List all subscription requests (admin only — checks email whitelist)."""
    if current_user.email != "karimbai.ali10@mail.ru":
        raise HTTPException(status_code=403, detail="Admin access required")
    stmt = select(Subscription).order_by(Subscription.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [SubscriptionOut.model_validate(r) for r in rows]
