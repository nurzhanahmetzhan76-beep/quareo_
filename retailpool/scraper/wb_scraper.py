import logging
import urllib.parse
import httpx

from retailpool.scraper.antifraud import BaseProxyProvider
from retailpool.schemas.product import WBProductCard

logger = logging.getLogger(__name__)

class WBScraper:
    """
    HTTPX-based scraper for Wildberries using their internal JSON API.
    Bypasses Cloudflare blockades and eliminates Playwright timeout issues.
    """

    def __init__(self, proxy_provider: BaseProxyProvider | None = None) -> None:
        self.proxy_provider = proxy_provider

    async def search(self, query: str, max_items: int = 10) -> list[WBProductCard]:
        """Search for products on Wildberries using JSON API."""
        proxy_url = None
        if self.proxy_provider:
            proxy_url = await self.proxy_provider.get_proxy()

        url = (
            f"https://search.wb.ru/exactmatch/ru/common/v5/search?"
            f"ab_testing=false&appType=128&curr=rub&dest=-1257786&"
            f"query={urllib.parse.quote(query)}&resultset=catalog&"
            f"sort=popular&spp=30&suppressSpellcheck=false"
        )
        
        headers = {
            "Accept": "*/*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://www.wildberries.ru",
            "Referer": "https://www.wildberries.ru/"
        }
        
        client_kwargs = {"headers": headers, "timeout": 20.0}
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        results = []
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(url)
                
                # If proxy is blocked or rate-limited, fallback to direct connection
                if resp.status_code == 429 and proxy_url:
                    logger.warning("WB API returned 429 with proxy, retrying without proxy...")
                    client_kwargs.pop("proxy", None)
                    async with httpx.AsyncClient(**client_kwargs) as direct_client:
                        resp = await direct_client.get(url)

                if resp.status_code != 200:
                    logger.error("WB API returned %d: %s", resp.status_code, resp.text)
                    return []
                    
                data = resp.json()
                # WB API sometimes returns 'data' wrapper, sometimes root wrapper
                products = data.get("data", data).get("products", [])

                for item in products[:max_items]:
                    wb_id = str(item.get("id", ""))
                    title = item.get("name", "")
                    brand = item.get("brand", "")
                    
                    price_kopecks = 0
                    if "sizes" in item and item["sizes"] and "price" in item["sizes"][0]:
                        price_obj = item["sizes"][0]["price"]
                        # 'product' is the discounted price, 'basic' is the original price
                        price_kopecks = price_obj.get("product", price_obj.get("basic", 0))
                    else:
                        price_kopecks = item.get("salePriceU", item.get("priceU", 0))
                        
                    price_rub = price_kopecks / 100.0 if price_kopecks else 0.0
                    
                    if not price_rub:
                        continue
                        
                    price_kzt = price_rub * 5.0
                    rating_val = float(item.get("reviewRating", item.get("rating", 0.0)))
                    feedbacks = item.get("feedbacks", 0)
                    
                    product_url = f"https://www.wildberries.ru/catalog/{wb_id}/detail.aspx"

                    results.append(WBProductCard(
                        wb_id=wb_id,
                        title=title.strip(),
                        brand=brand.strip(),
                        price_rub=price_rub,
                        price_kzt=price_kzt,
                        rating=rating_val,
                        review_count=feedbacks,
                        url=product_url
                    ))

                logger.info("WB Scraped %d products for query '%s' via API", len(results), query)
                return results

        except Exception as e:
            logger.error("Error scraping WB for '%s': %s", query, e)
            return []
