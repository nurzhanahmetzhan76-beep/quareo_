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
            await page.wait_for_timeout(3000)
            with open("ozon.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

asyncio.run(run())
