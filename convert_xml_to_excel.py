import xml.etree.ElementTree as ET
import openpyxl

# Load XML
print("Parsing XML...")
root = ET.parse('ACTIVE (1).xml').getroot()

for elem in root.iter():
    if '}' in elem.tag:
        elem.tag = elem.tag.split('}', 1)[1]

offers = root.findall('.//offer')
print(f"Found {len(offers)} offers in XML.")

# Create a new workbook
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Лист1"

# Add Kaspi headers (as requested)
headers = ['SKU', 'model', 'brand', 'price', 'PP1', 'PP2', 'PP3', 'PP4', 'PP5', 'preorder']
ws.append(headers)

# Extract data
for offer in offers:
    sku = offer.get('sku')
    
    model_node = offer.find('model')
    model = model_node.text if model_node is not None and model_node.text else f"Товар {sku}"
    
    brand_node = offer.find('brand')
    brand = brand_node.text if brand_node is not None and brand_node.text else "Без бренда"
    
    price = ""
    price_node = offer.find('price')
    if price_node is not None and price_node.text:
        price = price_node.text
    else:
        cityprice = offer.find('.//cityprice')
        if cityprice is not None and cityprice.text:
            price = cityprice.text
            
    try:
        price = float(price) if price else 0
    except ValueError:
        price = 0

    # Parse availabilities for stock counts
    pp_stocks = {'PP1': 0, 'PP2': 0, 'PP3': 0, 'PP4': 0, 'PP5': 0}
    availabilities = offer.findall('.//availability')
    for av in availabilities:
        store_id = av.get('storeId', '')
        stock_val = av.get('stockCount', '0')
        try:
            stock = int(float(stock_val))
        except ValueError:
            stock = 0
            
        # Figure out which PP column this belongs to
        if 'PP1' in store_id: pp_stocks['PP1'] = stock
        elif 'PP2' in store_id: pp_stocks['PP2'] = stock
        elif 'PP3' in store_id: pp_stocks['PP3'] = stock
        elif 'PP4' in store_id: pp_stocks['PP4'] = stock
        elif 'PP5' in store_id: pp_stocks['PP5'] = stock
        elif 'PP6' in store_id: pp_stocks['PP1'] += stock # fallback if PP6
        else: pp_stocks['PP1'] += stock # default to PP1

    row = [
        sku, 
        model, 
        brand, 
        price, 
        pp_stocks['PP1'], 
        pp_stocks['PP2'], 
        pp_stocks['PP3'], 
        pp_stocks['PP4'], 
        pp_stocks['PP5'], 
        ""
    ]
    ws.append(row)

# Save the workbook
output_file = 'ACTIVE_CONVERTED_v2.xlsx'
wb.save(output_file)
print(f"Success! Saved to {output_file}")
