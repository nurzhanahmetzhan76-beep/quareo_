import os
import glob

frontend_dir = r'c:\Users\user\Desktop\retailpool\frontend'
html_files = glob.glob(os.path.join(frontend_dir, '*.html'))

for file in html_files:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        updated = False
        
        # Add to nav
        if 'data-i="nav_kaspi_bot"' not in content:
            content = content.replace(
                '<a href="waybills.html" data-i="nav_waybills">Накладные</a>',
                '<a href="waybills.html" data-i="nav_waybills">Накладные</a>\n      <a href="kaspi-bot.html" data-i="nav_kaspi_bot">Kaspi-бот</a>'
            )
            updated = True
            
        # Add to footer
        if 'data-i="footer_l_scanner"' in content and '<a href="kaspi-bot.html"' not in content[content.find('footer_l_scanner'):content.find('footer_l_scanner')+300]:
            content = content.replace(
                '<a href="scanner.html" data-i="footer_l_scanner">Niche Scanner</a>',
                '<a href="scanner.html" data-i="footer_l_scanner">Niche Scanner</a>\n        <a href="kaspi-bot.html" data-i="nav_kaspi_bot">Kaspi-бот</a>'
            )
            updated = True
            
        if updated:
            with open(file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'Updated {os.path.basename(file)}')
    except Exception as e:
        print(f'Error on {os.path.basename(file)}: {e}')
