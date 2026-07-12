"""
Repricing Service — Decision Engine.

Contains the core logic that:
  1. Scrapes competitor prices from Kaspi product pages
  2. Decides the optimal price (strictly -step from competitor)
  3. Pushes the new price via Kaspi Seller API
  4. Logs every action for audit trail
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.models.repricing import RepricingRule, RepricingLog
from retailpool.services.kaspi_api import KaspiSellerClient

logger = logging.getLogger(__name__)
async def _notify_user_undercut(
    telegram_id: int | None,
    product_name: str,
    competitor_price: float,
    recommended_price: float,
) -> None:
    """Send a Telegram alert that a competitor undercut the user."""
    if not telegram_id:
        return
    from telegram import Bot
    from retailpool.bot.config import bot_settings

    if not bot_settings.BOT_TOKEN:
        logger.warning("No BOT_TOKEN — cannot send repricing alert.")
        return

    text = (
        f"⚠️ <b>Вас обошли по цене!</b>\n\n"
        f"Товар: {product_name[:60]}\n"
        f"Конкурент: {int(competitor_price)} ₸\n"
        f"Рекомендуемая цена: <b>{int(recommended_price)} ₸</b>\n\n"
        f"Обновите цену через загрузку прайс-листа в кабинете Kaspi."
    )
    try:
        bot = Bot(token=bot_settings.BOT_TOKEN)
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
    except Exception as exc:
        logger.error("Failed to send repricing alert to %s: %s", telegram_id, exc)

def _parse_price(text: str) -> float | None:
    """Parse a price string like '18 500 ₸' into a float."""
    cleaned = re.sub(r"[^\d]", "", text)
    if cleaned:
        return float(cleaned)
    return None


async def scrape_competitor_prices(
    product_url: str,
    my_merchant_name: str | None = None,
) -> list[dict]:
    """Scrape all seller prices from a Kaspi product page.

    Returns list of dicts: [{"merchant": "StoreName", "price": 12345.0}, ...]
    Excludes the user's own store if my_merchant_name is provided.
    """
    from retailpool.scraper.browser import BrowserManager, _run_in_pw_thread_async

    sellers: list[dict] = []

    async with BrowserManager() as bm:
        ctx = await bm.new_context()

        def _scrape():
            page = ctx.new_page()
            try:
                page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                # Click "Все продавцы" / "All sellers" tab if exists
                try:
                    sellers_tab = page.locator(
                        'a[data-tab="sellers"], '
                        'button:has-text("продавц"), '
                        'a:has-text("продавц")'
                    ).first
                    if sellers_tab.is_visible(timeout=3000):
                        sellers_tab.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

                # Parse seller cards
                seller_items = page.locator(
                    '.sellers-table__row, '
                    '.offer__wrap, '
                    '[data-merchant-id]'
                ).all()

                for item in seller_items:
                    try:
                        # Get merchant name
                        name_el = item.locator(
                            '.sellers-table__cell--merchant a, '
                            '.offer__merchant-name, '
                            '.merchant-name'
                        ).first
                        merchant_name = name_el.inner_text().strip() if name_el.is_visible(timeout=1000) else "Unknown"

                        # Get price
                        price_el = item.locator(
                            '.sellers-table__price, '
                            '.offer__price, '
                            '.price'
                        ).first
                        price_text = price_el.inner_text().strip() if price_el.is_visible(timeout=1000) else ""
                        price = _parse_price(price_text)

                        if price and price > 0:
                            sellers.append({
                                "merchant": merchant_name,
                                "price": price,
                            })
                    except Exception:
                        continue

                # Fallback: if no seller cards found, try to get the main price
                if not sellers:
                    try:
                        main_price_el = page.locator(
                            '.item__price-once, '
                            '.price__main-price, '
                            '[itemprop="price"]'
                        ).first
                        if main_price_el.is_visible(timeout=2000):
                            price = _parse_price(main_price_el.inner_text())
                            if price:
                                sellers.append({
                                    "merchant": "__main__",
                                    "price": price,
                                })
                    except Exception:
                        pass

            finally:
                page.close()
                ctx.close()

            return sellers

        sellers = await _run_in_pw_thread_async(_scrape)

    # Filter out user's own store
    if my_merchant_name:
        lower_name = my_merchant_name.lower()
        sellers = [s for s in sellers if s["merchant"].lower() != lower_name]

    return sellers


def compute_new_price(
    my_current_price: float,
    min_price: float,
    base_price: float | None,
    step_kzt: int,
    lowest_competitor_price: float,
) -> tuple[float | None, str]:
    """Compute the new price based on competitor data.

    Returns:
        (new_price, action) where action is one of:
        - "undercut": we went step_kzt below competitor
        - "floor_hit": we hit min_price floor
        - "raise_back": competitor raised price, we follow up
        - "alert_only": competitor is too cheap, we can't compete
        - None: no change needed
    """
    # STRICT RULE: step must never exceed 5 KZT
    step_kzt = min(step_kzt, 5)

    if lowest_competitor_price <= my_current_price:
        # Competitor is cheaper or equal — we need to undercut
        target = lowest_competitor_price - step_kzt

        if target >= min_price:
            # We can undercut exactly by step_kzt
            if target != my_current_price:
                return target, "undercut"
            return None, "no_change"  # Already at the right price
        elif my_current_price > min_price:
            # We hit the floor — set to min_price
            return min_price, "floor_hit"
        else:
            # Already at min_price, can't go lower
            return None, "alert_only"

    elif lowest_competitor_price > my_current_price + step_kzt:
        # Competitor raised price — we should raise too to recover margin
        # but stay exactly step_kzt below them
        target = lowest_competitor_price - step_kzt

        # If we have a base_price ceiling, don't go above it
        if base_price and target > base_price:
            target = base_price

        if target != my_current_price and target > my_current_price:
            return target, "raise_back"

    return None, "no_change"


async def process_single_rule(
    rule: RepricingRule,
    kaspi_client: KaspiSellerClient,
    db: AsyncSession,
) -> dict:
    """Process a single repricing rule: scrape, decide, push, log.

    Returns a status dict with the result.
    """
    result = {
        "rule_id": str(rule.id),
        "product": rule.product_name,
        "action": "no_change",
        "old_price": rule.my_current_price,
        "new_price": None,
        "competitor_price": None,
    }

    try:
        # Step 1: Scrape competitor prices
        if not rule.product_url:
            result["action"] = "skip_no_url"
            return result

        sellers = await scrape_competitor_prices(
            rule.product_url,
            rule.my_merchant_name,
        )

        if not sellers:
            result["action"] = "skip_no_competitors"
            return result

        lowest = min(s["price"] for s in sellers)
        result["competitor_price"] = lowest

        # Update monitoring state
        rule.last_competitor_price = lowest
        rule.last_checked_at = datetime.now(timezone.utc)

        # Step 2: Compute new price
        new_price, action = compute_new_price(
            my_current_price=rule.my_current_price,
            min_price=rule.min_price,
            base_price=rule.base_price,
            step_kzt=rule.step_kzt,
            lowest_competitor_price=lowest,
        )

        result["action"] = action

        if new_price is None:
            return result

        # Step 3: Push new price via Kaspi API
        await kaspi_client.update_price(rule.kaspi_sku, new_price)

        # Step 4: Log the change
        log = RepricingLog(
            rule_id=rule.id,
            old_price=rule.my_current_price,
            new_price=new_price,
            competitor_price=lowest,
            action=action,
        )
        db.add(log)

        # Update rule's current price
        rule.my_current_price = new_price
        result["new_price"] = new_price

        logger.info(
            "Repricing [%s]: %s -> %s (competitor: %s, action: %s)",
            rule.product_name[:30], rule.my_current_price,
            new_price, lowest, action,
        )

    except Exception as e:
        logger.exception("Repricing error for rule %s: %s", rule.id, e)
        result["action"] = f"error: {str(e)[:100]}"

    return result


async def run_repricing_cycle(db: AsyncSession) -> list[dict]:
    """Run one full repricing cycle for all active rules across all users.

    This is called by the background worker.
    """
    stmt = select(RepricingRule).where(RepricingRule.is_active == True)  # noqa: E712
    rows = await db.execute(stmt)
    rules = rows.scalars().all()

    if not rules:
        return []

    from retailpool.models.ntin import UserSellerSettings
    from retailpool.services.crypto import decrypt_secret

    # Group rules by user_id
    user_rules = {}
    for rule in rules:
        user_rules.setdefault(rule.user_id, []).append(rule)

    results = []

    for user_id, u_rules in user_rules.items():
        # Get Kaspi token for this user
        settings_stmt = select(UserSellerSettings).where(UserSellerSettings.user_id == user_id)
        settings = (await db.execute(settings_stmt)).scalar_one_or_none()
        
        if not settings or not settings.kaspi_api_key:
            logger.warning("Repricing skipped for user %s: no Kaspi token.", user_id)
            continue
            
        token = decrypt_secret(settings.kaspi_api_key)
        if not token:
            continue
            
        client = KaspiSellerClient(token)
        
        for rule in u_rules:
            result = await process_single_rule(rule, client, db)
            results.append(result)

    await db.commit()
    return results
