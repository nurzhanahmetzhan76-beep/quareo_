"""Quick test: proxy + Playwright + Kaspi scraping."""
import asyncio
import logging
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./dev.db"
logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

from retailpool.config import settings
from retailpool.scraper.antifraud import StaticProxyProvider
from retailpool.scraper.browser import BrowserManager, _run_in_pw_thread_async
from retailpool.scraper.kaspi_scraper import KaspiScraper


async def main():
    print(f"PROXY_URL: {settings.PROXY_URL[:30]}..." if settings.PROXY_URL else "NO PROXY!")

    proxy = StaticProxyProvider()

    print("\n--- Launching Playwright browser ---")
    try:
        async with BrowserManager(proxy_provider=proxy, headless=False) as browser:
            print("[OK] Browser launched!")
            ctx = await browser.new_context()
            print("[OK] Context created with proxy")

            # Test 1: IP check
            # print("\n--- Test 1: IP check ---")
            # def _check_ip():
            #     page = ctx.new_page()
            #     page.goto("https://ip.decodo.com/json", timeout=30000)
            #     body = page.inner_text("body")
            #     page.close()
            #     return body
            # ip_result = await _run_in_pw_thread_async(_check_ip)
            # print(f"IP: {ip_result[:200]}")

            # Test 2: Kaspi search
            print("\n--- Test 2: Kaspi search ---")
            
            def _get_status():
                page = ctx.new_page()
                resp = page.goto("https://kaspi.kz/shop/search/?text=bluetooth+speaker", timeout=45000)
                status = resp.status if resp else "NO_RESPONSE"
                page.close()
                return status
            
            status = await _run_in_pw_thread_async(_get_status)
            print(f"HTTP Status code from Kaspi: {status}")

            scraper = KaspiScraper(context=ctx, redis=None)
            products = await scraper.scrape_search(
                "https://kaspi.kz/shop/search/?text=bluetooth+speaker",
                query="bluetooth speaker",
                max_products=5,
            )
            print(f"Products found: {len(products)}")
            for p in products[:3]:
                print(f"  - {p.title[:60]} | {p.price_min} tg")

            # Close context in PW thread
            await _run_in_pw_thread_async(lambda: ctx.close())
            print("\n[OK] ALL TESTS PASSED!")

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await proxy.close()


if __name__ == "__main__":
    asyncio.run(main())
