"""
Pool handlers — marketplace view, join flow, status, quorum notifications.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

from retailpool.bot.api_client import RetailPoolAPI
from retailpool.bot.keyboards import (
    pool_card_keyboard,
    pool_closed_keyboard,
    pool_list_nav_keyboard,
    pool_join_confirm_keyboard,
    back_to_menu_keyboard,
)

logger = logging.getLogger(__name__)

POOLS_PER_PAGE = 3


def _format_price(price: float) -> str:
    """Format price in tenge."""
    return f"{int(price):,} ₸".replace(",", " ")


def _progress_bar(percent: float, length: int = 10) -> str:
    """Render a text progress bar: ████████░░"""
    filled = int(percent / 100 * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def _time_remaining(expires_at_str: str) -> str:
    """Human-readable time remaining from ISO datetime string."""
    try:
        expires = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = expires - now
        if delta.total_seconds() <= 0:
            return "Истёк"
        days = delta.days
        hours = delta.seconds // 3600
        if days > 0:
            return f"{days}д {hours}ч"
        return f"{hours}ч {(delta.seconds % 3600) // 60}м"
    except Exception:
        return "—"


def _format_pool_card(pool: dict) -> str:
    """Format a single pool into a rich text card."""
    status = pool.get("status", "open")
    name = pool.get("product_name", "Товар")
    supplier = pool.get("supplier_name", "—")
    target_qty = pool.get("target_quantity", 0)
    current_qty = pool.get("current_quantity", 0)
    target_amt = pool.get("target_amount", 0)
    current_amt = pool.get("current_amount", 0)
    expires = pool.get("expires_at", "")

    # Compute per-unit prices
    unit_buy_price = target_amt / target_qty if target_qty > 0 else 0
    # Estimate sell price (30% margin)
    unit_sell_price = unit_buy_price * 1.3

    qty_pct = (current_qty / target_qty * 100) if target_qty > 0 else 0
    remaining = target_qty - current_qty

    status_emoji = {
        "open": "🟢",
        "closed": "🔴",
        "completed": "✅",
        "expired": "⏰",
        "cancelled": "❌",
    }.get(status, "❓")

    lines = [
        f"{status_emoji} <b>{name}</b>",
        f"├ Поставщик: {supplier}",
        f"├ Закуп: {_format_price(unit_buy_price)}/шт",
        f"├ Целевая продажа: ~{_format_price(unit_sell_price)}/шт",
    ]

    if status == "open":
        lines.extend([
            f"├ Нужно собрать: {target_qty} шт",
            f"├ Собрано: {_progress_bar(qty_pct)} {qty_pct:.0f}% ({current_qty}/{target_qty})",
            f"├ Осталось: {remaining} шт",
            f"└ Дедлайн: {_time_remaining(expires)}",
        ])
    elif status == "closed":
        lines.append("└ ✅ Кворум собран! Закупка в процессе.")
    elif status == "completed":
        lines.append("└ ✅ Закупка завершена.")
    elif status == "expired":
        lines.append("└ ⏰ Срок истёк.")

    return "\n".join(lines)


# ── Command: /pools ──────────────────────────────────────────────────────

async def pools_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pools command — show open pools marketplace."""
    try:
        pools = await RetailPoolAPI.get_open_pools()
    except Exception as exc:
        logger.error("Failed to fetch pools: %s", exc)
        await update.message.reply_text(
            "❌ Не удалось загрузить пулы. Бэкенд недоступен.\n"
            f"Ошибка: <code>{exc}</code>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if not pools:
        await update.message.reply_text(
            "📦 <b>Витрина пулов</b>\n\n"
            "Сейчас нет открытых пулов.\n"
            "Создайте новый пул после сканирования ниши!",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    # Show first page
    await _send_pools_page(update.message, pools, page=0)


async def show_pools_list(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show pools list from a callback query (menu button press)."""
    try:
        pools = await RetailPoolAPI.get_open_pools()
    except Exception as exc:
        logger.error("Failed to fetch pools: %s", exc)
        await query.edit_message_text(
            "❌ Не удалось загрузить пулы.\n"
            f"Ошибка: <code>{exc}</code>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if not pools:
        await query.edit_message_text(
            "📦 <b>Витрина пулов</b>\n\n"
            "Сейчас нет открытых пулов.\n"
            "Создайте новый пул после сканирования ниши!",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    text = _build_pools_page_text(pools, 0)
    total_pages = (len(pools) + POOLS_PER_PAGE - 1) // POOLS_PER_PAGE
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=pool_list_nav_keyboard(0, total_pages),
    )


async def _send_pools_page(message, pools: list[dict], page: int) -> None:
    """Send a page of pool cards."""
    text = _build_pools_page_text(pools, page)
    total_pages = (len(pools) + POOLS_PER_PAGE - 1) // POOLS_PER_PAGE
    await message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=pool_list_nav_keyboard(page, total_pages),
    )


def _build_pools_page_text(pools: list[dict], page: int) -> str:
    """Build the text for a page of pools."""
    total = len(pools)
    total_pages = (total + POOLS_PER_PAGE - 1) // POOLS_PER_PAGE
    start = page * POOLS_PER_PAGE
    end = min(start + POOLS_PER_PAGE, total)
    page_pools = pools[start:end]

    header = f"📦 <b>Витрина пулов</b> (стр. {page + 1}/{total_pages})\n\n"
    cards = []
    for p in page_pools:
        card = _format_pool_card(p)
        pool_id = p.get("id", "")
        cards.append(
            f"{card}\n"
            f"  → /join_{pool_id[:8]}\n"
        )

    return header + "\n\n".join(cards)


# ── Callback: pool actions ───────────────────────────────────────────────

async def pool_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pool-related callback queries."""
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "pool:join:uuid", "pool:status:uuid"
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]
    pool_id = parts[2]

    if action == "join":
        # Ask for quantity
        context.user_data["joining_pool_id"] = pool_id
        await query.edit_message_text(
            "🛒 <b>Вход в пул</b>\n\n"
            "Сколько единиц товара вы хотите заказать?\n"
            "Отправьте число (например: <code>10</code>)",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

    elif action == "status":
        try:
            status = await RetailPoolAPI.get_pool_status(pool_id)
            pool_data = status.get("pool", {})
            card = _format_pool_card(pool_data)

            participants = status.get("participants", [])
            participant_lines = []
            for p in participants[:10]:
                participant_lines.append(
                    f"  • Участник {p['user_id'][:8]}... — {p['quantity']} шт, "
                    f"{_format_price(p['amount'])}"
                )

            full_text = (
                f"📊 <b>Статус пула</b>\n\n"
                f"{card}\n\n"
                f"👥 Участники ({len(participants)}):\n"
                + ("\n".join(participant_lines) if participant_lines else "  Пока нет")
            )

            kb = pool_card_keyboard(pool_id)
            if pool_data.get("status") == "closed":
                kb = pool_closed_keyboard(pool_id)

            await query.edit_message_text(
                full_text, parse_mode="HTML", reply_markup=kb
            )
        except Exception as exc:
            logger.error("Failed to get pool status: %s", exc)
            await query.edit_message_text(
                f"❌ Ошибка при получении статуса: {exc}",
                reply_markup=back_to_menu_keyboard(),
            )

    elif action == "confirm":
        # pool:confirm:pool_id:quantity
        if len(parts) >= 4:
            quantity = int(parts[3])
            user_id = str(update.effective_user.id)
            try:
                # Estimate amount (unit price * quantity)
                pool_status = await RetailPoolAPI.get_pool_status(pool_id)
                pool_data = pool_status.get("pool", {})
                target_qty = pool_data.get("target_quantity", 1)
                target_amt = pool_data.get("target_amount", 0)
                unit_price = target_amt / target_qty if target_qty > 0 else 0
                amount = unit_price * quantity

                result = await RetailPoolAPI.join_pool(
                    pool_id, user_id, quantity, amount
                )

                pool_out = result.get("pool", {})
                qty_pct = result.get("quantity_progress_percent", 0)
                is_quorum = result.get("is_quorum_reached", False)

                text = (
                    "✅ <b>Вы успешно вошли в пул!</b>\n\n"
                    f"Ваш заказ: {quantity} шт × {_format_price(unit_price)} = {_format_price(amount)}\n\n"
                    f"Прогресс пула: {_progress_bar(qty_pct)} {qty_pct:.0f}%\n"
                )

                if is_quorum:
                    text += (
                        "\n🎉 <b>Кворум достигнут!</b>\n"
                        "Пул закрыт. Закупка начинается!\n"
                        "Ожидайте счёт на оплату."
                    )

                kb = back_to_menu_keyboard()
                if is_quorum:
                    kb = pool_closed_keyboard(pool_id)

                await query.edit_message_text(
                    text, parse_mode="HTML", reply_markup=kb
                )

            except Exception as exc:
                logger.error("Failed to join pool: %s", exc)
                await query.edit_message_text(
                    f"❌ Ошибка при входе в пул: {exc}",
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard(),
                )

    elif action == "cancel":
        context.user_data.pop("joining_pool_id", None)
        await query.edit_message_text(
            "❌ Вход в пул отменён.",
            reply_markup=back_to_menu_keyboard(),
        )


async def pool_quantity_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle quantity input when user is joining a pool."""
    pool_id = context.user_data.get("joining_pool_id")
    if not pool_id:
        return  # Not in join flow

    text = update.message.text.strip()
    try:
        quantity = int(text)
        if quantity <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте положительное число.\n"
            "Например: <code>10</code>",
            parse_mode="HTML",
        )
        return

    # Clear the joining state
    context.user_data.pop("joining_pool_id", None)

    await update.message.reply_text(
        f"🛒 Подтвердите вход в пул\n\n"
        f"Количество: <b>{quantity} шт</b>\n\n"
        f"Нажмите кнопку для подтверждения:",
        parse_mode="HTML",
        reply_markup=pool_join_confirm_keyboard(pool_id, quantity),
    )


# ── Callback: page navigation ───────────────────────────────────────────

async def pools_page_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle pool list pagination."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")  # pools:page:N
    if len(parts) >= 3:
        page = int(parts[2])
        try:
            pools = await RetailPoolAPI.get_open_pools()
            text = _build_pools_page_text(pools, page)
            total_pages = (len(pools) + POOLS_PER_PAGE - 1) // POOLS_PER_PAGE
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=pool_list_nav_keyboard(page, total_pages),
            )
        except Exception as exc:
            logger.error("Failed to load pools page: %s", exc)
