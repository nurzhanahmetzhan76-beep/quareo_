import os

with open('frontend/scanner.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('<a href="scanner.html" class="active" data-i="nav_scanner">Сканер</a>', '<a href="scanner.html" data-i="nav_scanner">Сканер</a>')
html = html.replace('<a href="wb_scanner.html" data-i="nav_wb_scanner">Сканер WB</a>', '<a href="wb_scanner.html" class="active" data-i="nav_wb_scanner">Сканер WB</a>')

html = html.replace('/api/scan', '/api/wb_scan')

html = html.replace('Kaspi Niche Scanner', 'WB Niche Scanner')
html = html.replace('kaspi.kz', 'wildberries.ru')
html = html.replace('Kaspi.kz', 'Wildberries')
html = html.replace('Kaspi Доставки', 'быстрой доставки WB')
html = html.replace('quareo@scanner — wildberries.ru', 'quareo@scanner — wildberries.ru') # safety

with open('frontend/wb_scanner.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Done!')
