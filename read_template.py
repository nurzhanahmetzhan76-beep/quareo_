import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')
root = ET.parse('ACTIVE (1).xml').getroot()

# Kaspi XML uses either standard or namespace
for elem in root.iter():
    if '}' in elem.tag:
        elem.tag = elem.tag.split('}', 1)[1]

offers = root.findall('.//offer')
print(f"Total offers: {len(offers)}")
if offers:
    print(ET.tostring(offers[0]).decode('utf-8'))


