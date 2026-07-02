"""
Inline keyboards for the Telegram bot.

Centralized keyboard factory — every handler imports from here.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ═══════════════════════════════════════════════════════════════════════════
# Main menu
# ═══════════════════════════════════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main bot menu after /start."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Пулы закупок", callback_data="menu:pools"),
            InlineKeyboardButton("🔍 Сканер Kaspi", callback_data="menu:scanner"),
        ],
        [
            InlineKeyboardButton("🔔 Мои алерты", callback_data="menu:alerts"),
            InlineKeyboardButton("📄 Документы", callback_data="menu:documents"),
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help"),
        ],
    ])


# ═══════════════════════════════════════════════════════════════════════════
# Pools
# ═══════════════════════════════════════════════════════════════════════════

def pool_card_keyboard(pool_id: str) -> InlineKeyboardMarkup:
    """Buttons on each pool card in the marketplace view."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 Войти в пул", callback_data=f"pool:join:{pool_id}"
            ),
            InlineKeyboardButton(
                "📊 Подробнее", callback_data=f"pool:status:{pool_id}"
            ),
        ],
    ])


def pool_join_confirm_keyboard(pool_id: str, quantity: int) -> InlineKeyboardMarkup:
    """Confirmation after user enters quantity."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ Подтвердить ({quantity} шт)",
                callback_data=f"pool:confirm:{pool_id}:{quantity}",
            ),
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data="pool:cancel"),
        ],
    ])


def pool_closed_keyboard(pool_id: str) -> InlineKeyboardMarkup:
    """Buttons for a closed pool (quorum reached)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📄 Получить счёт", callback_data=f"doc:invoice:{pool_id}"
            ),
        ],
    ])


def pool_list_nav_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination buttons for pool list."""
    buttons = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton("◀️ Назад", callback_data=f"pools:page:{page - 1}")
        )
    if page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton("Вперёд ▶️", callback_data=f"pools:page:{page + 1}")
        )
    rows = []
    if buttons:
        rows.append(buttons)
    rows.append([InlineKeyboardButton("🏠 Меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


# ═══════════════════════════════════════════════════════════════════════════
# Scanner
# ═══════════════════════════════════════════════════════════════════════════

def scan_result_keyboard(query: str) -> InlineKeyboardMarkup:
    """Buttons after a scan result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📦 Создать пул", callback_data=f"scan:create_pool:{query[:60]}"
            ),
            InlineKeyboardButton(
                "🔔 Отслеживать", callback_data=f"scan:track:{query[:60]}"
            ),
        ],
        [
            InlineKeyboardButton("🔄 Сканировать ещё", callback_data="menu:scanner"),
            InlineKeyboardButton("🏠 Меню", callback_data="menu:main"),
        ],
    ])


# ═══════════════════════════════════════════════════════════════════════════
# Alerts
# ═══════════════════════════════════════════════════════════════════════════

def alert_list_keyboard(subscriptions: list[dict]) -> InlineKeyboardMarkup:
    """List of active alert subscriptions with unsubscribe buttons."""
    rows = []
    for sub in subscriptions[:10]:
        rows.append([
            InlineKeyboardButton(
                f"🔕 {sub['query'][:30]}",
                callback_data=f"alert:unsub:{sub['id']}",
            ),
        ])
    rows.append([
        InlineKeyboardButton("➕ Новый алерт", callback_data="alert:new"),
        InlineKeyboardButton("🏠 Меню", callback_data="menu:main"),
    ])
    return InlineKeyboardMarkup(rows)


def alert_type_keyboard(query: str) -> InlineKeyboardMarkup:
    """Choose alert type for a new subscription."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📉 Демпинг", callback_data=f"alert:type:dumping:{query[:50]}"
            ),
        ],
        [
            InlineKeyboardButton(
                "📦 Stock-out", callback_data=f"alert:type:stock_out:{query[:50]}"
            ),
        ],
        [
            InlineKeyboardButton(
                "📉+📦 Оба", callback_data=f"alert:type:both:{query[:50]}"
            ),
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data="menu:alerts"),
        ],
    ])


# ═══════════════════════════════════════════════════════════════════════════
# Back / generic
# ═══════════════════════════════════════════════════════════════════════════

def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")],
    ])
