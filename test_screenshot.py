"""Capture screenshot of the Kaspi block."""
import asyncio
import logging
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./dev.db"
logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

from retailpool.config import settings
from retailpool.scraper.antifraud import StaticProxyProvider
from retailpool.scraper.browser import BrowserManager, _run_in_pw_thread_async


async def main():
    proxy = StaticProxyProvider()

    async with BrowserManager(proxy_provider=proxy, headless=True) as browser:
        ctx = await browser.new_context()

        def _capture():
            page = ctx.new_page()
            # iPhone 13 128GB
            page.goto("https://kaspi.kz/shop/p/item-102298404/", timeout=45000)
            page.wait_for_timeout(3000)
            
            # Click "Все продавцы"
            try:
                sellers_tab = page.locator(
                    'a[data-tab="sellers"], '
                    'button:has-text("продавц"), '
                    'a:has-text("продавц")'
                ).first
                if sellers_tab.is_visible(timeout=3000):
                    sellers_tab.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass
            
            page.screenshot(path="kaspi_repricer_debug.png", full_page=True)
            with open("kaspi_repricer_debug.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            
            page.close()

        print("Capturing Kaspi screenshot...")
        await _run_in_pw_thread_async(_capture)
        print("Done! Saved kaspi_block.png and kaspi_block.html")

    await proxy.close()


if __name__ == "__main__":
    asyncio.run(main())
