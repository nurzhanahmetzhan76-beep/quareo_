import re
with open('kaspi_dump.html', 'r', encoding='utf-8') as f:
    html = f.read()

# try to find seller
seller_match = re.search(r'merchantName[^\w]{1,5}([\w\s\&]+)', html)
if seller_match:
    print('Found seller via regex:', seller_match.group(1))

brand_match = re.search(r'brand[^\w]{1,5}([\w\s\&]+)', html, re.IGNORECASE)
if brand_match:
    print('Found brand via regex:', brand_match.group(1))

from bs4 import BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')
for h in soup.find_all(['h1', 'h2', 'h3']):
    print(h.name, h.text.strip())
