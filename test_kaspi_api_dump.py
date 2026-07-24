"""
Test: intercept Kaspi.kz internal JSON API and dump full response.
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
            if "json" in ct and ("product-view" in url or "offer-view" in url):
                try:
                    body = await response.json()
                    api_responses[url[:120]] = body
                except:
                    pass
        
        page.on("response", on_response)
        
        await page.goto("https://kaspi.kz/shop/search/?text=кресло", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Now also try the direct product-view search API
        # Based on the intercepted URL pattern
        search_api_url = "https://kaspi.kz/yml/product-view/pl/results?text=кресло&page=0&limit=20&sort=relevance&all=false&fl=true&ui=d&q=:availableInZones:Magnum_ZONE1&i=-1&c=750000000"
        
        await page.goto(search_api_url, wait_until="networkidle", timeout=15000)
        try:
            content = await page.content()
            # Try to parse as JSON (sometimes wrapped in HTML)
            import re
            json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
            if json_match:
                api_responses["direct_search_api"] = json.loads(json_match.group(1))
        except Exception as e:
            api_responses["direct_search_api_error"] = str(e)
        
        with open("kaspi_api_response.json", "w", encoding="utf-8") as f:
            json.dump(api_responses, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"Captured {len(api_responses)} API responses. See kaspi_api_response.json")
        await browser.close()

asyncio.run(main())
