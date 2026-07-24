import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://kaspi.kz/shop/p/ofisnoe-kreslo-sport-fitness-sfbrgcfr11-chernyi-hrom-159544511/')
        await page.wait_for_timeout(3000)
        
        try:
            city_btn = page.locator('text=Алматы').first
            await city_btn.click(timeout=1000)
            await page.wait_for_timeout(1000)
        except:
            pass
            
        print('Title:', await page.title())
        
        html = await page.content()
        with open('kaspi_dump.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print('Dumped to kaspi_dump.html')
        await browser.close()

asyncio.run(main())
