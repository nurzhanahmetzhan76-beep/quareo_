"""
RetailPool AI Telegram Bot — PTB Application with Webhook support.

This is the main bot application that wires together all handlers
and provides both webhook (production) and polling (dev) modes.
"""

from __future__ import annotations

import logging
import asyncio
from threading import Thread

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from retailpool.bot.config import bot_settings
from retailpool.bot.api_client import close_client

# Handlers
from retailpool.bot.handlers.start import (
    start_handler,
    help_handler,
    menu_callback,
)

from retailpool.bot.handlers.scanner import (
    scan_command,
    kaspi_link_handler,
)

from retailpool.bot.handlers.alerts import (
    alerts_command,
    track_command,
    untrack_command,
    alert_callback,
    alert_text_input,
)
from retailpool.bot.handlers.auth import (
    login_command,
    auth_middleware,
)

logger = logging.getLogger(__name__)

# Bot commands for the Telegram menu
BOT_COMMANDS = [
    BotCommand("start", "Главное меню"),

    BotCommand("scan", "Сканировать нишу на Kaspi"),
    BotCommand("track", "Подписаться на алерт по нише"),
    BotCommand("alerts", "Мои активные подписки"),
    BotCommand("untrack", "Отписаться от алерта"),
    BotCommand("login", "Авторизация в боте"),
    BotCommand("help", "Справка по командам"),
]


def create_application() -> Application:
    """
    Build and configure the PTB Application.

    Returns a fully configured Application instance
    ready for polling or webhook mode.
    """
    if not bot_settings.BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Please add it to your .env file."
        )

    from telegram.ext import PicklePersistence, TypeHandler
    persistence = PicklePersistence(filepath="retailpool_bot_data.pickle")

    builder = Application.builder().token(bot_settings.BOT_TOKEN).persistence(persistence)
    app = builder.build()

    # ── Register Auth Middleware ─────────────────────────────────────────
    # Runs before all other handlers (group=-1) and stops execution if not authorized
    app.add_handler(TypeHandler(Update, auth_middleware), group=-1)

    # ── Register command handlers ────────────────────────────────────────
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("login", login_command))

    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("track", track_command))
    app.add_handler(CommandHandler("untrack", untrack_command))
    app.add_handler(CommandHandler("alerts", alerts_command))

    # ── Register callback query handlers ─────────────────────────────────
    # Order matters: more specific patterns first


    app.add_handler(CallbackQueryHandler(alert_callback, pattern=r"^alert:"))
    app.add_handler(CallbackQueryHandler(
        _scan_callback, pattern=r"^scan:"
    ))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))

    # ── Register message handlers ────────────────────────────────────────
    # Kaspi links (higher priority)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"kaspi\.kz"),
        kaspi_link_handler,
    ))



    # Alert text input (when creating_alert flag is set)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        _text_router,
    ))

    # ── Post-init: set bot commands ──────────────────────────────────────
    app.post_init = _post_init

    return app


async def _post_init(application: Application) -> None:
    """Set bot commands in Telegram menu after initialization."""
    try:
        await application.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot commands registered with Telegram")
    except Exception as exc:
        logger.warning("Failed to set bot commands: %s", exc)
    
    # Start the alert worker now that the event loop is running
    start_alert_worker(application)


async def _text_router(update: Update, context) -> None:
    """Route plain text messages to the appropriate handler."""
    # Check if user is in a specific flow
    if context.user_data.get("creating_alert"):
        await alert_text_input(update, context)
    # Otherwise ignore plain text (don't auto-scan)


async def _scan_callback(update: Update, context) -> None:
    """Handle scan-related callbacks (scan:create_pool, scan:track)."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]
    value = ":".join(parts[2:])

    if action == "track":
        # Auto-create alert
        from retailpool.bot.keyboards import alert_type_keyboard
        await query.edit_message_text(
            f"🔔 <b>Новый алерт: «{value}»</b>\n\n"
            "Выберите тип отслеживания:",
            parse_mode="HTML",
            reply_markup=alert_type_keyboard(value),
        )


def start_alert_worker(application: Application) -> None:
    """Start the background alert worker using APScheduler."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from retailpool.bot.alert_worker import check_alerts

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            check_alerts,
            "interval",
            minutes=bot_settings.ALERT_CHECK_INTERVAL_MINUTES,
            args=[application.bot],
            id="alert_checker",
            name="Alert Checker",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            "Alert worker started (interval: %d min)",
            bot_settings.ALERT_CHECK_INTERVAL_MINUTES,
        )
    except ImportError:
        logger.warning(
            "APScheduler not installed — alert worker disabled. "
            "Install with: pip install apscheduler"
        )
    except Exception as exc:
        logger.error("Failed to start alert worker: %s", exc)


async def shutdown(application: Application) -> None:
    """Cleanup on shutdown."""
    await close_client()
    logger.info("Bot shutdown complete")
