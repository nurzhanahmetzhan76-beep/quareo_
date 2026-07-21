import logging
import urllib.parse
from retailpool.scraper.antifraud import BaseProxyProvider
from retailpool.schemas.product import WBProductCard
from retailpool.scraper.browser import BrowserManager, _run_in_pw_thread_async

logger = logging.getLogger(__name__)

class WBScraper:
    """
    Playwright-based scraper for Wildberries.
    Bypasses Cloudflare blockades by simulating a real browser.
    """

    def __init__(self, proxy_provider: BaseProxyProvider | None = None) -> None:
        self.proxy_provider = proxy_provider

    async def search(self, query: str, max_items: int = 10) -> list[WBProductCard]:
        """Search for products on Wildberries using Playwright browser."""
        try:
            async with BrowserManager(proxy_provider=self.proxy_provider) as browser:
                ctx = await browser.new_context()
                raw_products = await _run_in_pw_thread_async(
                    lambda: self._scrape_search_sync(ctx, query, max_items)
                )
                
                results = []
                for p in raw_products:
                    try:
                        results.append(WBProductCard(**p))
                    except Exception as e:
                        logger.warning(f"Failed to parse WBProductCard: {e}")
                
                logger.info("WB Scraped %d products for query '%s' via Playwright", len(results), query)
                return results
                
        except Exception as e:
            logger.error("Error scraping WB for '%s' using Playwright: %s", query, e)
            return []

    @staticmethod
    def _scrape_search_sync(ctx, query: str, max_items: int) -> list[dict]:
        """Scrape search results page. MUST run in PW thread."""
        page = ctx.new_page()
        raw_products = []
        
        try:
            search_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={urllib.parse.quote(query)}"
            logger.info("Navigating to WB search: %s", search_url)
            
            resp = page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            
            # Wait for product cards
            try:
                page.wait_for_selector(
                    "article.product-card", timeout=15000
                )
            except Exception:
                logger.warning("WB Product cards not found. Checking if blocked or empty...")
                if "cloudflare" in page.content().lower() or "докажите, что вы человек" in page.content().lower():
                    logger.warning("WB BLOCKED by Cloudflare CAPTCHA!")
                return []
                
            # Scroll down to load images and trigger lazy loading
            page.evaluate("window.scrollBy(0, 500)")
            page.wait_for_timeout(1000)

            result_data = page.evaluate("""() => {
                const cards = document.querySelectorAll('article.product-card');
                
                return Array.from(cards).map(card => {
                    const linkEl = card.querySelector('a.product-card__link, a[class*="product-card"]');
                    const titleEl = card.querySelector('.product-card__name');
                    const brandEl = card.querySelector('.product-card__brand');
                    
                    // Prices
                    const priceLowerEl = card.querySelector('.price__lower-price, .price__wrap ins'); 
                    let priceText = priceLowerEl ? priceLowerEl.textContent : '';
                    
                    // Rating and reviews
                    const ratingEl = card.querySelector('.address-rate-mini, [class*="rating"]'); 
                    const reviewEl = card.querySelector('.product-card__count, [class*="review"]'); 
                    
                    const href = linkEl ? linkEl.getAttribute('href') : '';
                    
                    let wb_id = card.getAttribute('data-nm-id') || '';
                    if (!wb_id && href) {
                        const match = href.match(/catalog\\/(\\d+)\\/detail/);
                        if (match) wb_id = match[1];
                    }
                    
                    const title = titleEl ? titleEl.textContent.trim().replace(/^\\/\\s*/, '') : '';
                    const brand = brandEl ? brandEl.textContent.trim() : '';
                    
                    const priceClean = priceText.replace(/[^\\d]/g, '');
                    const price_rub = priceClean ? parseInt(priceClean) : 0;
                    
                    const ratingStr = ratingEl ? ratingEl.textContent.trim() : '';
                    const rating = ratingStr ? parseFloat(ratingStr) : null;
                    
                    const reviewStr = reviewEl ? reviewEl.textContent.replace(/[^\\d]/g, '') : '';
                    const review_count = reviewStr ? parseInt(reviewStr) : 0;
                    
                    return {
                        wb_id: wb_id,
                        title: title || 'Без названия',
                        brand: brand,
                        url: href ? (href.startsWith('http') ? href : 'https://www.wildberries.ru' + href) : '',
                        price_rub: price_rub,
                        rating: rating,
                        review_count: review_count
                    };
                }).filter(item => item.wb_id && item.price_rub > 0);
            }""")
            
            for item in result_data[:max_items]:
                # Calculate KZT price (~5 KZT per RUB)
                item['price_kzt'] = item['price_rub'] * 5.0
                raw_products.append(item)
                
        except Exception as exc:
            logger.error("Error scraping WB search sync '%s': %s", query, exc)
        finally:
            page.close()
            
        return raw_products
