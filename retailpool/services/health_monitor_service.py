"""
Health Monitor Service — "пожарная сигнализация" for the seller's shop.

Watches two signals via the Kaspi Seller API:
  1. Order cancellation rate — if it approaches the critical 2.8% mark,
     the seller is warned before Kaspi penalizes their account.
  2. New 1-star reviews — sent to Telegram the moment they appear, so
     the seller can react (contact the buyer, resolve the issue) fast.

This module never writes anything back to Kaspi — it only reads orders
and reviews and notifies the seller. Applying any fix (replying to a
review, resolving an order) is done by the seller in their own Kaspi
cabinet, exactly like the safe repricing flow.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.models.ntin import UserSellerSettings
from retailpool.models.user import User
from retailpool.services.kaspi_api import KaspiSellerClient
from retailpool.services.crypto import decrypt_secret

logger = logging.getLogger(__name__)

# ── Thresholds (per Ali's spec) ────────────────────────────────────
CANCELLATION_RATE_THRESHOLD = 2.8   # percent
CANCELLATION_WINDOW_DAYS = 30       # rolling window, matches Kaspi's own metric
ONE_STAR_RATING = 1


async def _notify(telegram_id: int | None, text: str) -> None:
    """Send a Telegram alert. Silently no-ops if telegram isn't linked."""
    if not telegram_id:
        return
    from telegram import Bot
    from retailpool.bot.config import bot_settings

    if not bot_settings.BOT_TOKEN:
        logger.warning("No BOT_TOKEN — cannot send health monitor alert.")
        return

    try:
        bot = Bot(token=bot_settings.BOT_TOKEN)
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
    except Exception as exc:
        logger.error("Failed to send health alert to %s: %s", telegram_id, exc)


async def check_single_seller(settings: UserSellerSettings, owner: User) -> dict:
    """Run both checks for one seller. Returns a small summary dict for logging."""
    token = decrypt_secret(settings.kaspi_api_key)
    if not token:
        return {"skipped": "no_kaspi_token"}

    client = KaspiSellerClient(token)
    result = {"cancellation": None, "new_one_star_reviews": 0}

    # ── 1. Cancellation rate ────────────────────────────────────────
    try:
        stats = await client.get_cancellation_rate(days=CANCELLATION_WINDOW_DAYS)
        result["cancellation"] = stats
        rate = stats["rate_percent"]

        if rate >= CANCELLATION_RATE_THRESHOLD:
            if not settings.cancellation_alert_sent:
                text = (
                    f"🚨 <b>Внимание! Процент отмен приближается к критическому!</b>\n\n"
                    f"За последние {CANCELLATION_WINDOW_DAYS} дней: "
                    f"<b>{rate}%</b> отмен ({stats['cancelled']} из {stats['total']} заказов).\n"
                    f"Критическая отметка Kaspi: {CANCELLATION_RATE_THRESHOLD}%.\n\n"
                    f"Проверьте причины отмен в кабинете Kaspi, чтобы не потерять рейтинг магазина."
                )
                await _notify(owner.telegram_id, text)
                settings.cancellation_alert_sent = True
        else:
            # Rate is healthy again — reset so we alert again if it re-crosses.
            settings.cancellation_alert_sent = False

    except Exception as exc:
        logger.warning("Cancellation check failed for user %s: %s", owner.id, exc)

    # ── 2. New 1-star reviews ───────────────────────────────────────
    try:
        since_ms = settings.last_review_check_ts
        reviews = await client.get_negative_reviews(since_ms=since_ms)

        one_star = [
            r for r in reviews
            if r.get("attributes", {}).get("rating") == ONE_STAR_RATING
        ]
        result["new_one_star_reviews"] = len(one_star)

        for review in one_star:
            attrs = review.get("attributes", {})
            comment = (attrs.get("comment") or "").strip()
            comment_preview = (comment[:200] + "…") if len(comment) > 200 else comment
            text = (
                f"⭐ <b>Новый отзыв 1 звезда!</b>\n\n"
                f"{comment_preview or '(без комментария)'}\n\n"
                f"Ответьте покупателю в кабинете Kaspi, пока это не повлияло на рейтинг магазина."
            )
            await _notify(owner.telegram_id, text)

        # Move the cursor forward regardless, so we don't re-check old reviews.
        import time
        settings.last_review_check_ts = int(time.time() * 1000)

    except Exception as exc:
        logger.warning("Review check failed for user %s: %s", owner.id, exc)

    return result


async def run_health_check_cycle(db: AsyncSession) -> list[dict]:
    """Run health checks for every user who has enabled the monitor."""
    stmt = select(UserSellerSettings).where(
        UserSellerSettings.health_monitor_enabled == True,  # noqa: E712
        UserSellerSettings.kaspi_api_key.isnot(None),
    )
    rows = await db.execute(stmt)
    all_settings = rows.scalars().all()

    if not all_settings:
        return []

    results = []
    for settings in all_settings:
        owner = (await db.execute(
            select(User).where(User.id == settings.user_id)
        )).scalar_one_or_none()
        if not owner:
            continue
        try:
            res = await check_single_seller(settings, owner)
            results.append({"user_id": str(owner.id), **res})
        except Exception as exc:
            logger.error("Health check failed for user %s: %s", owner.id, exc)

    await db.commit()
    return results
