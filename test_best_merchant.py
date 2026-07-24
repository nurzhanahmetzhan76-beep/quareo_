"""
Check bestMerchant values for search results
"""
import asyncio
import httpx
from retailpool.routers.blue_ocean import _kaspi_search, KASPI_HEADERS, KASPI_COOKIES

async def main():
    async with httpx.AsyncClient(headers=KASPI_HEADERS, cookies=KASPI_COOKIES, timeout=20.0) as client:
        cards = await _kaspi_search(client, "робот пылесос", limit=20)
        for card in cards:
            print(f"ID: {card.get('id')} | Brand: {card.get('brand')} | bestMerchant: {card.get('bestMerchant')}")

asyncio.run(main())
