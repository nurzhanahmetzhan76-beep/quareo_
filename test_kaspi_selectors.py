import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to Kaspi...")
        await page.goto('https://kaspi.kz/shop/search/?text=iphone', wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        # Inject JS to find the product cards
        data = await page.evaluate("""() => {
            let elements = document.querySelectorAll('a[href*="/shop/p/"]');
            let result = [];
            for(let i=0; i<Math.min(5, elements.length); i++) {
                let el = elements[i];
                let parent = el.parentElement;
                let classes = [];
                for(let j=0; j<4; j++) {
                    if (parent) {
                        classes.push(parent.className);
                        parent = parent.parentElement;
                    }
                }
                result.push({ href: el.getAttribute('href'), parent_classes: classes });
            }
            return result;
        }""")
        
        with open('kaspi_selectors.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
