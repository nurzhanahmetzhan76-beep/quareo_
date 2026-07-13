"""
Kaspi-bot repricing API endpoints.

Full CRUD for repricing rules + manual toggle ON/OFF + logs history.
Auto-sync products from Kaspi Seller API so users don't need to enter SKUs manually.
"""

from __future__ import annotations

import logging
import uuid
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import get_db
from retailpool.models.user import User
from retailpool.models.repricing import RepricingRule, RepricingLog
from retailpool.models.ntin import UserSellerSettings
from retailpool.schemas.repricing import (
    RepricingRuleCreate,
    RepricingRuleUpdate,
    RepricingRuleOut,
    RepricingToggle,
    RepricingLogOut,
)
from retailpool.services.auth_service import get_current_user
from retailpool.services.kaspi_api import KaspiSellerClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repricing", tags=["Repricing Bot"])

MAX_STEP_KZT = 5  # Hard cap — NEVER exceed 5 tenge


# ── Helper ────────────────────────────────────────────────────

async def _get_rule_for_user(
    rule_id: uuid.UUID, user: User, db: AsyncSession
) -> RepricingRule:
    """Fetch a repricing rule and verify ownership."""
    rule = await db.get(RepricingRule, rule_id)
    if not rule or rule.user_id != user.id:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return rule


# ══════════════════════════════════════════════════════════════
# CRUD — Rules
# ══════════════════════════════════════════════════════════════

