"""
Alert Worker — background job that checks niche subscriptions periodically.

Runs in a separate thread alongside the PTB application.
Uses APScheduler for periodic execution.
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone

from telegram import Bot

from retailpool.bot.config import bot_settings
from retailpool.bot.api_client import RetailPoolAPI

logger = logging.getLogger(__name__)

# Thresholds for triggering alerts
DUMPING_THRESHOLD_PERCENT = 15  # Price drop > 15%
STOCK_OUT_THRESHOLD = 0  # Seller disappeared


async def check_alerts(bot: Bot) -> None:
    """
    Check all active alert subscriptions and send notifications.

    Called periodically by APScheduler.
    """
    from retailpool.bot.handlers.alerts import (
        get_all_active_alerts,
        update_alert_snapshot,
    )

    all_alerts = get_all_active_alerts()
    if not all_alerts:
        return

    logger.info("Alert worker: checking %d users with active alerts",
                len(all_alerts))

    for user_id, alerts in all_alerts.items():
        for alert in alerts:
            try:
                await _check_single_alert(bot, user_id, alert)
            except Exception as exc:
                logger.error(
                    "Alert check failed for user %d, alert %s: %s",
                    user_id, alert["id"], exc,
                )


async def _check_single_alert(bot: Bot, user_id: int, alert: dict) -> None:
    """Check a single alert subscription against current market data."""
    from retailpool.bot.handlers.alerts import update_alert_snapshot

    query = alert["query"]
    alert_type = alert["type"]
    last_snapshot = alert.get("last_snapshot")

    # Scan the niche
    try:
        scan_data = await RetailPoolAPI.scan_niche(query)
    except Exception as exc:
        logger.warning("Scan failed for alert %s: %s", alert["id"], exc)
        return

    if not scan_data.get("success"):
        return

    # Build current snapshot
    products = scan_data.get("products", [])
    current_snapshot = {
        "avg_price": _parse_price(scan_data.get("avg_price", "0")),
        "score": scan_data.get("score", 0),
        "sellers": scan_data.get("sellers", "—"),
        "products": {
            p["kaspi_id"]: {
                "title": p.get("title", ""),
                "price": p.get("price", 0),
                "seller_count": p.get("seller_count", 0),
            }
            for p in products[:20]
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    notifications = []

    if last_snapshot:
        # ── Dumping detection ────────────────────────────────────────────
        if alert_type in ("dumping", "both"):
            old_avg = last_snapshot.get("avg_price", 0)
            new_avg = current_snapshot["avg_price"]

            if old_avg > 0 and new_avg > 0:
                price_change_pct = ((old_avg - new_avg) / old_avg) * 100
                if price_change_pct >= DUMPING_THRESHOLD_PERCENT:
                    notifications.append(
                        f"🚨 <b>Демпинг в нише «{query}»!</b>\n\n"
                        f"Средняя цена упала на {price_change_pct:.0f}%\n"
                        f"Было: {_format_price(old_avg)}\n"
                        f"Стало: {_format_price(new_avg)}\n\n"
                        f"Проверьте конкурентов: /scan {query}"
                    )

            # Check individual product price drops
            old_products = last_snapshot.get("products", {})
            for pid, new_data in current_snapshot["products"].items():
                if pid in old_products:
                    old_price = old_products[pid].get("price", 0)
                    new_price = new_data.get("price", 0)
                    if old_price > 0 and new_price > 0:
                        drop_pct = ((old_price - new_price) / old_price) * 100
                        if drop_pct >= DUMPING_THRESHOLD_PERCENT:
                            title = new_data.get("title", pid)[:40]
                            notifications.append(
                                f"📉 <b>Конкурент снизил цену!</b>\n\n"
                                f"Товар: {title}\n"
                                f"Было: {_format_price(old_price)}\n"
                                f"Стало: {_format_price(new_price)} "
                                f"(-{drop_pct:.0f}%)"
                            )

        # ── Stock-out detection ──────────────────────────────────────────
        if alert_type in ("stock_out", "both"):
            old_products = last_snapshot.get("products", {})
            new_product_ids = set(current_snapshot["products"].keys())

            for pid, old_data in old_products.items():
                if pid not in new_product_ids:
                    title = old_data.get("title", pid)[:40]
                    notifications.append(
                        f"💡 <b>Возможность!</b>\n\n"
                        f"Товар «{title}» пропал из выдачи\n"
                        f"в нише «{query}».\n\n"
                        f"Возможно, продавец ушёл — окно для перехвата трафика!"
                    )

    # Send notifications (limit to 3 per check to avoid spam)
    for notification in notifications[:3]:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=notification,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.error("Failed to send alert to user %d: %s", user_id, exc)

    # Update snapshot
    update_alert_snapshot(user_id, alert["id"], current_snapshot)


def _parse_price(price_str: str) -> float:
    """Parse price string like '18 500 ₸' into a float."""
    try:
        cleaned = price_str.replace("₸", "").replace(" ", "").strip()
        return float(cleaned) if cleaned else 0
    except (ValueError, AttributeError):
        return 0


def _format_price(price: float) -> str:
    return f"{int(price):,} ₸".replace(",", " ")
