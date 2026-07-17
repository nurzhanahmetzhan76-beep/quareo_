import asyncio
import logging
from retailpool.scraper.antifraud import StaticProxyProvider
from retailpool.scraper.browser import BrowserManager, _run_in_pw_thread_async
from retailpool.scraper.kaspi_scraper import KaspiScraper

logging.basicConfig(level=logging.INFO)

async def main():
    proxy = StaticProxyProvider()
    async with BrowserManager(proxy_provider=proxy, headless=True) as browser:
        ctx = await browser.new_context()
        scraper = KaspiScraper(context=ctx, redis=None)
        print("Scraping...")
        products, found = await scraper.scrape_search("https://kaspi.kz/shop/search/?text=iphone", "iphone", 5)
        print(f"Found {found} products.")
        print("Closing ctx...")
        await _run_in_pw_thread_async(lambda: ctx.close())
        print("Context closed successfully.")

asyncio.run(main())
