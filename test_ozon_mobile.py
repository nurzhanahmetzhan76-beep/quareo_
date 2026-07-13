import asyncio
import httpx

async def f(): 
    async with httpx.AsyncClient() as c: 
        r = await c.get('https://api.ozon.ru/composer-api.bx/page/json/v2?url=/search/?text=iphone', headers={
            'User-Agent': 'ozonapp_android/16.14.0+2331'
        })
        print(r.status_code)
        if r.status_code == 200:
            print("Length of content:", len(r.content))
        else:
            print(r.text[:200])

asyncio.run(f())
