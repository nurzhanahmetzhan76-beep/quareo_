import asyncio
import httpx
from retailpool.scraper.antifraud import StaticProxyProvider

async def main():
    proxy = StaticProxyProvider()
    url = await proxy.get_proxy()
    print("Proxy URL:", url)
    try:
        async with httpx.AsyncClient(proxy=url, timeout=10) as client:
            resp = await client.get("https://api.ipify.org?format=json")
            print("IP:", resp.json())
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
