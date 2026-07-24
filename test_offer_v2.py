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
        r1 = await client.get(f"https://kaspi.kz/yml/offer-view/offers/{PRODUCT_ID}")
        out.append(f"GET /offers/ID: status={r1.status_code} len={len(r1.text)}")
        
        r2 = await client.get(f"https://kaspi.kz/yml/offer-view/offers/{PRODUCT_ID}", params={"cityId": "750000000"})
        out.append(f"GET /offers/ID?cityId: status={r2.status_code} len={len(r2.text)}")
        
        body = {"cityId": "750000000", "id": PRODUCT_ID, "limit": 20}
        r3 = await client.post("https://kaspi.kz/yml/offer-view/offers", json=body)
        out.append(f"POST /offers: status={r3.status_code} len={len(r3.text)}")
        
        # Save last successful response
        best = max([r1, r2, r3], key=lambda r: len(r.text))
        out.append(f"\nBest response body snippet:\n{best.text[:400]}")
    
    with open("offer_api_test.txt", "w", encoding="utf-8") as f:
        for line in out:
            f.write(line + "\n")

asyncio.run(main())
