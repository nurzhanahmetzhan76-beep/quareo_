import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://kaspi.kz/shop/search/?text=iphone', wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        print("Looking for products...")
        # Kaspi usually has a grid of products. Let's find links that go to /shop/p/
        links = soup.find_all('a', href=lambda href: href and '/shop/p/' in href)
        
        seen_classes = set()
        for link in links:
            # Let's find the parent container of the link that might be a product card
            parent = link.parent
            for _ in range(3): # Go up a few levels
                if parent:
                    if parent.get('class'):
                        seen_classes.add(' '.join(parent.get('class')))
                    if parent.get('data-product-id'):
                        seen_classes.add('HAS_DATA_PRODUCT_ID: ' + parent.get('data-product-id'))
                    parent = parent.parent
        
        print("Possible product card classes:", seen_classes)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
