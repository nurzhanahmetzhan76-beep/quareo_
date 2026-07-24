from bs4 import BeautifulSoup

with open('kaspi_dump.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print('Title:', soup.title.text if soup.title else 'No title')

for a in soup.find_all('a'):
    href = a.get('href') or ''
    if 'shop/c' in href and 'manufacturer' in href:
        print('Found brand via href:', a.text)
        
for tr in soup.select('.specifications-list__spec'):
    dt = tr.select_one('.specifications-list__spec-term-text')
    dd = tr.select_one('.specifications-list__spec-def')
    if dt and dd:
        print('Spec:', dt.text.strip(), '->', dd.text.strip())

sellers = soup.select('a[href*="/shop/info/merchant/"]')
for s in sellers:
    print('Seller:', s.text.strip())

# Look for rating and reviews
reviews = soup.select('.reviews-count, .product-rating__count, .rating__reviews')
for r in reviews:
    print('Reviews:', r.text.strip())

rating = soup.select('.rating__value, [data-rating]')
for r in rating:
    print('Rating:', r.text.strip())
