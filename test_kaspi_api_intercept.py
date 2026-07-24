"""
Test: intercept Kaspi.kz XHR/fetch calls to find internal API endpoints.
"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        api_calls = []
        
        def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "json" in ct or "yml" in url or "api" in url:
                api_calls.append({
                    "url": url[:200],
                    "status": response.status,
                    "content_type": ct[:50],
                })
        
        page.on("response", on_response)
        
        await page.goto("https://kaspi.kz/shop/search/?text=кресло", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        
        with open("kaspi_api_calls.txt", "w", encoding="utf-8") as f:
            for call in api_calls:
                f.write(f"{call['status']} | {call['content_type']} | {call['url']}\n")
            f.write(f"\nTotal API calls: {len(api_calls)}\n")
        
        print(f"Captured {len(api_calls)} API/JSON calls. See kaspi_api_calls.txt")
        await browser.close()

asyncio.run(main())
