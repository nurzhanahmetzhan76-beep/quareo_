import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1920, "height": 1080}
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = await context.new_page()
        try:
            await page.goto("https://www.ozon.ru/search/?text=iphone", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            content = await page.content()
            if "abt-challenge" in content:
                print("BLOCKED")
            else:
                print("SUCCESS, length:", len(content))
        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

asyncio.run(run())
