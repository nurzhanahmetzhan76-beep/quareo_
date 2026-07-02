"""
RetailPool AI v2.0 — Configuration Module.

Centralizes all settings via Pydantic BaseSettings.
Hardcoded target Kaspi categories for MVP scanning.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field


# ---------------------------------------------------------------------------
# Target categories for Kaspi Niche Scanner (MVP hardcoded list)
# Team Lead note: Don't crawl the entire catalog. Start narrow.
# ---------------------------------------------------------------------------
TARGET_CATEGORIES: list[dict[str, str]] = [
    {
        "name": "Увлажнители воздуха",
        "url": "https://kaspi.kz/shop/c/air-humidifiers/",
        "slug": "air-humidifiers",
    },
    {
        "name": "Очистители воздуха",
        "url": "https://kaspi.kz/shop/c/air-purifiers/",
        "slug": "air-purifiers",
    },
    {
        "name": "Автоаксессуары",
        "url": "https://kaspi.kz/shop/c/auto-accessories/",
        "slug": "auto-accessories",
    },
    {
        "name": "Автоэлектроника",
        "url": "https://kaspi.kz/shop/c/auto-electronics/",
        "slug": "auto-electronics",
    },
    {
        "name": "Ароматизаторы и освежители для дома",
        "url": "https://kaspi.kz/shop/c/home-fragrances/",
        "slug": "home-fragrances",
    },
]


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://retailpool:retailpool@localhost:5432/retailpool",
        description="Async SQLAlchemy connection string for PostgreSQL.",
    )

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for scraper cache.",
    )
    REDIS_CACHE_TTL: int = Field(
        default=3600,
        description="Default TTL in seconds for cached scraper results.",
    )

    # ── Security ──────────────────────────────────────────────────────────
    API_KEY: str = Field(
        default="change-me-in-production",
        description="Static API key for service-to-service auth (MVP).",
    )

    # ── JWT Authentication ────────────────────────────────────────────────
    JWT_SECRET: str = Field(
        default="retailpool-jwt-secret-change-me",
        description="Secret key for signing JWT tokens.",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used for JWT encoding.",
    )
    JWT_EXPIRE_HOURS: int = Field(
        default=24,
        description="JWT token expiration time in hours.",
    )

    # ── Proxy Provider ────────────────────────────────────────────────────
    PROXY_PROVIDER_API_URL: str = Field(
        default="",
        description="Rotating proxy provider API endpoint (e.g. SmartProxy, Bright Data).",
    )
    PROXY_PROVIDER_API_KEY: str = Field(
        default="",
        description="API key for the proxy provider.",
    )
    PROXY_COUNTRY: str = Field(
        default="kz",
        description="Target country code for residential/mobile proxies. Kazakhstan = kz.",
    )
    PROXY_URL: str = Field(
        default="",
        description="Static or provider-side rotating gateway proxy URL (e.g. http://user:pass@host:port).",
    )

    # ── Telegram (for document service payload target) ────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Telegram Bot API token (used by the separate bot worker).",
    )
    TELEGRAM_WEBHOOK_URL: str = Field(
        default="",
        description="Public HTTPS URL for Telegram webhook (production only).",
    )
    BOT_API_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="Base URL of the FastAPI backend for bot API calls.",
    )
    ALERT_CHECK_INTERVAL_MINUTES: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Interval in minutes between alert checks.",
    )

    # ── NKT (National Catalog) API ────────────────────────────────────────
    NKT_API_KEY: str = Field(
        default="",
        description="API key for nationalcatalog.kz (НКТ) — platform-level default.",
    )
    NKT_API_BASE_URL: str = Field(
        default="https://api.nationalcatalog.kz/v1",
        description="Base URL for the НКТ REST API.",
    )

    # ── Success Fee ───────────────────────────────────────────────────────
    SUCCESS_FEE_PERCENT: float = Field(
        default=3.0,
        ge=3.0,
        le=5.0,
        description="Commission percentage (3-5%) charged for organizing a co-buy.",
    )

    # ── Scraper ───────────────────────────────────────────────────────────
    SCRAPER_MIN_DELAY: float = Field(
        default=2.0,
        description="Minimum delay (seconds) between scraper requests.",
    )
    SCRAPER_MAX_DELAY: float = Field(
        default=5.0,
        description="Maximum delay (seconds) between scraper requests.",
    )
    SCRAPER_HEADLESS: bool = Field(
        default=False,
        description="Run Playwright browser in headless mode.",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    # Security check for defaults
    def __init__(self, **data):
        super().__init__(**data)
        defaults_used = []
        if self.API_KEY == "change-me-in-production": defaults_used.append("API_KEY")
        if self.JWT_SECRET == "retailpool-jwt-secret-change-me": defaults_used.append("JWT_SECRET")
        
        if defaults_used:
            import warnings
            warnings.warn(
                f"SECURITY WARNING: You are using default values for {', '.join(defaults_used)}. "
                "This is extremely dangerous in production! Please set them in your .env file."
            )


# Singleton instance
settings = Settings()
