import httpx
import asyncio

async def test():
    url = "https://search.wb.ru/exactmatch/ru/common/v5/search?appType=128&curr=rub&dest=-1257786&query=iPhone%2015&resultset=catalog&sort=popular"
    params = {
        "url": url,
        "apikey": "c6bc7254d563bc03cad885311962fbcdedbf8606",
        "premium_proxy": "true",
        "proxy_country": "ru"
    }
    r = await httpx.AsyncClient(timeout=30.0).get("https://api.zenrows.com/v1/", params=params)
    print(r.status_code)
    print(r.text[:200])

asyncio.run(test())
