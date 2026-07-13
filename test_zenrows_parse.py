import asyncio
import httpx
import urllib.parse
import re
import json

async def f(): 
    zenrows_key = "c6bc7254d563bc03cad885311962fbcdedbf8606"
    query = urllib.parse.quote("iphone")
    ozon_url = f"https://www.ozon.ru/search/?text={query}"
    
    url = "https://api.zenrows.com/v1/"
    params = {
        "url": ozon_url,
        "apikey": zenrows_key,
        "js_render": "true",
        "premium_proxy": "true",
        "proxy_country": "ru",
        "wait_for": ".widget-search-result-container, a[href*='/product/']"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as c: 
        print("Sending request to ZenRows...")
        r = await c.get(url, params=params)
        print("Status:", r.status_code)
        
        if r.status_code == 200:
            content = r.text
            with open("ozon_zenrows.html", "w", encoding="utf-8") as f:
                f.write(content)
            
            # Simple regex to find product data or links
            links = re.findall(r'href="(/product/[^"]+)"', content)
            print("Found links:", len(set(links)))
            
            # Look for JSON state
            match = re.search(r'data-state="({.*?})"', content)
            if match:
                print("Found JSON state data")
            
        else:
            print("Error:", r.text[:200])

asyncio.run(f())
