import re
from bs4 import BeautifulSoup
with open('kaspi_dump.html', 'r', encoding='utf-8') as f:
    html = f.read()

out = []

seller_match = re.search(r'merchantName[^\w]{1,5}([\w\s\&]+)', html)
if seller_match:
    out.append('Found seller via regex: ' + seller_match.group(1))

brand_match = re.search(r'brand[^\w]{1,5}([\w\s\&]+)', html, re.IGNORECASE)
if brand_match:
    out.append('Found brand via regex: ' + brand_match.group(1))

soup = BeautifulSoup(html, 'html.parser')

reviews = soup.select('.reviews-count, .product-rating__count, .rating__reviews')
for r in reviews:
    out.append('Reviews: ' + r.text.strip())

rating = soup.select('.rating__value, [data-rating]')
for r in rating:
    out.append('Rating: ' + r.text.strip())

with open('output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
