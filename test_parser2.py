from bs4 import BeautifulSoup
import re

with open('kaspi_dump.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print('Title:', soup.title.text if soup.title else '')

# Find all links
links = soup.find_all('a')
for a in links:
    href = a.get('href', '')
    if 'merchant' in href:
        print('Merchant link:', a.text.strip(), href)
    if 'manufacturer' in href:
        print('Manufacturer link:', a.text.strip(), href)

# Find any text with 'отзыв'
for tag in soup.find_all(string=re.compile('отзыв', re.I)):
    print('Reviews element:', tag.parent.name, tag.parent.get('class'), tag.strip())

