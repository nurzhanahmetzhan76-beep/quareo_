import os, glob, re

d = 'frontend'

# 1. Read wb_scanner.html
content = open(os.path.join(d, 'wb_scanner.html'), encoding='utf-8').read()

# 2. Modify to create ozon_scanner.html
# First replace nav items to prevent replacing wb_scanner completely
# The nav looks like:
# <a href="scanner.html" data-i="nav_scanner">Сканер Kaspi</a>
# <a href="wb_scanner.html" class="active" data-i="nav_wb_scanner">Сканер WB</a>
# We'll inject Ozon scanner nav to all files below.

# String replacements for ozon_scanner.html
ozon = content.replace('Wildberries', 'Ozon')
ozon = ozon.replace('WB', 'Ozon')
ozon = ozon.replace('wildberries.ru', 'ozon.ru')
ozon = ozon.replace('/api/wb_scan', '/api/ozon_scan')

# Fix the navigation in ozon_scanner.html
# It currently has: <a href="ozon_scanner.html" class="active" data-i="nav_ozon_scanner">Сканер Ozon</a> (due to 'wb_scanner.html' replacement -> wait, I didn't replace 'wb_scanner.html' yet)
ozon = ozon.replace('wb_scanner.html', 'ozon_scanner.html')
# Now the nav is:
# <a href="scanner.html" data-i="nav_scanner">Сканер Kaspi</a>
# <a href="ozon_scanner.html" class="active" data-i="nav_ozon_scanner">Сканер Ozon</a>
# We lost wb_scanner! Let's insert it back before ozon_scanner.html:
ozon = re.sub(r'(<a href="ozon_scanner\.html" class="active"[^>]*>Сканер Ozon</a>)',
              r'<a href="wb_scanner.html" data-i="nav_wb_scanner">Сканер WB</a>\n      \1', ozon)

open(os.path.join(d, 'ozon_scanner.html'), 'w', encoding='utf-8').write(ozon)

# 3. Inject Ozon scanner to all other HTML files
for f in glob.glob(os.path.join(d, '*.html')):
    if f.endswith('ozon_scanner.html'): continue
    
    c = open(f, encoding='utf-8').read()
    if 'ozon_scanner.html' not in c and 'nav_wb_scanner' in c:
        # Match wb_scanner link and append ozon_scanner link
        c = re.sub(r'(<a href="wb_scanner\.html"[^>]*>Сканер WB</a>)', 
                   r'\1\n      <a href="ozon_scanner.html" data-i="nav_ozon_scanner">Сканер Ozon</a>', c)
        open(f, 'w', encoding='utf-8').write(c)

print("Done")
