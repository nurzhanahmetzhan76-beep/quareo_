import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to Kaspi...")
        response = await page.goto('https://kaspi.kz/shop/search/?text=iphone', wait_until='networkidle')
        print(f"Status: {response.status if response else 'None'}")
        await page.wait_for_timeout(3000)
        
        # Take a screenshot
        await page.screenshot(path='kaspi_test_screenshot.png')
        print("Screenshot saved to kaspi_test_screenshot.png")
        
        # Print some HTML to see what's there
        html = await page.content()
        print(f"HTML length: {len(html)}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
