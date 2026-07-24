"""
Test offer-view endpoint with different approaches.
"""
import asyncio
import httpx

PRODUCT_ID = "124138280"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-KZ,ru;q=0.9,en-US;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://kaspi.kz/shop/",
    "Origin": "https://kaspi.kz",
}

COOKIES = {"kaspiCity": "750000000", "kaspi.store.city": "750000000"}

async def main():
    out = []
    
    async with httpx.AsyncClient(headers=HEADERS, cookies=COOKIES, timeout=20.0, follow_redirects=True) as client:
        # Test 1: simple GET
        r1 = await client.get(f"https://kaspi.kz/yml/offer-view/offers/{PRODUCT_ID}")
        out.append(f"GET /offers/ID: status={r1.status_code} body={r1.text[:300]}")
        
        # Test 2: GET with city
        r2 = await client.get(f"https://kaspi.kz/yml/offer-view/offers/{PRODUCT_ID}", params={"cityId": "750000000"})
        out.append(f"GET /offers/ID?cityId: status={r2.status_code} body={r2.text[:300]}")
        
        # Test 3: POST with body
        body = {"cityId": "750000000", "id": PRODUCT_ID, "limit": 20}
        r3 = await client.post("https://kaspi.kz/yml/offer-view/offers", json=body)
        out.append(f"POST /offers: status={r3.status_code} body={r3.text[:300]}")
    
    with open("offer_api_test.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(out))

asyncio.run(main())