@router.post(
    "/rules",
    response_model=RepricingRuleOut,
    status_code=201,
    summary="Create a repricing rule for a product",
)
async def create_rule(
    data: RepricingRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepricingRuleOut:
    """Add a product to the repricing bot.

    Bot is OFF by default — user must explicitly toggle it ON.
    Step is capped at 5 KZT maximum.
    """
    # Enforce step cap
    step = min(data.step_kzt, MAX_STEP_KZT)

    # Validate min_price < current_price
    if data.min_price >= data.my_current_price:
        raise HTTPException(
            status_code=400,
            detail="Минимальная цена должна быть ниже текущей цены."
        )

    rule = RepricingRule(
        user_id=current_user.id,
        product_name=data.product_name,
        kaspi_sku=data.kaspi_sku,
        product_url=data.product_url,
        my_merchant_name=data.my_merchant_name,
        my_current_price=data.my_current_price,
        min_price=data.min_price,
        base_price=data.base_price or data.my_current_price,
        step_kzt=step,
        is_active=data.is_active,
    )

    db.add(rule)
    await db.flush()
    await db.refresh(rule)

    logger.info(
        "Repricing rule created: %s (SKU=%s) by user %s",
        rule.product_name, rule.kaspi_sku, current_user.email,
    )

    return RepricingRuleOut.model_validate(rule)


@router.get(
    "/rules",
    response_model=list[RepricingRuleOut],
    summary="List all repricing rules for the current user",
)
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RepricingRuleOut]:
    """Get all products being tracked by the repricing bot."""
    stmt = (
        select(RepricingRule)
        .where(RepricingRule.user_id == current_user.id)
        .order_by(RepricingRule.created_at.desc())
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [RepricingRuleOut.model_validate(r) for r in rules]


@router.get(
    "/rules/{rule_id}",
    response_model=RepricingRuleOut,
    summary="Get a specific repricing rule",
)
async def get_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepricingRuleOut:
    rule = await _get_rule_for_user(rule_id, current_user, db)
    return RepricingRuleOut.model_validate(rule)


@router.patch(
    "/rules/{rule_id}",
    response_model=RepricingRuleOut,
    summary="Update a repricing rule",
)
async def update_rule(
    rule_id: uuid.UUID,
    data: RepricingRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepricingRuleOut:
    """Update product settings (min_price, step, etc.).

    Step is always capped at 5 KZT.
    """
    rule = await _get_rule_for_user(rule_id, current_user, db)

    update_data = data.model_dump(exclude_unset=True)

    # Enforce step cap
    if "step_kzt" in update_data:
        update_data["step_kzt"] = min(update_data["step_kzt"], MAX_STEP_KZT)

    for field, value in update_data.items():
        setattr(rule, field, value)

    # Validate min < current after update
    if rule.min_price >= rule.my_current_price:
        raise HTTPException(
            status_code=400,
            detail="Минимальная цена должна быть ниже текущей цены."
        )

    await db.flush()
    await db.refresh(rule)
    return RepricingRuleOut.model_validate(rule)


@router.delete(
    "/rules/{rule_id}",
    status_code=204,
    summary="Delete a repricing rule",
)
async def delete_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a product from the repricing bot (deletes all logs too)."""
    rule = await _get_rule_for_user(rule_id, current_user, db)
    await db.delete(rule)
    await db.flush()


# ══════════════════════════════════════════════════════════════
# Toggle ON/OFF — the core user control
# ══════════════════════════════════════════════════════════════

@router.post(
    "/rules/{rule_id}/toggle",
    response_model=RepricingRuleOut,
    summary="Toggle repricing ON or OFF for a product",
)
async def toggle_rule(
    rule_id: uuid.UUID,
    body: RepricingToggle,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepricingRuleOut:
    """User explicitly enables or disables the bot for a specific product.

    When toggled OFF, the bot immediately stops monitoring this product.
    """
    rule = await _get_rule_for_user(rule_id, current_user, db)
    old_state = rule.is_active
    rule.is_active = body.is_active

    await db.flush()
    await db.refresh(rule)

    state_str = "ВКЛ" if body.is_active else "ВЫКЛ"
    logger.info(
        "Repricing toggled %s for %s (was %s) by %s",
        state_str, rule.product_name, "ВКЛ" if old_state else "ВЫКЛ",
        current_user.email,
    )

    return RepricingRuleOut.model_validate(rule)


# ══════════════════════════════════════════════════════════════
# Logs — history of price changes
# ══════════════════════════════════════════════════════════════

@router.get(
    "/rules/{rule_id}/logs",
    response_model=list[RepricingLogOut],
    summary="Get price change history for a product",
)
async def get_rule_logs(
    rule_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RepricingLogOut]:
    """Get the audit trail of all price changes made by the bot."""
    # Verify ownership
    await _get_rule_for_user(rule_id, current_user, db)

    stmt = (
        select(RepricingLog)
        .where(RepricingLog.rule_id == rule_id)
        .order_by(RepricingLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [RepricingLogOut.model_validate(log) for log in logs]


# ══════════════════════════════════════════════════════════════
# Stats — dashboard summary
# ══════════════════════════════════════════════════════════════

@router.get(
    "/stats",
    summary="Get repricing dashboard stats",
)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dashboard KPIs: total products, active bots, total price changes."""
    total_stmt = select(func.count()).select_from(RepricingRule).where(
        RepricingRule.user_id == current_user.id
    )
    active_stmt = select(func.count()).select_from(RepricingRule).where(
        RepricingRule.user_id == current_user.id,
        RepricingRule.is_active == True,  # noqa: E712
    )

    total = (await db.execute(total_stmt)).scalar() or 0
    active = (await db.execute(active_stmt)).scalar() or 0

    # Count total price changes
    rule_ids_stmt = select(RepricingRule.id).where(
        RepricingRule.user_id == current_user.id
    )
    logs_stmt = select(func.count()).select_from(RepricingLog).where(
        RepricingLog.rule_id.in_(rule_ids_stmt)
    )
    total_changes = (await db.execute(logs_stmt)).scalar() or 0

    return {
        "total_products": total,
        "active_bots": active,
        "total_price_changes": total_changes,
    }


# ══════════════════════════════════════════════════════════════
# Sync — auto-import products from Kaspi Seller API
# ══════════════════════════════════════════════════════════════

@router.get(
    "/check-token",
    summary="Check if user has a Kaspi API token configured",
)
async def check_kaspi_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check whether the user has a Kaspi Seller API token saved."""
    stmt = select(UserSellerSettings).where(
        UserSellerSettings.user_id == current_user.id
    )
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    has_token = bool(settings and settings.kaspi_api_key)
    shop_name = settings.kaspi_shop_name if settings else None

    return {
        "has_token": has_token,
        "shop_name": shop_name,
    }


@router.post(
    "/sync",
    summary="Sync products from Kaspi Seller API",
)
async def sync_products(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch all products from Kaspi Seller API and create repricing rules.

    Products that already exist (by kaspi_sku) are skipped.
    Bot is OFF by default for all synced products.
    """
    # 1. Get user's Kaspi API token
    stmt = select(UserSellerSettings).where(
        UserSellerSettings.user_id == current_user.id
    )
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if not settings or not settings.kaspi_api_key:
        raise HTTPException(
            status_code=400,
            detail="Сначала добавьте Kaspi Seller API ключ в настройках NTIN."
        )

    # Decrypt the token
    from retailpool.services.crypto import decrypt_secret
    api_token = decrypt_secret(settings.kaspi_api_key)
    if not api_token:
        raise HTTPException(
            status_code=400,
            detail="Kaspi API ключ повреждён. Пожалуйста, обновите его в настройках."
        )

    # 2. Fetch products from Kaspi
    client = KaspiSellerClient(api_token)

    try:
        kaspi_products = await client.get_products(page=0, size=100)
    except httpx.HTTPStatusError as e:
        logger.exception("Kaspi API sync failed for user %s: HTTP %s", current_user.email, e.response.status_code)
        err_text = e.response.text[:200] if e.response else str(e)
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка подключения к Kaspi API (HTTP {e.response.status_code}): {err_text}"
        )
    except Exception as e:
        logger.exception("Kaspi API sync failed for user %s: %s", current_user.email, e)
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка подключения к Kaspi API: {str(e)[:200]}"
        )

    if not kaspi_products:
        return {"synced": 0, "skipped": 0, "message": "Kaspi API вернул 0 товаров."}

    # 3. Get existing SKUs to avoid duplicates
    existing_stmt = select(RepricingRule.kaspi_sku).where(
        RepricingRule.user_id == current_user.id
    )
    existing_result = await db.execute(existing_stmt)
    existing_skus = {row[0] for row in existing_result.all()}

    # 4. Create rules for new products
    synced = 0
    skipped = 0
    merchant_name = settings.kaspi_shop_name

    for product in kaspi_products:
        # Parse Kaspi API response structure
        attrs = product.get("attributes", {})
        sku = attrs.get("masterSku") or product.get("id", "")
        name = attrs.get("name", "Без названия")
        price = attrs.get("price", 0)

        if not sku:
            continue

        if str(sku) in existing_skus:
            skipped += 1
            continue

        rule = RepricingRule(
            user_id=current_user.id,
            product_name=str(name)[:512],
            kaspi_sku=str(sku),
            product_url=None,  # user fills this later
            my_merchant_name=merchant_name,
            my_current_price=float(price) if price else 0,
            min_price=float(price) * 0.9 if price else 0,  # default: 90% of current
            base_price=float(price) if price else 0,
            step_kzt=5,
            is_active=False,  # OFF by default!
        )
        db.add(rule)
        synced += 1

    await db.flush()

    logger.info(
        "Kaspi sync for %s: synced=%d, skipped=%d",
        current_user.email, synced, skipped,
    )

    return {
        "synced": synced,
        "skipped": skipped,
        "message": f"Импортировано {synced} товаров. Пропущено (уже есть): {skipped}.",
    }
