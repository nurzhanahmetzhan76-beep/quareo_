import xml.etree.ElementTree as ET
filepath = r'c:\Users\user\Desktop\retailpool\archive.xml'
tree = ET.parse(filepath)
root = tree.getroot()
ns = {'k': 'kaspiShopping'} if 'kaspiShopping' in root.tag else {}
offers = root.findall('.//k:offer', ns) if ns else root.findall('.//offer')

print('Total offers:', len(offers))

cityprice_count = 0
for offer in offers:
    cp = offer.findall('.//k:cityprice', ns) if ns else offer.findall('.//cityprice')
    if cp:
        cityprice_count += 1
print('Offers with cityprice:', cityprice_count)

brand_count = 0
for offer in offers:
    b = offer.find('k:brand', ns) if ns else offer.find('brand')
    if b is not None and b.text and b.text.strip():
        brand_count += 1
print('Offers with brand:', brand_count)
