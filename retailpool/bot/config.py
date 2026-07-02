"""
Bot-specific configuration.

Reads from the same .env as the main FastAPI app.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class BotSettings:
    """Telegram bot settings pulled from environment."""

    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    API_BASE_URL: str = os.getenv("BOT_API_BASE_URL", "http://localhost:8000")
    API_KEY: str = os.getenv("API_KEY", "change-me-in-production")

    # Alert worker
    ALERT_CHECK_INTERVAL_MINUTES: int = int(
        os.getenv("ALERT_CHECK_INTERVAL_MINUTES", "30")
    )

    # Webhook server
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "5000"))

    @property
    def webhook_path(self) -> str:
        """Webhook URL path derived from bot token for security."""
        return f"/webhook/{self.BOT_TOKEN}"

    @property
    def full_webhook_url(self) -> str:
        """Full public webhook URL for Telegram setWebhook."""
        base = self.WEBHOOK_URL.rstrip("/")
        return f"{base}{self.webhook_path}"


bot_settings = BotSettings()
