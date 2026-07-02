"""
Playwright Browser Manager for Kaspi scraping.

Uses Playwright's SYNC API in a single dedicated thread.
All Playwright objects (browser, contexts, pages) are bound to
the greenlet in that thread; we dispatch ALL Playwright work there.

Python 3.14 / Windows compatible.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse, unquote
from concurrent.futures import Future
import threading
from types import TracebackType
from typing import Any, Callable, TypeVar

from playwright.sync_api import (
    sync_playwright, Browser, BrowserContext, Playwright,
)

from retailpool.config import settings
from retailpool.scraper.antifraud import BaseProxyProvider, UserAgentRotator

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ── Single dedicated Playwright thread ────────────────────────────────────
# All Playwright sync calls MUST run in this thread to satisfy greenlet.

_pw_thread: threading.Thread | None = None
_pw_lock = threading.Lock()
_task_queue: list | None = None  # will be a queue.Queue

_global_playwright: Playwright | None = None
_global_browser: Browser | None = None


def _ensure_pw_thread() -> None:
    """Start the Playwright worker thread (once)."""
    import queue as _queue_mod
    global _pw_thread, _task_queue
    with _pw_lock:
        if _pw_thread is not None and _pw_thread.is_alive():
            return
        _task_queue = _queue_mod.Queue()

        def _worker():
            while True:
                item = _task_queue.get()
                if item is None:
                    break
                func, future = item
                try:
                    result = func()
                    future.set_result(result)
                except Exception as exc:
                    future.set_exception(exc)

        _pw_thread = threading.Thread(target=_worker, daemon=True, name="playwright-worker")
        _pw_thread.start()
        logger.info("Playwright worker thread started")


def _run_in_pw_thread(func: Callable[[], T]) -> T:
    """Submit a callable to the Playwright thread and block for result."""
    _ensure_pw_thread()
    future: Future[T] = Future()
    _task_queue.put((func, future))
    return future.result(timeout=180)


async def _run_in_pw_thread_async(func: Callable[[], T]) -> T:
    """Async wrapper: run a callable in the Playwright thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_in_pw_thread, func)


class BrowserManager:
    """Manages Playwright Chromium browser + stealth contexts.

    All Playwright operations run in a single dedicated thread.
    """

    def __init__(
        self,
        proxy_provider: BaseProxyProvider | None = None,
        ua_rotator: UserAgentRotator | None = None,
        headless: bool | None = None,
    ) -> None:
        self._proxy_provider = proxy_provider
        self._ua_rotator = ua_rotator or UserAgentRotator()
        self._headless = headless if headless is not None else settings.SCRAPER_HEADLESS
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def _launch_sync(self) -> None:
        """Launch Playwright and Chromium if not already launched. MUST run in PW thread."""
        global _global_playwright, _global_browser
        if _global_playwright is None:
            _global_playwright = sync_playwright().start()
            logger.info("Playwright global instance started")
        
        if _global_browser is None:
            _global_browser = _global_playwright.chromium.launch(
                headless=self._headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            logger.info("Browser launched (headless=%s)", self._headless)

        self._browser = _global_browser

    def _shutdown_sync(self) -> None:
        """Do nothing on shutdown; we keep the browser alive globally."""
        pass

    def _create_context_sync(self, proxy_url: str | None = None) -> BrowserContext:
        """Create a stealth browser context. MUST run in PW thread."""
        assert self._browser is not None, "Browser not launched"

        ua = self._ua_rotator.get_random()
        kwargs: dict = {
            "user_agent": ua,
            "locale": "ru-KZ",
            "timezone_id": "Asia/Almaty",
            "viewport": {"width": 1920, "height": 1080},
            "java_script_enabled": True,
            "ignore_https_errors": True,
            "extra_http_headers": {
                "Accept-Language": "ru-KZ,ru;q=0.9,en-US;q=0.8",
                "DNT": "1",
            },
        }

        if proxy_url:
            parsed = urlparse(proxy_url)
            proxy_cfg: dict = {
                "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            }
            if parsed.username:
                proxy_cfg["username"] = unquote(parsed.username)
            if parsed.password:
                proxy_cfg["password"] = unquote(parsed.password)
            kwargs["proxy"] = proxy_cfg
            logger.info("Proxy configured: %s:%s", parsed.hostname, parsed.port)

        ctx = self._browser.new_context(**kwargs)

        # Mask navigator.webdriver
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        return ctx

    # ── Async interface ──────────────────────────────────────────────

    async def __aenter__(self) -> BrowserManager:
        await _run_in_pw_thread_async(self._launch_sync)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await _run_in_pw_thread_async(self._shutdown_sync)

    async def new_context(self) -> BrowserContext:
        """Create stealth context with KZ locale, proxy, rotated UA."""
        proxy_url: str | None = None
        if self._proxy_provider:
            proxy_url = await self._proxy_provider.get_proxy()

        return await _run_in_pw_thread_async(
            lambda: self._create_context_sync(proxy_url)
        )
