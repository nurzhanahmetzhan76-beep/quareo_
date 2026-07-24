"""
Blue Ocean Scanner — Niche analysis via Kaspi.kz internal JSON API.

Uses direct HTTP requests to Kaspi's internal /yml/ endpoints instead of
Playwright browser automation. This completely avoids anti-bot detection
since these endpoints are designed for the SPA frontend and return clean JSON.

Endpoints used:
  - /yml/product-view/pl/filters    — search results (brand, price, rating, reviews)
  - /yml/review-view/api/v1/reviews — reviews with merchant names (seller identification)
"""

import logging
import urllib.parse
from typing import Any

from curl_cffi.requests import AsyncSession as CurlSession, RequestsError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.config import settings
from retailpool.database import get_db
from retailpool.models.user import User
from retailpool.services.auth_service import get_optional_user
from retailpool.scraper.blue_ocean_logic import analyze_blue_ocean, estimate_sales_from_total_reviews

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/blue_ocean", tags=["Blue Ocean Scanner"])

# ── Kaspi internal API ───────────────────────────────────────────────────
KASPI_BASE = "https://kaspi.kz"
KASPI_SEARCH_API = f"{KASPI_BASE}/yml/product-view/pl/filters"
KASPI_REVIEW_API = f"{KASPI_BASE}/yml/review-view/api/v1/reviews/product"

# Headers mimicking the Kaspi SPA frontend
KASPI_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-KZ,ru;q=0.9,en-US;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://kaspi.kz/shop/",
    "Origin": "https://kaspi.kz",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

KASPI_COOKIES = {
    "kaspiCity": "750000000",
    "kaspi.store.city": "750000000",
}


class BlueOceanRequest(BaseModel):
    query: str


# ── Kaspi JSON API helpers ───────────────────────────────────────────────

async def _kaspi_search(client: CurlSession, query: str, limit: int = 20) -> list[dict]:
    """
    Call Kaspi internal search API.
    Returns product cards with brand, price, rating, reviewsQuantity, bestMerchant.
    """
    params = {
        "text": query,
        "page": 0,
        "limit": limit,
        "sort": "relevance",
        "all": "false",
        "fl": "true",
        "ui": "d",
        "i": "-1",
        "c": "750000000",
    }

    resp = await client.get(KASPI_SEARCH_API, params=params)
    resp.raise_for_status()
    data = resp.json()

    cards = data.get("data", {}).get("cards", [])
    total = data.get("data", {}).get("total", len(cards))
    logger.info("Kaspi API search '%s': %d cards (total: %d)", query, len(cards), total)
    return cards


async def _kaspi_get_merchants_from_reviews(
    client: CurlSession, product_id: str
) -> list[str]:
    """
    Call Kaspi review API and extract unique merchant names.
    Each review includes the merchant who fulfilled the order.
    This gives us the real list of sellers for a product.
    """
    url = f"{KASPI_REVIEW_API}/{product_id}"
    try:
        resp = await client.get(url, params={
            "filter": "COMMENT",
            "sort": "POPULARITY",
            "limit": 20,
            "withAgg": "true",
        })
        resp.raise_for_status()
        data = resp.json()
        reviews = data.get("data", [])

        merchants = []
        seen = set()
        for rev in reviews:
            m = rev.get("merchant", {})
            name = m.get("name", "")
            if name and name not in seen:
                seen.add(name)
                merchants.append(name)

        return merchants
    except Exception as exc:
        logger.warning("Failed to fetch reviews for %s: %s", product_id, exc)
        return []


# ── Main scan endpoint ───────────────────────────────────────────────────

@router.post("/scan")
async def scan_blue_ocean_niche(
    req: BlueOceanRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    logger.info("Blue Ocean Scan (API mode) for: %s", query)

    enriched_products: list[dict] = []

    try:
        async with CurlSession(
            headers=KASPI_HEADERS,
            cookies=KASPI_COOKIES,
            timeout=25.0,
            impersonate="chrome120",
        ) as client:
            # ── Step 1: Search ────────────────────────────────────────
            cards = await _kaspi_search(client, query, limit=20)

            if not cards:
                logger.warning("Kaspi API returned 0 cards for '%s'", query)
                return {
                    "success": False,
                    "error": "Ничего не найдено на Kaspi по этому запросу.",
                }

            # ── Step 2: Enrich each card with seller data ─────────────
            for card in cards:
                product_id = str(card.get("id", ""))
                title = card.get("title", "")
                brand = card.get("brand", "")
                price = card.get("unitPrice", 0) or 0
                rating = card.get("rating") or 0.0
                review_count = card.get("reviewsQuantity", 0) or 0
                shop_link = card.get("shopLink", "")
                url = f"{KASPI_BASE}{shop_link}" if shop_link else ""
                best_merchant = str(card.get("bestMerchant", ""))

                # Get real merchants from review API
                merchants = await _kaspi_get_merchants_from_reviews(client, product_id)
                total_sellers = len(merchants)

                if merchants:
                    buybox_seller = merchants[0]  # First/most popular = BuyBox
                elif best_merchant:
                    buybox_seller = f"Merchant#{best_merchant}"
                    total_sellers = 1
                else:
                    buybox_seller = f"Seller-{product_id}"
                    total_sellers = 1

                # Estimate revenue
                estimated_sales = estimate_sales_from_total_reviews(review_count)
                estimated_revenue = estimated_sales * price

                enriched_products.append({
                    "kaspi_id": product_id,
                    "title": title,
                    "url": url,
                    "price": price,
                    "rating": rating,
                    "review_count": review_count,
                    "brand": brand,
                    "buybox_seller": buybox_seller,
                    "total_sellers": total_sellers,
                    "estimated_sales": estimated_sales,
                    "estimated_revenue": estimated_revenue,
                })

            logger.info(
                "Enriched %d products for Blue Ocean analysis", len(enriched_products)
            )

        # ── Step 3: Run Math Core ─────────────────────────────────────
        analysis_result = analyze_blue_ocean(enriched_products)
        
        # DEBUG: Save last scan to file so we can inspect it
        try:
            import json
            with open("last_scan_debug.json", "w", encoding="utf-8") as f:
                json.dump({
                    "query": query,
                    "analysis": analysis_result,
                    "products": enriched_products
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return {
            "success": True,
            "query": query,
            "analysis": analysis_result,
            "products": enriched_products,
        }

    except RequestsError as exc:
        logger.error("Kaspi API HTTP error: %s", exc)
        return {
            "success": False,
            "error": f"Kaspi API error: {exc}",
        }
    except Exception as exc:
        logger.error("Blue Ocean scan error: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}
