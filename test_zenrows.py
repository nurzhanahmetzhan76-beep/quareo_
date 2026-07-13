import asyncio
import httpx
import urllib.parse

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
        "proxy_country": "ru"
    }
    
    async with httpx.AsyncClient(timeout=45.0) as c: 
        print("Sending request to ZenRows...")
        r = await c.get(url, params=params)
        print("Status:", r.status_code)
        if r.status_code == 200:
            content = r.text
            if "abt-challenge" in content or "Shield" in content:
                print("BLOCKED by Ozon")
            else:
                print("SUCCESS, length:", len(content))
        else:
            print("Error:", r.text[:200])

asyncio.run(f())
