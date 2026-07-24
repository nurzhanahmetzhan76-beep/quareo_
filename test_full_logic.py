"""
Test exactly what analyze_blue_ocean is getting.
"""
import asyncio
import httpx
from retailpool.routers.blue_ocean import _kaspi_search, _kaspi_get_merchants_from_reviews, KASPI_HEADERS, KASPI_COOKIES
from retailpool.scraper.blue_ocean_logic import analyze_blue_ocean, estimate_sales_from_total_reviews
import json

async def main():
    async with httpx.AsyncClient(headers=KASPI_HEADERS, cookies=KASPI_COOKIES, timeout=20.0) as client:
        cards = await _kaspi_search(client, "робот пылесос", limit=20)
        enriched = []
        for card in cards:
            product_id = str(card.get("id", ""))
            brand = card.get("brand", "")
            price = card.get("unitPrice", 0) or 0
            merchants = await _kaspi_get_merchants_from_reviews(client, product_id)
            
            best_merchant = str(card.get("bestMerchant", ""))
            
            if merchants:
                buybox_seller = merchants[0]
            elif best_merchant:
                buybox_seller = f"Merchant#{best_merchant}"
            else:
                buybox_seller = f"Seller-{product_id}"
            
            enriched.append({
                "kaspi_id": product_id,
                "brand": brand,
                "buybox_seller": buybox_seller,
                "total_sellers": len(merchants) or 1,
                "price": price,
                "estimated_revenue": price * 10, # mock revenue
                "rating": card.get("rating", 0)
            })
            
        analysis = analyze_blue_ocean(enriched)
        
        with open("test_full_logic.json", "w", encoding="utf-8") as f:
            json.dump({"analysis": analysis, "products": enriched}, f, ensure_ascii=False, indent=2)

asyncio.run(main())
