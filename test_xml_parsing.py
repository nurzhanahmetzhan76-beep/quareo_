from defusedxml.ElementTree import fromstring
import xml.etree.ElementTree as ET

xml_data = """<?xml version="1.0" encoding="utf-8"?>
<kaspi_catalog date="2026-07-26 12:00" xmlns="kaspiShopping" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="kaspiShopping http://kaspi.kz/kaspishopping.xsd">
    <company>Test Seller</company>
    <merchantid>TestMerchant</merchantid>
    <offers>
        <offer sku="12345">
            <model>Product 1</model>
            <brand>Brand 1</brand>
            <price>2000</price>
            <availabilities>
                <availability available="yes" storeId="PP1" stockCount="50.0" preOrder="0"/>
            </availabilities>
        </offer>
    </offers>
</kaspi_catalog>"""

ns = {'k': 'kaspiShopping'}
ET.register_namespace('', 'kaspiShopping')

root = fromstring(xml_data)
offers = root.find('.//k:offers', ns)

for offer in offers.findall('.//k:offer', ns):
    target_node = offer.find('.//k:price', ns)
    if target_node is not None:
        target_node.text = "1500"
        print("Updated price!")
        
    avail_node = offer.find('.//k:availabilities', ns)
    if avail_node is None:
        avail_node = ET.SubElement(offer, '{kaspiShopping}availabilities')
    
    # Check if stockCount is preserved
    avails = avail_node.findall('.//k:availability', ns)
    for av in avails:
        print(f"StockCount is: {av.get('stockCount')}")

xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
print("\nFinal XML:")
print(xml_str)
