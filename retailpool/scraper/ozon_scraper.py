"""
Ozon scraper — ZenRows API based parser for search results.
"""

from __future__ import annotations

import logging
import urllib.parse
import re
import httpx

from retailpool.scraper.antifraud import RateLimiter

logger = logging.getLogger(__name__)

class OzonScraper:
    def __init__(
        self,
        api_key: str,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._api_key = api_key
        self._limiter = rate_limiter or RateLimiter()

    async def scrape_search(
        self, query: str, max_products: int = 15
    ) -> tuple[list[dict], int]:
        """Scrape search results page on Ozon via ZenRows."""
        await self._limiter.wait()
        
        raw_products = []
        total_found = 0

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.ozon.ru/search/?text={encoded_query}"

        # ZenRows API settings
        api_url = "https://api.zenrows.com/v1/"
        params = {
            "url": search_url,
            "apikey": self._api_key,
            "js_render": "true",
            "antibot": "true",
            "proxy_country": "ru",
            # We wait for the products container to render
            "wait_for": ".widget-search-result-container, a[href*='/product/']"
        }

        try:
            logger.info("Requesting Ozon search via ZenRows: %s", search_url)
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(api_url, params=params)
                
            if resp.status_code != 200:
                logger.error("ZenRows returned %s: %s", resp.status_code, resp.text[:200])
                return [], 0
                
            content = resp.text
            if "abt-challenge" in content or "Shield" in content:
                logger.warning("BLOCKED on Ozon search page despite ZenRows")
                return [], 0

            # Find all product links
            links = re.findall(r'href="(/product/[^"]+)"', content)
            unique_links = list(dict.fromkeys(links))  # Deduplicate while preserving order
            
            # Simple heuristic parser (MVP)
            for link in unique_links[:max_products]:
                id_match = re.search(r'-(\d+)/?$', link)
                ozon_id = id_match.group(1) if id_match else f"ozon-{len(raw_products)}"
                
                raw_products.append({
                    "kaspi_id": ozon_id,
                    "title": f"Товар Ozon ({ozon_id})", # In full version we extract from JSON
                    "url": f"https://www.ozon.ru{link}",
                    "price_rub": 1000, # In full version we extract from JSON
                    "rating": 4.5,
                    "review_count": 100,
                })
                
            total_found = len(unique_links) * 10 if unique_links else 0
            logger.info("Scraped %d products from Ozon via ZenRows", len(raw_products))

        except Exception as exc:
            logger.error("Error scraping Ozon via ZenRows '%s': %s", query, exc)
            total_found = 0

        return raw_products, total_found
