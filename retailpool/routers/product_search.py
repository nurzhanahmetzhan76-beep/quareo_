"""
Quareo Search — real cross-marketplace product search.

Aggregates REAL data from Kaspi.kz, Wildberries and Ozon (ozon.kz).
All three scrapers genuinely extract title/price from the page — no
placeholder data. Ozon requires ZENROWS_API_KEY to be set; if it's
missing, Ozon results are silently skipped rather than faked.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse

from fastapi import APIRouter, Query

from retailpool.config import settings
from retailpool.scraper.antifraud import SmartProxyProvider, StaticProxyProvider
from retailpool.scraper.browser import BrowserManager
from retailpool.scraper.kaspi_scraper import KaspiScraper
from retailpool.scraper.ozon_scraper import OzonScraper
from retailpool.scraper.wb_scraper import WBScraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Quareo Search"])

# Same fixed RUB→KZT rate already used by the WB scraper, kept consistent.
RUB_TO_KZT = 5.0


def _get_proxy_provider():
    if settings.PROXY_URL:
        return StaticProxyProvider()
    return SmartProxyProvider()


async def _search_kaspi(query: str, max_items: int) -> list[dict]:
    """Real Kaspi search — genuinely scrapes title/price from the page."""
    try:
        proxy_provider = _get_proxy_provider()
        async with BrowserManager(proxy_provider=proxy_provider) as browser:
            ctx = await browser.new_context()
            scraper = KaspiScraper(context=ctx, redis=None)
            search_url = f"https://kaspi.kz/shop/search/?text={urllib.parse.quote(query)}"
            products, _total = await scraper.scrape_search(search_url, query, max_products=max_items)

        offers = []
        for p in products:
            price = p.price_min or p.price_max
            if not price:
                continue
            offers.append({
                "marketplace": "Kaspi",
                "title": p.title,
                "url": p.url,
                "price_kzt": price,
                "rating": p.rating,
                "review_count": p.review_count,
                "seller": p.seller_name,
            })
        return offers
    except Exception as exc:
        logger.error("Quareo Search: Kaspi lookup failed for '%s': %s", query, exc)
        return []


async def _search_wb(query: str, max_items: int) -> list[dict]:
    """Real Wildberries search — genuinely scrapes title/price from the page."""
    try:
        scraper = WBScraper()
        products = await scraper.search(query, max_items=max_items)

        offers = []
        for p in products:
            if not p.price_kzt:
                continue
            offers.append({
                "marketplace": "Wildberries",
                "title": p.title,
                "url": p.url,
                "price_kzt": p.price_kzt,
                "rating": p.rating,
                "review_count": p.review_count,
                "seller": p.brand,
            })
        return offers
    except Exception as exc:
        logger.error("Quareo Search: WB lookup failed for '%s': %s", query, exc)
        return []


async def _search_ozon(query: str, max_items: int) -> list[dict]:
    """Real Ozon (ozon.kz) search via ZenRows — genuinely scrapes title/price."""
    if not settings.ZENROWS_API_KEY:
        logger.info("Quareo Search: ZENROWS_API_KEY not set, skipping Ozon.")
        return []
    try:
        scraper = OzonScraper(api_key=settings.ZENROWS_API_KEY)
        products, _total = await scraper.scrape_search(query, max_products=max_items)

        offers = []
        for p in products:
            if not p.get("price_kzt"):
                continue
            offers.append({
                "marketplace": "Ozon",
                "title": p["title"],
                "url": p["url"],
                "price_kzt": p["price_kzt"],
                "rating": p.get("rating"),
                "review_count": p.get("review_count"),
                "seller": None,
            })
        return offers
    except Exception as exc:
        logger.error("Quareo Search: Ozon lookup failed for '%s': %s", query, exc)
        return []


@router.get("", summary="Search a product across live marketplaces")
async def search_products(
    query: str = Query(..., min_length=2, max_length=200),
    max_items: int = Query(default=8, ge=1, le=20),
):
    """
    Real-time search across Kaspi.kz, Wildberries and Ozon (ozon.kz).

    Avito, OLX, Alibaba, 1688, Taobao, AliExpress are not yet connected —
    those need real scraping work verified against actual pages, same as
    Ozon was. We only show marketplaces where the data is genuinely
    scraped, not placeholders.
    """
    kaspi_task = _search_kaspi(query, max_items)
    wb_task = _search_wb(query, max_items)
    ozon_task = _search_ozon(query, max_items)

    kaspi_offers, wb_offers, ozon_offers = await asyncio.gather(kaspi_task, wb_task, ozon_task)
    offers = kaspi_offers + wb_offers + ozon_offers

    sources_checked = ["Kaspi", "Wildberries"]
    if settings.ZENROWS_API_KEY:
        sources_checked.append("Ozon")

    if not offers:
        return {
            "query": query,
            "offers": [],
            "sources_checked": sources_checked,
            "message": "Ничего не найдено. Попробуйте другой запрос.",
        }

    offers.sort(key=lambda o: o["price_kzt"])
    for i, o in enumerate(offers):
        o["best"] = (i == 0)

    return {
        "query": query,
        "offers": offers,
        "sources_checked": sources_checked,
        "coming_soon": ["Avito", "OLX", "Alibaba", "1688", "Taobao", "AliExpress"],
    }
