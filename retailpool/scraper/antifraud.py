"""
Anti-fraud layer for Kaspi scraping.

Provides:
- Abstract proxy provider + SmartProxy implementation (KZ residential/mobile)
- User-Agent rotation pool
- Rate limiter with randomized delays
- Captcha / block detection helpers
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from random import choice, uniform

import httpx

from retailpool.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# User-Agent Rotation
# ═══════════════════════════════════════════════════════════════════════════

# 20+ realistic desktop & mobile UAs (updated 2025-2026)
_USER_AGENTS: list[str] = [
    # Chrome Desktop (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome Desktop (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox Desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Edge Desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Safari Desktop (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Chrome Mobile (Android)
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    # Safari Mobile (iOS)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/110.0.0.0",
    # Yandex Browser (popular in KZ/CIS)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 YaBrowser/24.6.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 YaBrowser/24.6.0.0 Mobile Safari/537.36",
]


class UserAgentRotator:
    """Returns a random User-Agent string from the pool."""

    def __init__(self, agents: list[str] | None = None) -> None:
        self._agents = agents or _USER_AGENTS

    def get_random(self) -> str:
        return choice(self._agents)


# ═══════════════════════════════════════════════════════════════════════════
# Proxy Provider Abstraction
# ═══════════════════════════════════════════════════════════════════════════


class BaseProxyProvider(ABC):
    """
    Abstract interface for rotating proxy providers.

    IMPORTANT: For Kaspi.kz, proxies MUST be Kazakhstan residential or
    mobile IPs. Datacenter IPs from AWS/DO/Hetzner will be blocked
    immediately by Cloudflare/Variti WAF.
    """

    @abstractmethod
    async def get_proxy(self) -> str | None:
        """
        Return a proxy URL string in format:
            http://user:pass@host:port
        Returns None if no proxy is available.
        """
        ...

    @abstractmethod
    async def report_blocked(self, proxy: str) -> None:
        """Report that a proxy was detected as blocked (for provider feedback)."""
        ...


class SmartProxyProvider(BaseProxyProvider):
    """
    Rotating proxy provider implementation.
    Works with providers that expose an HTTP API for proxy rotation
    (SmartProxy, Bright Data, Proxy-Seller, etc.).

    Configure via environment variables:
        PROXY_PROVIDER_API_URL — endpoint to fetch a proxy
        PROXY_PROVIDER_API_KEY — auth key
        PROXY_COUNTRY — target country (default: kz)
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        country: str | None = None,
    ) -> None:
        self._api_url = api_url or settings.PROXY_PROVIDER_API_URL
        self._api_key = api_key or settings.PROXY_PROVIDER_API_KEY
        self._country = country or settings.PROXY_COUNTRY
        self._client = httpx.AsyncClient(timeout=10.0)

    async def get_proxy(self) -> str | None:
        """
        Fetch a fresh rotating proxy from the provider API.
        Returns None if provider is not configured or request fails.
        """
        if not self._api_url:
            logger.warning(
                "Proxy provider API URL is not configured. Running WITHOUT proxy."
            )
            return None

        try:
            response = await self._client.get(
                self._api_url,
                params={
                    "api_key": self._api_key,
                    "country": self._country,
                    "type": "residential",
                    "format": "url",
                },
            )
            response.raise_for_status()
            proxy_url = response.text.strip()
            logger.debug("Obtained proxy: %s", proxy_url[:30] + "...")
            return proxy_url
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch proxy from provider: %s", exc)
            return None

    async def report_blocked(self, proxy: str) -> None:
        """Notify the provider that a proxy IP was blocked."""
        if not self._api_url:
            return
        try:
            await self._client.post(
                f"{self._api_url}/report",
                json={"proxy": proxy, "reason": "blocked_by_target"},
            )
        except httpx.HTTPError:
            logger.warning("Could not report blocked proxy to provider.")

    async def close(self) -> None:
        await self._client.aclose()


class StaticProxyProvider(BaseProxyProvider):
    """
    Provider for a single static proxy or a provider-side rotating gateway.
    
    Configure via environment variable:
        PROXY_URL — target proxy URL
    """

    def __init__(self, proxy_url: str | None = None) -> None:
        self._proxy_url = proxy_url or settings.PROXY_URL

    async def get_proxy(self) -> str | None:
        """Return the configured proxy URL, or None if not set."""
        if not self._proxy_url:
            logger.warning("Static Proxy URL is not configured. Running WITHOUT proxy.")
            return None
        return self._proxy_url

    async def report_blocked(self, proxy: str) -> None:
        """Cannot report blocks for a static proxy."""
        pass

    async def close(self) -> None:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# Rate Limiter
# ═══════════════════════════════════════════════════════════════════════════


class RateLimiter:
    """
    Async rate limiter with randomized delays between requests.
    Team Lead note: "Don't scrape everything at once — Kaspi will block you fast."
    """

    def __init__(
        self,
        min_delay: float | None = None,
        max_delay: float | None = None,
    ) -> None:
        self._min = min_delay or settings.SCRAPER_MIN_DELAY
        self._max = max_delay or settings.SCRAPER_MAX_DELAY

    async def wait(self) -> None:
        """Sleep for a random duration within the configured range."""
        delay = uniform(self._min, self._max)
        logger.debug("Rate limiter: sleeping %.2f seconds", delay)
        await asyncio.sleep(delay)


# ═══════════════════════════════════════════════════════════════════════════
# Block / Captcha Detection
# ═══════════════════════════════════════════════════════════════════════════

# Signatures that indicate Kaspi/Cloudflare/Variti blocked the request
_BLOCK_SIGNATURES = [
    "cf-challenge",
    "just a moment",
    "variti",
    "ddos protection",
    "cloudflare-nginx",
    "suspicious activity",
]


def is_blocked(page_content: str, status_code: int = 200) -> bool:
    """
    Check if the page response indicates a block or captcha challenge.

    Args:
        page_content: Raw HTML content of the page.
        status_code: HTTP status code (403, 429 are immediate red flags).

    Returns:
        True if the request was likely blocked.
    """
    if status_code in (403, 429, 503):
        return True

    content_lower = page_content.lower()
    for sig in _BLOCK_SIGNATURES:
        if sig in content_lower:
            logger.warning(f"is_blocked triggered by signature: '{sig}'")
            return True
    return False
