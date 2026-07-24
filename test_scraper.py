import asyncio
from retailpool.scraper.browser import BrowserManager
from retailpool.scraper.kaspi_scraper import KaspiScraper

async def test():
    async with BrowserManager() as browser:
        ctx = await browser.new_context()
        scraper = KaspiScraper(context=ctx)
        
        print("Scraping search...")
        cards, total = await scraper.scrape_search("https://kaspi.kz/shop/search/?text=кресло&hint_chips_click=false", "кресло", 5)
        print(f"Found {len(cards)} cards")
        
        if cards:
            for c in cards:
                print(f"Product: {c.title} | {c.url}")
                if c.url:
                    print("Scraping details...")
                    detail = await scraper.scrape_product_card(c.url)
                    print(f"Detail: {detail}")

if __name__ == "__main__":
    asyncio.run(test())
