"""
Scanner handler — analyze Kaspi niches from links or text queries.
"""

from __future__ import annotations

import re
import logging
import urllib.parse

from telegram import Update
from telegram.ext import ContextTypes

from retailpool.bot.api_client import RetailPoolAPI
from retailpool.bot.keyboards import scan_result_keyboard, back_to_menu_keyboard

logger = logging.getLogger(__name__)

# Regex to detect kaspi.kz links
KASPI_LINK_RE = re.compile(
    r"https?://(?:www\.)?kaspi\.kz/shop/(?:c/|p/|search/\?text=)([^\s]+)",
    re.IGNORECASE,
)


def _format_price(price: float) -> str:
    return f"{int(price):,} ₸".replace(",", " ")


def _extract_query_from_url(url: str) -> str | None:
    """Extract search query or category slug from a Kaspi URL."""
    # Search URL: kaspi.kz/shop/search/?text=наушники
    if "search/" in url:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        text = params.get("text", [None])[0]
        if text:
            return urllib.parse.unquote(text)

    # Category URL: kaspi.kz/shop/c/air-humidifiers/
    match = re.search(r"/shop/c/([^/?]+)", url)
    if match:
        slug = match.group(1).replace("-", " ")
        return slug

    # Product URL: kaspi.kz/shop/p/product-name-12345/
    match = re.search(r"/shop/p/([^/?]+)", url)
    if match:
        product_slug = match.group(1)
        # Remove trailing ID
        product_slug = re.sub(r"-\d+$", "", product_slug)
        return product_slug.replace("-", " ")

    return None


def _format_scan_result(data: dict, query: str) -> str:
    """Format scan API response into a rich Telegram message."""
    score = data.get("score", 0)
    score_label = data.get("score_label", "—")
    demand = data.get("demand", "—")
    sellers = data.get("sellers", "—")
    avg_price = data.get("avg_price", "—")
    products_scraped = data.get("products_scraped", 0)
    analysis = data.get("analysis", "")
    weaknesses = data.get("weaknesses", [])
    recommendations = data.get("recommendations", [])

    # Score emoji
    if score >= 80:
        score_emoji = "🔥"
    elif score >= 60:
        score_emoji = "🟢"
    elif score >= 40:
        score_emoji = "🟡"
    else:
        score_emoji = "🔴"

    lines = [
        f"🔍 <b>Сканирование: {query}</b>\n",
        f"📊 Niche Score: <b>{score}/100</b> — {score_label} {score_emoji}",
        f"├ Спрос: {demand}",
        f"├ Продавцов: {sellers}",
        f"├ Средняя цена: {avg_price}",
        f"└ Товаров найдено: {products_scraped}",
    ]

    if weaknesses:
        lines.append("\n⚠️ <b>Слабости конкурентов:</b>")
        for w in weaknesses[:3]:
            lines.append(f"  • {w}")

    if recommendations:
        lines.append("\n💡 <b>Рекомендации:</b>")
        for r in recommendations[:3]:
            lines.append(f"  • {r}")

    if analysis:
        lines.append(f"\n📝 {analysis[:500]}")

    # Top products
    products = data.get("products", [])
    if products:
        lines.append("\n📦 <b>Топ товары:</b>")
        for i, p in enumerate(products[:5], 1):
            price_str = _format_price(p["price"]) if p.get("price") else "—"
            rating_str = f"⭐{p['rating']}" if p.get("rating") else ""
            weak_mark = " ⚡" if p.get("is_weak") else ""
            lines.append(
                f"  {i}. {p['title'][:50]}\n"
                f"     {price_str} {rating_str}{weak_mark}"
            )

    return "\n".join(lines)


# ── Command: /scan ───────────────────────────────────────────────────────

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scan <query> command."""
    if not context.args:
        await update.message.reply_text(
            "🔍 Использование: <code>/scan запрос</code>\n\n"
            "Пример: <code>/scan наушники TWS</code>\n\n"
            "Или просто отправьте ссылку с kaspi.kz",
            parse_mode="HTML",
        )
        return

    query = " ".join(context.args)
    await _run_scan(update.message, query)


async def kaspi_link_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle messages containing kaspi.kz links."""
    text = update.message.text or ""

    # Try to extract query from URL
    urls = re.findall(r"https?://[^\s]+", text)
    for url in urls:
        if "kaspi.kz" in url:
            query = _extract_query_from_url(url)
            if query:
                await _run_scan(update.message, query)
                return

    # If no kaspi link found but message looks like a query
    # (this handler is only triggered by kaspi links, so shouldn't reach here)
    pass


async def text_scan_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle plain text that might be a scan query (fallback handler)."""
    text = (update.message.text or "").strip()

    # Skip if it's a command
    if text.startswith("/"):
        return

    # Check if user is in a joining flow
    if context.user_data.get("joining_pool_id"):
        return  # Let pool_quantity_input handle it

    # Check if user is in alert creation flow
    if context.user_data.get("creating_alert"):
        return  # Let alert handler handle it

    # Check for kaspi links
    if "kaspi.kz" in text:
        query = _extract_query_from_url(text)
        if query:
            await _run_scan(update.message, query)
            return

    # For now, don't auto-scan plain text to avoid confusion
    # User should use /scan command explicitly


async def _run_scan(message, query: str) -> None:
    """Execute a scan and send results."""
    # Send "typing" indicator
    await message.reply_text(
        f"🔍 Сканирую <b>«{query}»</b> на Kaspi.kz...\n"
        "⏳ Это может занять 15-30 секунд...",
        parse_mode="HTML",
    )

    try:
        data = await RetailPoolAPI.scan_niche(query)

        if not data.get("success", False):
            error = data.get("error", "Unknown error")
            await message.reply_text(
                f"❌ Сканирование не удалось:\n<code>{error}</code>\n\n"
                "Попробуйте через 30 секунд.",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        text = _format_scan_result(data, query)
        await message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=scan_result_keyboard(query),
        )

    except Exception as exc:
        logger.error("Scan failed: %s", exc)
        await message.reply_text(
            f"❌ Ошибка при сканировании: <code>{exc}</code>\n\n"
            "Убедитесь, что бэкенд запущен.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
