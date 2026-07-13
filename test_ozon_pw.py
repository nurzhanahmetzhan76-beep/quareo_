import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        try:
            await page.goto("https://www.ozon.ru/search/?text=iphone", timeout=15000)
            await page.wait_for_selector(".widget-search-result-container", timeout=5000)
            print("Found search results container!")
            
            # extract some text
            text = await page.locator("div").first.inner_text()
            print("Successfully loaded page.")
        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

asyncio.run(run())
