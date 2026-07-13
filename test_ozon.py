import asyncio
import httpx

async def f(): 
    async with httpx.AsyncClient() as c: 
        r = await c.get('https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/search/?text=iphone', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        })
        print(r.status_code)
        if r.status_code == 200:
            print("Length of content:", len(r.content))
        else:
            print(r.text[:200])

asyncio.run(f())
