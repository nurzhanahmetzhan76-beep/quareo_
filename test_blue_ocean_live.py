import asyncio
from retailpool.scraper.browser import BrowserManager
from retailpool.scraper.kaspi_scraper import KaspiScraper
from retailpool.scraper.blue_ocean_logic import analyze_blue_ocean, estimate_sales_from_total_reviews

async def test():
    query = "кресло"
    async with BrowserManager() as browser:
        ctx = await browser.new_context()
        scraper = KaspiScraper(context=ctx)
        
        cards, total = await scraper.scrape_search(f"https://kaspi.kz/shop/search/?text={query}", query, 5)
        print(f"Found {len(cards)} cards")
        
        enriched = []
        if cards:
            for p in cards:
                detail = await scraper.scrape_product_card(p.url)
                
                brand = detail.get("brand", "") if detail else ""
                buybox_seller = detail.get("buybox_seller", "") if detail else ""
                review_count = detail.get("review_count", 0) if detail else 0
                rating = detail.get("rating", 0.0) if detail else 0.0
                
                if not review_count and hasattr(p, 'review_count') and p.review_count:
                    review_count = p.review_count
                if not rating and hasattr(p, 'rating') and p.rating:
                    rating = p.rating
                if not brand:
                    parts = p.title.split(' ')
                    brand = parts[1] if len(parts) > 1 and len(parts[1]) > 2 else "Unknown"
                if not buybox_seller:
                    buybox_seller = "Скрытый продавец"
                    
                estimated_sales = estimate_sales_from_total_reviews(review_count)
                estimated_revenue = estimated_sales * (p.price_min or 0)
                
                print(f"Product: {p.title[:30]}... | Seller: {buybox_seller} | Brand: {brand} | Rev: {estimated_revenue}")
                enriched.append({
                    "title": p.title,
                    "price": p.price_min,
                    "rating": rating,
                    "review_count": review_count,
                    "brand": brand,
                    "buybox_seller": buybox_seller,
                    "total_sellers": detail.get("seller_count", 1) if detail else 1,
                    "estimated_revenue": estimated_revenue,
                })
        print("\nAnalysis:", analyze_blue_ocean(enriched))

if __name__ == "__main__":
    asyncio.run(test())
