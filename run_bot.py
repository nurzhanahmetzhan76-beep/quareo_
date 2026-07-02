"""
RetailPool AI — Telegram Bot Entry Point.

Usage:
    # Polling mode (development — no public URL needed)
    python run_bot.py --polling

    # Webhook mode (production — requires TELEGRAM_WEBHOOK_URL in .env)
    python run_bot.py --webhook

    # Default: polling
    python run_bot.py
"""

from __future__ import annotations

import sys
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("retailpool.bot")


def main() -> None:
    parser = argparse.ArgumentParser(description="RetailPool AI Telegram Bot")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--polling",
        action="store_true",
        default=True,
        help="Run in long-polling mode (default, for development)",
    )
    group.add_argument(
        "--webhook",
        action="store_true",
        help="Run in webhook mode (production, requires public URL)",
    )
    args = parser.parse_args()

    from retailpool.bot.config import bot_settings
    from retailpool.bot.app import create_application, start_alert_worker, shutdown

    if not bot_settings.BOT_TOKEN:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set! "
            "Add it to .env: TELEGRAM_BOT_TOKEN=your-token-here"
        )
        sys.exit(1)

    application = create_application()

    if args.webhook:
        # Webhook mode
        if not bot_settings.WEBHOOK_URL:
            logger.error(
                "TELEGRAM_WEBHOOK_URL is not set! "
                "Required for webhook mode. "
                "Set it in .env or use --polling for development."
            )
            sys.exit(1)

        webhook_url = bot_settings.full_webhook_url
        logger.info("Starting bot in WEBHOOK mode")
        logger.info("Webhook URL: %s", webhook_url)
        logger.info("Listen: %s:%d", bot_settings.WEBHOOK_HOST, bot_settings.WEBHOOK_PORT)

        application.run_webhook(
            listen=bot_settings.WEBHOOK_HOST,
            port=bot_settings.WEBHOOK_PORT,
            url_path=bot_settings.webhook_path,
            webhook_url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
    else:
        # Polling mode (default for development)
        logger.info("Starting bot in POLLING mode (development)")
        logger.info("Bot token: %s...%s", bot_settings.BOT_TOKEN[:10], bot_settings.BOT_TOKEN[-5:])

        application.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )


if __name__ == "__main__":
    main()
