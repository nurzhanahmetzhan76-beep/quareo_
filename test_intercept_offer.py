import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        intercepted = []
        
        async def on_request(request):
            url = request.url
            if "offer-view" in url:
                intercepted.append({
                    "url": url,
                    "method": request.method,
                    "post_data": request.post_data,
                })
        
        page.on("request", on_request)
        
        await page.goto(
            "https://kaspi.kz/shop/p/igrovoe-kreslo-mizone-ergo-seryi-136658828/?c=750000000",
            wait_until="networkidle",
            timeout=30000,
        )
        await page.wait_for_timeout(5000)
        
        with open("offer_request_intercept.json", "w", encoding="utf-8") as f:
            json.dump(intercepted, f, ensure_ascii=False, indent=2)

        await browser.close()

asyncio.run(main())
