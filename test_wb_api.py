import asyncio
import httpx
import urllib.parse

async def test():
    query = "iPhone 15"
    url = (
        f"https://search.wb.ru/exactmatch/ru/common/v5/search?"
        f"ab_testing=false&appType=128&curr=rub&dest=-1257786&"
        f"query={urllib.parse.quote(query)}&resultset=catalog&"
        f"sort=popular&spp=30&suppressSpellcheck=false"
    )
    headers = {
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "User-Agent": "Wildberries/1.0",
        "Origin": "https://www.wildberries.ru",
    }
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url)
        print("Status:", resp.status_code)
        try:
            data = resp.json()
            products = data.get("data", {}).get("products", [])
            print("Products found:", len(products))
        except Exception as e:
            print("Error parsing JSON:", e)
            print("Body:", resp.text)

if __name__ == "__main__":
    asyncio.run(test())
