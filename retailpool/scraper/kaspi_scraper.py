"""
Kaspi.kz scraper — Playwright-based parser for category listings
and individual product cards. Uses Redis caching.

All Playwright calls are dispatched to the dedicated PW worker thread
via _run_in_pw_thread_async from browser.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis
from playwright.sync_api import BrowserContext, Page

from retailpool.config import settings
from retailpool.scraper.antifraud import RateLimiter, is_blocked
from retailpool.scraper.browser import _run_in_pw_thread_async
from retailpool.schemas.product import ProductCard

logger = logging.getLogger(__name__)


class KaspiScraper:
    """
    Scrapes Kaspi category pages and product cards.

    Usage::
        scraper = KaspiScraper(context=ctx, redis=redis)
        products = await scraper.scrape_category("https://kaspi.kz/shop/c/air-humidifiers/")
    """

    def __init__(
        self,
        context: BrowserContext,
        redis: aioredis.Redis | None = None,
        rate_limiter: RateLimiter | None = None,
        cache_ttl: int | None = None,
    ) -> None:
        self._ctx = context
        self._redis = redis
        self._limiter = rate_limiter or RateLimiter()
        self._cache_ttl = cache_ttl or settings.REDIS_CACHE_TTL

    # ── Cache helpers ─────────────────────────────────────────────────
    def _cache_key(self, url: str) -> str:
        h = hashlib.md5(url.encode()).hexdigest()
        return f"kaspi:cache:{h}"

    async def _get_cached(self, url: str) -> Any | None:
        if not self._redis:
            return None
        data = await self._redis.get(self._cache_key(url))
        if data:
            logger.debug("Cache HIT for %s", url)
            return json.loads(data)
        return None

    async def _set_cache(self, url: str, data: Any) -> None:
        if not self._redis:
            return
        await self._redis.setex(
            self._cache_key(url), self._cache_ttl, json.dumps(data, ensure_ascii=False)
        )

    # ── Sync scraping (runs in PW thread) ─────────────────────────────

    @staticmethod
    def _scrape_category_sync(
        ctx: BrowserContext, category_url: str, max_products: int
    ) -> list[dict]:
        """Scrape category listing. MUST run in PW thread."""
        page: Page = ctx.new_page()
        raw_products: list[dict] = []

        try:
            resp = page.goto(category_url, wait_until="domcontentloaded", timeout=30000)

            if resp and is_blocked(page.content(), resp.status):
                logger.warning("BLOCKED on category page: %s", category_url)
                return []

            page.wait_for_selector(
                "[data-product-id], .item-card, .product-card", timeout=10000
            )

            raw_items = page.evaluate("""() => {
                const cards = document.querySelectorAll(
                    '[data-product-id], .item-card, .product-card'
                );
                return Array.from(cards).map(card => {
                    const link = card.querySelector('a[href*="/shop/p/"]');
                    const titleEl = card.querySelector(
                        '.item-card__name, .product-card__title, [data-product-name]'
                    );
                    const priceEl = card.querySelector(
                        '.item-card__prices-price, .product-card__price'
                    );
                    const ratingEl = card.querySelector('.rating, [data-rating]');
                    const reviewEl = card.querySelector(
                        '.item-card__reviews, .product-card__reviews-count'
                    );
                    const href = link ? link.getAttribute('href') : '';
                    const productId = card.getAttribute('data-product-id')
                        || (href.match(/\\/p\\/([^/?]+)/) || [])[1] || '';
                    const text = priceEl ? priceEl.textContent : '0';
                    const match = text.replace(/\\s+/g, '').match(/\\d+/);
                    const priceText = match ? match[0] : '0';
                    return {
                        kaspi_id: productId,
                        title: titleEl ? titleEl.textContent.trim() : '',
                        url: href ? 'https://kaspi.kz' + href : '',
                        price: parseInt(priceText) || 0,
                        rating: ratingEl
                            ? parseFloat(ratingEl.getAttribute('data-rating')
                              || ratingEl.textContent) || null
                            : null,
                        review_count: reviewEl
                            ? parseInt(reviewEl.textContent.replace(/[^\\d]/g, '')) || 0
                            : 0,
                    };
                });
            }""")

            slug = category_url.rstrip("/").split("/")[-1]
            for item in raw_items[:max_products]:
                if not item.get("kaspi_id") or not item.get("title"):
                    continue
                raw_products.append({
                    "kaspi_id": item["kaspi_id"],
                    "title": item["title"],
                    "category_slug": slug,
                    "url": item.get("url", ""),
                    "price_min": item.get("price"),
                    "price_max": item.get("price"),
                    "rating": item.get("rating"),
                    "review_count": item.get("review_count", 0),
                })
            logger.info("Scraped %d products from %s", len(raw_products), slug)

        except Exception as exc:
            logger.error("Error scraping category %s: %s", category_url, exc)
        finally:
            page.close()

        return raw_products

    @staticmethod
    def _scrape_search_sync(
        ctx: BrowserContext, search_url: str, query: str, max_products: int
    ) -> tuple[list[dict], int]:
        """Scrape search results page. MUST run in PW thread."""
        page: Page = ctx.new_page()
        raw_products: list[dict] = []
        total_found = 0

        try:
            logger.info("Navigating to Kaspi search: %s", search_url)
            resp = page.goto(search_url, wait_until="domcontentloaded", timeout=45000)

            if resp and is_blocked(page.content(), resp.status):
                logger.warning("BLOCKED on search page: %s", search_url)
                return [], 0

            # Wait for product cards
            try:
                page.wait_for_selector(
                    ".item-card, .product-card, [data-product-id]", timeout=15000
                )
            except Exception:
                logger.warning("Primary selectors not found, trying alternatives...")
                try:
                    page.wait_for_selector(
                        ".catalog-list .catalog-item, .search-results-list .item",
                        timeout=10000,
                    )
                except Exception:
                    logger.warning("No product cards found on search page")
                    content = page.content()
                    if is_blocked(content, 200):
                        logger.error("Search page appears to be blocked")
                    else:
                        logger.info(
                            "Page loaded but no products found. Content length: %d",
                            len(content),
                        )
                    return [], 0

            result_data = page.evaluate("""() => {
                let cards = document.querySelectorAll('[data-product-id]');
                if (cards.length === 0)
                    cards = document.querySelectorAll('.item-card');
                if (cards.length === 0)
                    cards = document.querySelectorAll(
                        '.catalog-item, .product-card, .search-results-list .item'
                    );

                const items = Array.from(cards).map(card => {
                    const link = card.querySelector('a[href*="/p/"], a[href*="/shop/p/"]')
                        || card.querySelector('a');
                    const titleEl = card.querySelector(
                        '.item-card__name, .product-card__title, '
                        + '[data-product-name], .item-card__name-link'
                    ) || link;
                    const priceEl = card.querySelector(
                        '.item-card__prices-price, .product-card__price, .item-card__price'
                    );
                    const ratingEl = card.querySelector(
                        '.rating, [data-rating], .item-card__rating'
                    );
                    const reviewEl = card.querySelector(
                        '.item-card__reviews, .product-card__reviews-count, '
                        + '.item-card__reviews-count'
                    );
                    const href = link ? link.getAttribute('href') : '';
                    const productId = card.getAttribute('data-product-id')
                        || (href && href.match(/\\/p\\/([^/?]+)/)
                            ? href.match(/\\/p\\/([^/?]+)/)[1] : '') || '';
                    const text = priceEl ? priceEl.textContent : '0';
                    const match = text.replace(/\\s+/g, '').match(/\\d+/);
                    const priceText = match ? match[0] : '0';
                    const title = titleEl ? titleEl.textContent.trim() : '';
                    if (!title || title.length < 3) return null;
                    let fullUrl = '';
                    if (href)
                        fullUrl = href.startsWith('http') ? href : 'https://kaspi.kz' + href;
                    return {
                        kaspi_id: productId
                            || ('search-' + Math.random().toString(36).substr(2, 9)),
                        title: title.substring(0, 200),
                        url: fullUrl,
                        price: parseInt(priceText) || 0,
                        rating: ratingEl
                            ? parseFloat(ratingEl.getAttribute('data-rating')
                              || ratingEl.textContent) || null
                            : null,
                        review_count: reviewEl
                            ? parseInt(reviewEl.textContent.replace(/[^\\d]/g, '')) || 0
                            : 0,
                    };
                }).filter(item => item !== null);

                let totalFound = items.length;
                const titleEl = document.querySelector('.search-result__title, .catalog__title, .search-page__title');
                if (titleEl) {
                    const text = titleEl.textContent.replace(/\\s/g, '');
                    const match = text.match(/(\\d+)/);
                    if (match) {
                        totalFound = parseInt(match[1]);
                    }
                }
                return { items: items, totalFound: totalFound };
            }""")

            raw_items = result_data.get("items", [])
            total_found = result_data.get("totalFound", len(raw_items))

            slug = query.lower().replace(" ", "-")[:64]
            for item in raw_items[:max_products]:
                if not item.get("title"):
                    continue
                raw_products.append({
                    "kaspi_id": item["kaspi_id"] or f"search-{len(raw_products)}",
                    "title": item["title"],
                    "category_slug": slug,
                    "url": item.get("url", ""),
                    "price_min": item.get("price"),
                    "price_max": item.get("price"),
                    "rating": item.get("rating"),
                    "review_count": item.get("review_count", 0),
                })
            logger.info("Scraped %d products from search: %s", len(raw_products), query)

        except Exception as exc:
            logger.error("Error scraping search '%s': %s", query, exc)
            total_found = 0
        finally:
            page.close()

        return raw_products, total_found

    @staticmethod
    def _scrape_product_card_sync(
        ctx: BrowserContext, product_url: str
    ) -> dict[str, Any] | None:
        """Scrape detailed product card. MUST run in PW thread."""
        page: Page = ctx.new_page()
        try:
            resp = page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
            if resp and is_blocked(page.content(), resp.status):
                logger.warning("BLOCKED on product page: %s", product_url)
                return None

            page.wait_for_selector(
                ".product, .item, [data-product-id]", timeout=10000
            )

            return page.evaluate("""() => {
                const gallery = document.querySelectorAll(
                    '.gallery__thumb, .product-gallery img, [data-gallery] img'
                );
                const hasInfographics = document.querySelectorAll(
                    '.infographic, [data-infographic], .badge-overlay'
                ).length > 0;
                const descEl = document.querySelector(
                    '.product__description, [data-product-description], .item__description'
                );
                const sellers = document.querySelectorAll(
                    '.sellers-table__row, .offer-list__item, [data-merchant]'
                );
                const ratingEl = document.querySelector('[data-rating], .rating__value');
                const reviewEl = document.querySelector(
                    '.reviews-count, .product-rating__count'
                );
                return {
                    photo_count: gallery.length,
                    has_infographics: hasInfographics,
                    description_length: descEl ? descEl.textContent.trim().length : 0,
                    seller_count: sellers.length,
                    rating: ratingEl
                        ? parseFloat(ratingEl.getAttribute('data-rating')
                          || ratingEl.textContent) || null : null,
                    review_count: reviewEl
                        ? parseInt(reviewEl.textContent.replace(/[^\\d]/g, '')) || 0 : 0,
                };
            }""")
        except Exception as exc:
            logger.error("Error scraping product %s: %s", product_url, exc)
            return None
        finally:
            page.close()

    @staticmethod
    def _get_seller_count_sync(ctx: BrowserContext, category_url: str) -> int:
        """Count unique sellers. MUST run in PW thread."""
        page: Page = ctx.new_page()
        try:
            page.goto(category_url, wait_until="domcontentloaded", timeout=30000)
            count = page.evaluate("""() => {
                const sellers = document.querySelectorAll(
                    '[data-merchant-id], .item-card__merchant, .seller-name'
                );
                const unique = new Set(
                    Array.from(sellers).map(el =>
                        el.getAttribute('data-merchant-id') || el.textContent.trim()
                    )
                );
                return unique.size;
            }""")
            return count or 0
        except Exception:
            return 0
        finally:
            page.close()

    # ── Async public API ──────────────────────────────────────────────

    async def scrape_category(
        self, category_url: str, max_products: int = 30
    ) -> list[ProductCard]:
        """Scrape product listing from a Kaspi category page."""
        cached = await self._get_cached(category_url)
        if cached:
            return [ProductCard(**item) for item in cached]

        await self._limiter.wait()
        ctx = self._ctx
        raw = await _run_in_pw_thread_async(
            lambda: self._scrape_category_sync(ctx, category_url, max_products)
        )
        products = [ProductCard(**item) for item in raw]
        if products:
            await self._set_cache(
                category_url, [p.model_dump(mode="json") for p in products]
            )
        return products

    async def scrape_search(
        self, search_url: str, query: str, max_products: int = 20
    ) -> tuple[list[ProductCard], int]:
        """Scrape product listing from a Kaspi SEARCH page."""
        cached = await self._get_cached(search_url)
        if cached:
            if isinstance(cached, dict) and "products" in cached:
                return [ProductCard(**item) for item in cached["products"]], cached.get("total_found", len(cached["products"]))
            else:
                return [ProductCard(**item) for item in cached], len(cached)

        await self._limiter.wait()
        ctx = self._ctx
        raw, total_found = await _run_in_pw_thread_async(
            lambda: self._scrape_search_sync(ctx, search_url, query, max_products)
        )
        products = [ProductCard(**item) for item in raw]
        if products:
            await self._set_cache(
                search_url, {"products": [p.model_dump(mode="json") for p in products], "total_found": total_found}
            )
        return products, total_found

    async def scrape_product_card(self, product_url: str) -> dict[str, Any] | None:
        """Scrape detailed product card page."""
        await self._limiter.wait()
        ctx = self._ctx
        return await _run_in_pw_thread_async(
            lambda: self._scrape_product_card_sync(ctx, product_url)
        )

    async def get_seller_count(self, category_url: str) -> int:
        """Count unique sellers on a category listing page."""
        ctx = self._ctx
        return await _run_in_pw_thread_async(
            lambda: self._get_seller_count_sync(ctx, category_url)
        )
