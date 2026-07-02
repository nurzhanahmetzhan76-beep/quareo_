import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="ru-KZ"
        )
        page = await context.new_page()
        print("Navigating to Kaspi search...")
        await page.goto("https://kaspi.kz/shop/search/?text=беспроводные%20наушники&hint_chips_click=false", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000) # wait a bit for dynamic content
        
        # Save search HTML
        search_html = await page.content()
        with open("kaspi_search.html", "w", encoding="utf-8") as f:
            f.write(search_html)
        print("Saved kaspi_search.html")
        
        # Get the first product link
        link = await page.evaluate("() => { const el = document.querySelector('.item-card__name-link, a[href*=\"/shop/p/\"]'); return el ? el.href : null; }")
        
        if link:
            print(f"Navigating to product: {link}")
            await page.goto(link, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            product_html = await page.content()
            with open("kaspi_product.html", "w", encoding="utf-8") as f:
                f.write(product_html)
            print("Saved kaspi_product.html")
        else:
            print("Could not find product link on search page")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
