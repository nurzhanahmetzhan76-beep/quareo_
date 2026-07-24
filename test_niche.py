import asyncio
from curl_cffi.requests import AsyncSession
from retailpool.scraper.blue_ocean_logic import analyze_blue_ocean, estimate_sales_from_total_reviews

async def test_niche(query):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://kaspi.kz/shop/',
        'Origin': 'https://kaspi.kz',
    }
    async with AsyncSession(impersonate='chrome120') as client:
        r = await client.get(f'https://kaspi.kz/yml/product-view/pl/filters?text={query}&c=750000000', headers=headers)
        if r.status_code != 200: return False
        cards = r.json().get('data', {}).get('cards', [])
        
        enriched = []
        for card in cards:
            brand = card.get('brand', '')
            price = card.get('unitPrice', 0)
            rating = card.get('rating', 0)
            reviews = card.get('reviewsQuantity', 0)
            
            url = f'https://kaspi.kz/yml/review-view/api/v1/reviews/product/{card.get("id")}'
            try:
                rr = await client.get(url, params={'filter': 'COMMENT', 'sort': 'POPULARITY', 'limit': 10, 'withAgg': 'true'})
                merchants = [m.get('merchant', {}).get('name', '') for m in rr.json().get('data', [])]
                merchants = list(set([m for m in merchants if m]))
            except:
                merchants = []
                
            buybox = merchants[0] if merchants else 'Unknown'
            total_sellers = len(merchants) or 1
            est_sales = estimate_sales_from_total_reviews(reviews)
            
            enriched.append({
                'brand': brand,
                'buybox_seller': buybox,
                'total_sellers': total_sellers,
                'estimated_revenue': est_sales * price,
                'rating': rating,
                'title': card.get('title')
            })
            
        analysis = analyze_blue_ocean(enriched)
        
        score = 85
        if analysis.get('is_red_ocean'): score = 25
        elif analysis.get('is_stm_red_ocean') or analysis.get('is_oligopoly_red_ocean'): score = 45
        
        print(f'{query}: Score {score}, STM {analysis.get("stm_share")}, Top3 {analysis.get("concentration", {}).get("top_3_share")}')

async def run_all():
    for q in ['чехол iphone 13', 'держатель для телефона в машину', 'гусь обнимусь', 'органайзер для косметики', 'коврик для мыши', 'органайзер для кухни']:
        await test_niche(q)

asyncio.run(run_all())
