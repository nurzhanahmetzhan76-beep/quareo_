"""
/start and /help handlers + main menu navigation.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from retailpool.bot.keyboards import main_menu_keyboard, back_to_menu_keyboard

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "🏪 <b>RetailPool AI</b> — ваш персональный помощник\n"
    "для совместных закупок на Kaspi.kz\n\n"
    "Что я умею:\n"
    "📦 <b>Пулы закупок</b> — витрина совместных закупок, вход в один клик\n"
    "🔍 <b>Сканер Kaspi</b> — анализ ниши по ссылке или запросу\n"
    "🔔 <b>Push-алерты</b> — трекинг демпинга и стоков конкурентов\n"
    "📄 <b>Документы</b> — автоматическая генерация счетов\n\n"
    "Выберите действие ниже 👇"
)

HELP_TEXT = (
    "📖 <b>Справка по командам</b>\n\n"
    "/start — Главное меню\n"
    "/pools — Витрина открытых пулов\n"
    "/scan &lt;запрос&gt; — Анализ ниши на Kaspi\n"
    "/track &lt;запрос&gt; — Подписка на алерт по нише\n"
    "/alerts — Мои активные подписки\n"
    "/help — Эта справка\n\n"
    "💡 <b>Совет:</b> Просто отправьте ссылку на товар или категорию\n"
    "с Kaspi.kz — бот автоматически запустит анализ!"
)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — show welcome message and main menu."""
    user = update.effective_user
    logger.info("User %s (%s) started the bot", user.id, user.username)
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main menu button presses (callback_data starting with 'menu:')."""
    query = update.callback_query
    await query.answer()

    action = query.data.split(":", 1)[1] if ":" in query.data else ""

    if action == "main":
        await query.edit_message_text(
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    elif action == "help":
        await query.edit_message_text(
            HELP_TEXT,
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
    elif action == "pools":
        # Import here to avoid circular imports
        from retailpool.bot.handlers.pools import show_pools_list
        await show_pools_list(query, context)
    elif action == "scanner":
        await query.edit_message_text(
            "🔍 <b>Сканер Kaspi</b>\n\n"
            "Отправьте мне:\n"
            "• Ссылку на категорию или товар с kaspi.kz\n"
            "• Или текстовый запрос (например: «наушники TWS»)\n\n"
            "Также можно использовать команду:\n"
            "<code>/scan наушники TWS</code>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
    elif action == "alerts":
        from retailpool.bot.handlers.alerts import show_alerts_list
        await show_alerts_list(query, context)
    elif action == "documents":
        await query.edit_message_text(
            "📄 <b>Документы</b>\n\n"
            "Счета генерируются автоматически при закрытии пула.\n"
            "Перейдите в раздел Пулов и нажмите «📄 Получить счёт»\n"
            "на закрытом пуле.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
