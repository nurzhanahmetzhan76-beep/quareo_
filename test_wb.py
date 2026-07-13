from dotenv import load_dotenv
load_dotenv()
import asyncio
from retailpool.scraper.wb_scraper import WBScraper
from retailpool.scraper.antifraud import StaticProxyProvider

async def main():
    proxy = StaticProxyProvider()
    scraper = WBScraper(proxy_provider=proxy)
    print("Searching for 'iPhone 15' on WB...")
    results = await scraper.search("iPhone 15", max_items=3)
    print(f"Results len: {len(results)}")
    for r in results:
        print(f"{r.title} - {r.price_rub} RUB (~{r.price_kzt} KZT) - {r.review_count} reviews")

if __name__ == "__main__":
    asyncio.run(main())
