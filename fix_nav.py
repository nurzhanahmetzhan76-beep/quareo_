import os
import re

html_dir = 'c:\\Users\\user\\Desktop\\retailpool\\frontend'

items = [
    ('index.html', 'nav_home', 'Главная'),
    ('scanner.html', 'nav_scanner', 'Сканер'),
    ('ntin.html', 'nav_ntin', 'NTIN'),
    ('analytics.html', 'nav_analytics', 'Аналитика'),
    ('waybills.html', 'nav_waybills', 'Накладные'),
    ('pricing.html', 'nav_pricing', 'Тарифы'),
]

for file in os.listdir(html_dir):
    if not file.endswith('.html'): continue
    path = os.path.join(html_dir, file)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update navLinks
    nav_match = re.search(r'<div class="nav-links" id="navLinks">.*?</div>', content, flags=re.DOTALL)
    if nav_match:
        nav_html = '<div class="nav-links" id="navLinks">\n'
        for href, data_i, text in items:
            active_str = ' class="active"' if href == file else ''
            nav_html += f'      <a href="{href}"{active_str} data-i="{data_i}">{text}</a>\n'
        nav_html += '    </div>'
        content = content[:nav_match.start()] + nav_html + content[nav_match.end():]
        
    # Update Contacts in Footer
    content = re.sub(r'<a href="[^"]*"( data-i="footer_l_contact")?>Контакты</a>', r'<a href="https://t.me/@Lulsiok" target="_blank" data-i="footer_l_contact">Контакты</a>', content)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

print('Done')
