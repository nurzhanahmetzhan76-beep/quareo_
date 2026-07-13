import asyncio
from retailpool.scraper.wb_scraper import WBScraper
from retailpool.scraper.antifraud import StaticProxyProvider
from retailpool.config import settings
import logging

logging.basicConfig(level=logging.DEBUG)

async def test():
    provider = StaticProxyProvider() if settings.PROXY_URL else None
    scraper = WBScraper(proxy_provider=provider)
    print("Testing WB Scraper directly...")
    res = await scraper.search("iPhone 15", max_items=5)
    print("Results length:", len(res))
    for p in res:
        print(p.title, p.price_rub)

if __name__ == "__main__":
    asyncio.run(test())
