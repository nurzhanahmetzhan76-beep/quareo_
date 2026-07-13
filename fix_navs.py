import os
import glob
import re

nav_links_html = """      <a href="dashboard.html" data-i="nav_dashboard">Личный кабинет</a>
      <a href="index.html" data-i="nav_home">Главная</a>
      <a href="scanner.html" data-i="nav_scanner">Сканер Kaspi</a>
      <a href="wb_scanner.html" data-i="nav_wb_scanner">Сканер WB</a>
      <a href="ntin.html" data-i="nav_ntin">NTIN</a>
      <a href="analytics.html" data-i="nav_analytics">Аналитика</a>
      <a href="waybills.html" data-i="nav_waybills">Накладные</a>
      <a href="pricing.html" data-i="nav_pricing">Тарифы</a>"""

def update_nav(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The block to replace usually starts with <div class="nav-links" id="navLinks">
    # and ends with </div>
    pattern = re.compile(r'(<div class="nav-links" id="navLinks">)(.*?)(</div>)', re.DOTALL)
    
    def replacer(match):
        # We also want to keep the "active" class on the correct link
        # We'll just replace the inner content with nav_links_html, and then add 'class="active"' to the link that matches the current filename
        filename = os.path.basename(filepath)
        
        links = nav_links_html
        
        # Replace href="filename" with href="filename" class="active"
        if filename in links:
            # specifically for index.html, scanner.html etc
            links = links.replace(f'href="{filename}"', f'href="{filename}" class="active"')
            
        return f"{match.group(1)}\n{links}\n    {match.group(3)}"

    new_content = pattern.sub(replacer, content)
    
    # We also need to remove footer links to kaspi-bot.html
    new_content = re.sub(r'<a href="kaspi-bot.html".*?</a>\s*', '', new_content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for html_file in glob.glob('frontend/*.html'):
    update_nav(html_file)
