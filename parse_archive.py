import xml.etree.ElementTree as ET
import sys
import os

filepath = r'c:\Users\user\Desktop\retailpool\archive.xml'

tree = ET.parse(filepath)
root = tree.getroot()

ns = {'k': 'kaspiShopping'} if 'kaspiShopping' in root.tag else {}
offers = root.findall('.//k:offer', ns) if ns else root.findall('.//offer')

print(f'Total offers found: {len(offers)}')

yes_count = 0
no_count = 0

for offer in offers:
    avails = offer.findall('.//k:availability', ns) if ns else offer.findall('.//availability')
    is_yes = False
    for avail in avails:
        if avail.get('available') == 'yes':
            is_yes = True
    
    if is_yes:
        yes_count += 1
    else:
        no_count += 1

print(f'Available YES: {yes_count}')
print(f'Available NO: {no_count}')

# Print first 5 YES
print("--- YES ---")
found = 0
for offer in offers:
    avails = offer.findall('.//k:availability', ns) if ns else offer.findall('.//availability')
    is_yes = False
    for avail in avails:
        if avail.get('available') == 'yes':
            is_yes = True
    
    if is_yes:
        sku = offer.get('sku')
        price = offer.find('k:price', ns) if ns else offer.find('price')
        price_text = price.text if price is not None else 'N/A'
        print(f'SKU: {sku}, Price: {price_text}, Avails: {[a.attrib for a in avails]}')
        found += 1
        if found >= 5: break
