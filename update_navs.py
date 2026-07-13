import glob
import os

html_files = glob.glob('frontend/*.html')

for filepath in html_files:
    if 'dashboard.html' in filepath:
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # We are replacing dashboard.html#products with wb_scanner.html
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if 'dashboard.html#products' in line and 'Сканер WB' in line:
            line = line.replace('dashboard.html#products', 'wb_scanner.html')
        new_lines.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
        
print("Updated all HTML nav bars!")
