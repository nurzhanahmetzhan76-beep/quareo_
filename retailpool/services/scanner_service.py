"""
Scanner Service — orchestrates Playwright scraping and niche analysis.
Coordinates between BrowserManager, KaspiScraper, and NicheAnalyzer,
then persists results to the database.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.config import settings, TARGET_CATEGORIES
from retailpool.models.product import Product, NicheAnalysis
from retailpool.schemas.product import CategoryScanResult, ProductCard
from retailpool.scraper.antifraud import SmartProxyProvider, StaticProxyProvider
from retailpool.scraper.browser import BrowserManager
from retailpool.scraper.kaspi_scraper import KaspiScraper
from retailpool.scraper.niche_analyzer import NicheAnalyzer, NicheResult

logger = logging.getLogger(__name__)


class ScannerService:
    """
    High-level orchestrator for the Kaspi niche scanning pipeline.

    Flow:
      1. Launch Playwright browser with stealth settings
      2. For each target category → scrape listings + card details
      3. Run niche analysis (monopolization + visual weakness)
      4. Persist results to database (PostgreSQL or SQLite)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._analyzer = NicheAnalyzer()

    async def scan_all_categories(self) -> list[CategoryScanResult]:
        """Run full scan across all configured target categories."""
        results: list[CategoryScanResult] = []
        if settings.PROXY_URL:
            proxy_provider = StaticProxyProvider()
        else:
            proxy_provider = SmartProxyProvider()

        try:
            redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            logger.warning("Redis unavailable — running without cache")
            redis = None

        try:
            async with BrowserManager(proxy_provider=proxy_provider) as browser:
                ctx = await browser.new_context()
                scraper = KaspiScraper(context=ctx, redis=redis)

                for cat in TARGET_CATEGORIES:
                    try:
                        result = await self._scan_category(
                            scraper, cat["url"], cat["slug"], cat["name"]
                        )
                        results.append(result)
                    except Exception as exc:
                        logger.error(
                            "Failed to scan category %s: %s", cat["slug"], exc
                        )
                        continue

                await ctx.close()
        finally:
            await proxy_provider.close()
            if redis:
                await redis.aclose()

        return results

    async def scan_single_category(
        self, category_url: str, slug: str, name: str
    ) -> CategoryScanResult:
        """Scan a single category on demand."""
        if settings.PROXY_URL:
            proxy_provider = StaticProxyProvider()
        else:
            proxy_provider = SmartProxyProvider()

        try:
            redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            redis = None

        try:
            async with BrowserManager(proxy_provider=proxy_provider) as browser:
                ctx = await browser.new_context()
                scraper = KaspiScraper(context=ctx, redis=redis)
                result = await self._scan_category(scraper, category_url, slug, name)
                await ctx.close()
        finally:
            await proxy_provider.close()
            if redis:
                await redis.aclose()

        return result

    async def _scan_category(
        self,
        scraper: KaspiScraper,
        url: str,
        slug: str,
        name: str,
    ) -> CategoryScanResult:
        """Internal: scrape one category, analyze, persist."""
        logger.info("Scanning category: %s (%s)", name, slug)

        # 1. Scrape category listing
        products = await scraper.scrape_category(url)
        if not products:
            return CategoryScanResult(
                category_slug=slug, category_name=name,
                products_scraped=0, vulnerable_products=0,
                vulnerability_ratio=0.0, is_niche_vulnerable=False,
                monopolization_index_avg=0.0,
            )

        # 2. Enrich top products with card detail
        for i, prod in enumerate(products[:10]):
            if prod.url:
                detail = await scraper.scrape_product_card(prod.url)
                if detail:
                    prod.photo_count = detail.get("photo_count", 0)
                    prod.has_infographics = detail.get("has_infographics", False)
                    prod.description_length = detail.get("description_length", 0)
                    prod.seller_count = detail.get("seller_count", 0)
                    if detail.get("rating") is not None:
                        prod.rating = detail["rating"]
                    if detail.get("review_count"):
                        prod.review_count = detail["review_count"]

        # 3. Get seller count
        seller_count = await scraper.get_seller_count(url)

        # 4. Analyze niche
        niche: NicheResult = self._analyzer.analyze_niche(
            category_slug=slug,
            products=products,
            seller_count=seller_count,
        )

        # 5. Persist to DB
        await self._persist_results(products, niche)

        return CategoryScanResult(
            category_slug=slug,
            category_name=name,
            products_scraped=len(products),
            vulnerable_products=niche.weak_card_count,
            vulnerability_ratio=niche.vulnerability_ratio,
            is_niche_vulnerable=niche.is_vulnerable,
            monopolization_index_avg=niche.monopolization_index,
            top_opportunities=products[:5] if niche.is_vulnerable else [],
        )

    async def _persist_results(
        self, products: list[ProductCard], niche: NicheResult
    ) -> None:
        """Upsert products and niche analysis to the database.

        Uses SELECT + merge pattern for cross-DB compatibility
        (works with both PostgreSQL and SQLite for tests).
        """
        product_orm_map: dict[str, Product] = {}

        for prod in products:
            # Check if product already exists
            stmt = select(Product).where(Product.kaspi_id == prod.kaspi_id)
            result = await self._db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing product
                existing.title = prod.title
                existing.price_min = prod.price_min
                existing.price_max = prod.price_max
                existing.photo_count = prod.photo_count
                existing.has_infographics = prod.has_infographics
                existing.description_length = prod.description_length
                existing.rating = prod.rating
                existing.review_count = prod.review_count
                existing.seller_count = prod.seller_count
                product_orm_map[prod.kaspi_id] = existing
            else:
                # Insert new product
                new_product = Product(
                    kaspi_id=prod.kaspi_id,
                    title=prod.title,
                    category_slug=prod.category_slug,
                    url=prod.url,
                    price_min=prod.price_min,
                    price_max=prod.price_max,
                    photo_count=prod.photo_count,
                    has_infographics=prod.has_infographics,
                    description_length=prod.description_length,
                    rating=prod.rating,
                    review_count=prod.review_count,
                    seller_name=prod.seller_name,
                    seller_count=prod.seller_count,
                )
                self._db.add(new_product)
                await self._db.flush()
                product_orm_map[prod.kaspi_id] = new_product

        # Persist NicheAnalysis for each product in the niche
        for card_score in niche.card_scores:
            product_orm = product_orm_map.get(card_score.kaspi_id)
            if not product_orm:
                continue

            niche_record = NicheAnalysis(
                product_id=product_orm.id,
                category_slug=niche.category_slug,
                demand_score=niche.demand_score,
                seller_count_in_category=niche.seller_count,
                monopolization_index=niche.monopolization_index,
                visual_score=card_score.weak_signals / card_score.total_signals
                if card_score.total_signals > 0 else 0.0,
                is_vulnerable=niche.is_vulnerable,
            )
            self._db.add(niche_record)

        await self._db.flush()
        logger.info(
            "Persisted %d products + %d niche analyses for category %s",
            len(products), len(niche.card_scores), niche.category_slug,
        )
