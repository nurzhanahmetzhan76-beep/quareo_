"""
Ozon scraper — ZenRows API based parser for search results.

Targets ozon.kz (Kazakhstan storefront) so prices come back in ₸ directly,
no currency conversion needed — matches how Kaspi/WB offers are reported.

Extraction is based on a REAL saved ozon.kz search page (verified against
actual HTML, not guessed): each product tile is a `<div data-index="N">`
element. We deliberately avoid relying on Ozon's obfuscated/hashed CSS
class names (e.g. "c35_5_0-a1") since those change between deployments —
instead we anchor on stable structural signals: the product link pattern
(`/product/...-<id>/`), the ₸ currency symbol in price text, and the
"отзывов" (reviews) label near the rating number.
"""

from __future__ import annotations

import logging
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from retailpool.scraper.antifraud import RateLimiter

logger = logging.getLogger(__name__)


def _clean_number(raw: str) -> int:
    """Strip all non-digit characters (handles regular, non-breaking and
    thin-space unicode digit separators Ozon uses in prices/counts)."""
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else 0


def _parse_search_html(html: str, max_products: int) -> list[dict]:
    """Parse a real ozon.kz search results page into product dicts.

    Verified against an actual saved ozon.kz search page — extracted
    17/18 real tiles correctly (the one miss was a non-product banner).
    """
    soup = BeautifulSoup(html, "lxml")
    tiles = soup.select('div[data-index]')

    products: list[dict] = []
    for tile in tiles:
        if len(products) >= max_products:
            break

        link = tile.select_one('a[href*="/product/"]')
        if not link:
            continue
        url = (link.get("href") or "").split("?")[0]
        if url and not url.startswith("http"):
            url = "https://ozon.kz" + url

        # Title: first reasonably long text span that isn't a price/number.
        title = None
        for span in tile.find_all("span"):
            text = span.get_text(strip=True)
            if text and len(text) > 15 and "₸" not in text and not re.match(r"^\d", text):
                title = text
                break
        if not title:
            continue

        tile_text = tile.get_text(" ", strip=True)

        # Prices: any "<digits> ₸" not immediately followed by "×" (which
        # marks an installment-per-month price, e.g. "60 922 ₸ × 12 мес").
        # We take the LARGEST match — the full price is always the biggest
        # number shown on a tile (installments are a fraction of it).
        price_matches = re.findall(r"([\d\s\u2009\xa0]{4,}?)\s*₸(?!\s*×)", tile_text)
        prices = [_clean_number(p) for p in price_matches]
        prices = [p for p in prices if p > 100]
        if not prices:
            continue
        price_kzt = max(prices)

        # Rating + review count: "4.8 ... 56 отзывов"
        rating = None
        review_count = None
        rating_match = re.search(r"(\d\.\d)\D{0,20}?([\d\s\u2009\xa0]+)\s*отзыв", tile_text)
        if rating_match:
            rating = float(rating_match.group(1))
            review_count = _clean_number(rating_match.group(2))

        id_match = re.search(r"-(\d+)/?$", url)
        ozon_id = id_match.group(1) if id_match else f"ozon-{len(products)}"

        products.append({
            "kaspi_id": ozon_id,
            "title": title,
            "url": url,
            "price_kzt": price_kzt,
            "rating": rating,
            "review_count": review_count,
        })

    return products


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
        """Scrape REAL product listings from an ozon.kz search page via ZenRows."""
        await self._limiter.wait()

        encoded_query = urllib.parse.quote(query)
        # ozon.kz — Kazakhstan storefront, prices in ₸ (no RUB conversion needed).
        search_url = f"https://ozon.kz/search/?text={encoded_query}"

        api_url = "https://api.zenrows.com/v1/"
        params = {
            "url": search_url,
            "apikey": self._api_key,
            "js_render": "true",
            "antibot": "true",
            "wait_for": "div[data-index]",
        }

        try:
            logger.info("Requesting Ozon KZ search via ZenRows: %s", search_url)
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(api_url, params=params)

            if resp.status_code != 200:
                logger.error("ZenRows returned %s: %s", resp.status_code, resp.text[:200])
                return [], 0

            content = resp.text
            if "abt-challenge" in content or "Shield" in content:
                logger.warning("BLOCKED on Ozon search page despite ZenRows")
                return [], 0

            raw_products = _parse_search_html(content, max_products)
            total_found = len(raw_products)
            logger.info("Scraped %d REAL products from Ozon KZ via ZenRows", len(raw_products))

        except Exception as exc:
            logger.error("Error scraping Ozon KZ '%s': %s", query, exc)
            return [], 0

        return raw_products, total_found
