"""
Quick test: Blue Ocean scan via Kaspi internal JSON API (no Playwright).
"""
import asyncio
import httpx
import json

KASPI_SEARCH_API = "https://kaspi.kz/yml/product-view/pl/filters"
KASPI_OFFER_API = "https://kaspi.kz/yml/offer-view/offers"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-KZ,ru;q=0.9,en-US;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://kaspi.kz/shop/",
    "Origin": "https://kaspi.kz",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

async def main():
    query = "робот пылесос"
    
    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:
        # Step 1: Search
        params = {
            "text": query, "page": 0, "limit": 20,
            "sort": "relevance", "all": "false", "fl": "true", "ui": "d",
            "q": ":availableInZones:Magnum_ZONE1", "i": "-1", "c": "750000000",
        }
        resp = await client.get(KASPI_SEARCH_API, params=params)
        data = resp.json()
        cards = data.get("data", {}).get("cards", [])
        
        results = []
        for card in cards[:5]:  # test first 5
            pid = card.get("id")
            brand = card.get("brand")
            price = card.get("unitPrice")
            rating = card.get("rating")
            reviews = card.get("reviewsQuantity")
            
            # Step 2: Get sellers
            offer_resp = await client.get(f"{KASPI_OFFER_API}/{pid}")
            offers = offer_resp.json().get("offers", [])
            seller = offers[0].get("merchantName") if offers else "Unknown"
            seller_count = len(offers)
            
            results.append({
                "id": pid,
                "brand": brand,
                "price": price,
                "rating": rating,
                "reviews": reviews,
                "buybox_seller": seller,
                "total_sellers": seller_count,
                "title": card.get("title", "")[:50],
            })
    
    with open("blue_ocean_test_result.txt", "w", encoding="utf-8") as f:
        f.write(f"Query: {query}\n")
        f.write(f"Total cards from API: {len(cards)}\n\n")
        for r in results:
            f.write(f"ID={r['id']} | Brand={r['brand']} | Price={r['price']} | Rating={r['rating']} | Reviews={r['reviews']} | Seller={r['buybox_seller']} ({r['total_sellers']} sellers)\n")
            f.write(f"  Title: {r['title']}\n\n")

asyncio.run(main())
