import xml.etree.ElementTree as ET
from openpyxl import Workbook
import os

filepath = r'c:\Users\user\Desktop\retailpool\archive.xml'
outpath = r'c:\Users\user\Desktop\retailpool\RECOVERY_KASPI.xlsx'

tree = ET.parse(filepath)
root = tree.getroot()
ns = {'k': 'kaspiShopping'} if 'kaspiShopping' in root.tag else {}
offers = root.findall('.//k:offer', ns) if ns else root.findall('.//offer')

wb = Workbook()
ws = wb.active
ws.append(['SKU', 'model', 'brand', 'price', 'PP1', 'PP2', 'PP3', 'PP4', 'PP5', 'preorder'])

count = 0
for offer in offers:
    sku = offer.get('sku')
    model_node = offer.find('k:model', ns) if ns else offer.find('model')
    brand_node = offer.find('k:brand', ns) if ns else offer.find('brand')
    price_node = offer.find('k:price', ns) if ns else offer.find('price')
    
    if price_node is None:
        cp = offer.find('.//k:cityprice', ns) if ns else offer.find('.//cityprice')
        if cp is not None:
            price_node = cp
            
    model = model_node.text if model_node is not None else ''
    brand = brand_node.text if brand_node is not None else 'Без бренда'
    if not brand or not str(brand).strip():
        brand = 'Без бренда'
    
    try:
        price = int(float(price_node.text)) if price_node is not None and price_node.text else 1000
    except:
        price = 1000
        
    ws.append([
        sku,
        model,
        brand,
        price,
        'yes',
        '', '', '', '', ''
    ])
    count += 1

wb.save(outpath)
print(f"Created {outpath} with {count} items.")
