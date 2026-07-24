"""
Test Kaspi offer-view API to get sellers for a specific product.
Capture ALL JSON responses from a product page.
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        api_responses = {}
        
        async def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "json" in ct:
                try:
                    body = await response.json()
                    api_responses[url[:200]] = body
                except Exception:
                    pass
        
        page.on("response", on_response)
        
        await page.goto("https://kaspi.kz/shop/p/igrovoe-kreslo-mizone-ergo-seryi-136658828/?c=750000000", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        
        with open("kaspi_product_api.json", "w", encoding="utf-8") as f:
            json.dump(api_responses, f, ensure_ascii=False, indent=2, default=str)
        
        urls = list(api_responses.keys())
        with open("kaspi_product_urls.txt", "w", encoding="utf-8") as f:
            for u in urls:
                f.write(u + "\n")
        
        await browser.close()

asyncio.run(main())
