import asyncio
import logging
from retailpool.scraper.antifraud import StaticProxyProvider
from retailpool.scraper.browser import BrowserManager, _run_in_pw_thread_async
from retailpool.scraper.kaspi_scraper import KaspiScraper

logging.basicConfig(level=logging.INFO)

async def main():
    proxy = StaticProxyProvider()
    async with BrowserManager(proxy_provider=proxy, headless=True) as browser:
        ctx = await browser.new_context()
        page = await _run_in_pw_thread_async(ctx.new_page)
        
        def run_goto():
            page.goto("https://kaspi.kz/shop/search/?text=iphone", wait_until="domcontentloaded", timeout=45000)
            return page.content()
            
        content = await _run_in_pw_thread_async(run_goto)
        
        with open("kaspi_search.html", "w", encoding="utf-8") as f:
            f.write(content)
            
        await _run_in_pw_thread_async(page.close)
        await _run_in_pw_thread_async(lambda: ctx.close())

asyncio.run(main())
