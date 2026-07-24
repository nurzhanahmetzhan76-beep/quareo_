"""
Test: get review data to extract merchant names as seller proxies.
"""
import asyncio
import httpx
import json

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-KZ,ru;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://kaspi.kz/shop/",
    "Origin": "https://kaspi.kz",
}

COOKIES = {"kaspiCity": "750000000", "kaspi.store.city": "750000000"}

async def main():
    product_ids = ["136658828", "124138280", "150419990", "130209647"]
    
    async with httpx.AsyncClient(headers=HEADERS, cookies=COOKIES, timeout=20.0, follow_redirects=True) as client:
        results = []
        for pid in product_ids:
            # Try review API to get merchant names
            review_url = f"https://kaspi.kz/yml/review-view/api/v1/reviews/product/{pid}"
            r = await client.get(review_url, params={
                "filter": "COMMENT", "sort": "POPULARITY", "limit": 20,
                "withAgg": "true"
            })
            
            data = r.json() if r.status_code == 200 else {}
            reviews = data.get("data", [])
            
            # Extract unique merchants from reviews
            merchants = set()
            for rev in reviews:
                m = rev.get("merchant", {})
                if m.get("name"):
                    merchants.add(m["name"])
            
            total_count = data.get("totalCount", 0)
            agg = data.get("aggregations", {})
            
            results.append(f"Product {pid}: status={r.status_code} reviews_in_page={len(reviews)} totalCount={total_count}")
            results.append(f"  Merchants from reviews: {merchants}")
            results.append(f"  Aggregations keys: {list(agg.keys()) if isinstance(agg, dict) else 'N/A'}")
            results.append("")
        
        with open("review_api_test.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(results))

asyncio.run(main())
