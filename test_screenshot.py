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
            page.goto("https://kaspi.kz/shop/search/?text=bluetooth+speaker", timeout=45000)
            page.wait_for_timeout(3000)  # Wait for cloudflare/variti to load
            
            # Save screenshot and HTML
            page.screenshot(path="kaspi_block.png")
            with open("kaspi_block.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            
            page.close()

        print("Capturing Kaspi screenshot...")
        await _run_in_pw_thread_async(_capture)
        print("Done! Saved kaspi_block.png and kaspi_block.html")

    await proxy.close()


if __name__ == "__main__":
    asyncio.run(main())
