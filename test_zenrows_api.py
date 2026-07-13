import asyncio
import httpx
import urllib.parse
import json

async def f(): 
    zenrows_key = "c6bc7254d563bc03cad885311962fbcdedbf8606"
    query = urllib.parse.quote("iphone")
    ozon_url = f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/search/?text={query}"
    
    url = "https://api.zenrows.com/v1/"
    params = {
        "url": ozon_url,
        "apikey": zenrows_key,
        "premium_proxy": "true",
        "proxy_country": "ru"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as c: 
        print("Sending request to ZenRows JSON API...")
        r = await c.get(url, params=params)
        print("Status:", r.status_code)
        
        if r.status_code == 200:
            content = r.text
            print("Response length:", len(content))
            with open("ozon_zenrows_api.json", "w", encoding="utf-8") as f_out:
                f_out.write(content)
        else:
            print("Error:", r.text[:200])

asyncio.run(f())
