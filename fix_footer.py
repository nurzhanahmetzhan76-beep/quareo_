import os
import glob
import re

html_files = glob.glob(r'c:\Users\user\Desktop\retailpool\frontend\*.html')

new_footer = """<div class="footer-grid">
      <div>
        <div class="footer-brand">Quareo</div>
        <p class="footer-desc" data-i="footer_desc">ИИ-радар по Kaspi.kz: находим ниши со слабой конкуренцией и оптимизируем ваши продажи через глубокую аналитику.</p>
      </div>
      <div class="footer-col">
        <div class="footer-col-title" data-i="footer_product">Продукт</div>
        <a href="scanner.html" data-i="footer_l_scanner">Niche Scanner</a>
        <a href="wb_scanner.html" data-i="footer_l_wb">Сканер WB</a>
        <a href="analytics.html" data-i="footer_l_analytics">Аналитика</a>
        <a href="ntin.html" data-i="footer_l_ntin">NTIN</a>
        <a href="waybills.html" data-i="footer_l_waybills">Накладные</a>
        <a href="pricing.html" data-i="footer_l_pricing">Тарифы</a>
      </div>
      <div class="footer-col">
        <div class="footer-col-title" data-i="footer_company">Компания</div>
        <a href="about.html" data-i="footer_l_about">О проекте</a>
        <a href="https://t.me/Lulsiok" target="_blank" data-i="footer_l_contact">Контакты</a>
        <a href="https://t.me/quareobot" target="_blank" data-i="footer_l_telegram">Telegram-бот</a>
      </div>
      <div class="footer-col">
        <div class="footer-col-title" data-i="footer_legal">Документы</div>
        <a href="privacy.html" data-i="footer_l_privacy">Политика конфиденциальности</a>
        <a href="terms.html" data-i="footer_l_terms">Условия использования</a>
        <a href="terms.html" data-i="footer_l_offer">Публичная оферта</a>
      </div>
    </div>"""

for file_path in html_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the entire footer grid
    content = re.sub(
        r'<div class="footer-grid">.*?</div>\s*<div class="footer-bottom">',
        new_footer + '\n    <div class="footer-bottom">',
        content,
        flags=re.DOTALL
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Footers updated.")
