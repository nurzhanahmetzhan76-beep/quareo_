import os
import glob

html_files = glob.glob('frontend/*.html')
for file in html_files:
    if file.endswith('blue_ocean.html'): continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '<a href="blue_ocean.html"' in content: continue
    
    old_line = '<a href="wb_scanner.html" data-i="nav_wb_scanner">Сканер WB</a>'
    new_line = '<a href="wb_scanner.html" data-i="nav_wb_scanner">Сканер WB</a>\n        <a href="blue_ocean.html" data-i="nav_blue_ocean">Blue Ocean 🌊</a>'
    
    old_line_active = '<a href="wb_scanner.html" class="active" data-i="nav_wb_scanner">Сканер WB</a>'
    new_line_active = '<a href="wb_scanner.html" class="active" data-i="nav_wb_scanner">Сканер WB</a>\n        <a href="blue_ocean.html" data-i="nav_blue_ocean">Blue Ocean 🌊</a>'
    
    content = content.replace(old_line, new_line)
    content = content.replace(old_line_active, new_line_active)
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print('Done replacing in HTML files.')
