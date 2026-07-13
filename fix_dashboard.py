import re
import os

with open('frontend/dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# We want to replace the page-connect section with the new Kaspi-like profile section.
new_section = """  <!-- ═══════ PAGE: Profile (Личный кабинет) ═══════ -->
  <section class="page active" id="page-connect" style="background:#fff; padding: 2rem 3rem;">
    <h2 style="font-size: 24px; font-weight: bold; margin-bottom: 24px; color: #333;">Информация о магазине</h2>
    
    <div class="kaspi-tabs">
      <div class="kaspi-tab active" onclick="switchKaspiTab('general', this)">Общая информация</div>
      <div class="kaspi-tab">Склады и магазины</div>
      <div class="kaspi-tab">Kaspi Доставка</div>
      <div class="kaspi-tab">Моя доставка</div>
      <div class="kaspi-tab">Расписание в праздники</div>
      <div class="kaspi-tab" onclick="switchKaspiTab('api', this)">Токен API</div>
    </div>

    <!-- General Info Tab -->
    <div class="kaspi-tab-content" id="kTabGeneral">
      <div class="k-section-header">
        <h3 style="font-size: 18px; font-weight: bold; color: #333; margin: 0;">Общая информация</h3>
        <svg class="k-edit-icon" viewBox="0 0 24 24" fill="none" stroke="#0089D0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
      </div>
      
      <div class="k-info-row">
        <div class="k-info-label">ID партнера</div>
        <div class="k-info-value font-bold">17768037</div>
      </div>
      <div class="k-info-row">
        <div class="k-info-label">Название магазина</div>
        <div class="k-info-value font-bold" id="kShopName">Revalo 1</div>
      </div>
      <div class="k-info-row">
        <div class="k-info-label">Логотип</div>
        <div class="k-info-value">
          <div class="k-logo-circle">R</div>
        </div>
      </div>
      <div class="k-info-row">
        <div class="k-info-label">Страница магазина на Kaspi.kz</div>
        <div class="k-info-value"><a href="#" class="k-link">Ссылка</a></div>
      </div>
      <div class="k-info-row">
        <div class="k-info-label">Все товары магазина на Kaspi.kz</div>
        <div class="k-info-value"><a href="#" class="k-link">Ссылка</a></div>
      </div>
      <div class="k-info-row">
        <div class="k-info-label">График работы</div>
        <div class="k-info-value font-bold">Пн - Вс: 09:00 - 21:00</div>
      </div>

      <div class="k-section-header" style="margin-top: 40px;">
        <h3 style="font-size: 18px; font-weight: bold; color: #333; margin: 0;">Номера телефонов для покупателей</h3>
      </div>
    </div>

    <!-- API Token Tab (for actual connection) -->
    <div class="kaspi-tab-content" id="kTabApi" style="display:none;">
      <div class="card connect-card" style="margin: 2rem 0; max-width: 500px; box-shadow: none; border: 1px solid #E2E8F0;">
        <h3 style="margin-bottom: 8px;">Данные для подключения</h3>
        <p class="connect-sub">Эти данные нужны роботу для работы с вашим кабинетом.</p>
        
        <div class="form-group"><label class="form-label">Номер телефона (ID магазина)</label><input class="form-input" id="kaspiPhone" placeholder="+7 ___ ___ __ __"></div>
        <div class="form-group"><label class="form-label">API-ключ Kaspi Seller</label><input class="form-input" id="kaspiApiKey" type="password" placeholder="Вставьте ваш API-ключ"></div>
        <div class="form-group"><label class="form-label">API-ключ НКТ (для NTIN)</label><input class="form-input" id="nktApiKey" type="password" placeholder="Ключ от nationalcatalog.kz"></div>
        
        <button class="btn-primary" style="width:100%;padding:14px;margin-top:1rem" onclick="connectStore()">Сохранить настройки</button>
        <div id="connectStatus" style="margin-top:12px;font-size:13px"></div>
      </div>
    </div>
  </section>"""

pattern = re.compile(r'<!-- ═══════ PAGE: Connect Kaspi ═══════ -->.*?</section>', re.DOTALL)
html = pattern.sub(new_section, html)

# Make "connect" page active instead of NTIN initially to show the profile
html = html.replace('<section class="page active" id="page-ntin">', '<section class="page" id="page-ntin">')
# The sb-link logic: we'll change it in dashboard.js or just hardcode active here.
html = html.replace('<a class="sb-link active" data-page="ntin"', '<a class="sb-link" data-page="ntin"')
html = html.replace('<a class="sb-link" data-page="connect"', '<a class="sb-link active" data-page="connect"')
# Change the sidebar text from "🔗 Подключение" to "👤 Мой профиль"
html = html.replace('🔗 Подключение', '👤 Мой профиль')

with open('frontend/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)


with open('frontend/assets/dashboard.css', 'a', encoding='utf-8') as f:
    f.write('''
/* ── Kaspi Style Profile ───────────────────────────────────── */
.kaspi-tabs {
  display: flex;
  border-bottom: 1px solid #E0E0E0;
  margin-bottom: 2rem;
  overflow-x: auto;
}
.kaspi-tab {
  padding: 12px 20px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  white-space: nowrap;
  border-bottom: 3px solid transparent;
  margin-bottom: -1px;
}
.kaspi-tab:hover {
  color: #E21836;
}
.kaspi-tab.active {
  color: #333;
  font-weight: 500;
  border-bottom-color: #F14635; /* Kaspi red */
}
.k-section-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}
.k-edit-icon {
  width: 18px;
  height: 18px;
  cursor: pointer;
}
.k-info-row {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  font-size: 14px;
}
.k-info-label {
  width: 250px;
  color: #555;
}
.k-info-value {
  color: #333;
}
.k-info-value.font-bold {
  font-weight: 600;
}
.k-link {
  color: #0089D0;
  text-decoration: none;
}
.k-link:hover {
  text-decoration: underline;
}
.k-logo-circle {
  width: 60px;
  height: 60px;
  background-color: #FFD100; /* Kaspi yellow */
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 300;
  font-family: sans-serif;
}
''')

# Update dashboard.js to handle tab switching inside Kaspi profile
with open('frontend/assets/dashboard.js', 'r', encoding='utf-8') as f:
    js = f.read()

if "switchKaspiTab" not in js:
    kaspi_js = """
/* ── Kaspi Profile Tabs ───────────────────────────────────── */
function switchKaspiTab(tabId, el) {
  document.querySelectorAll('.kaspi-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  
  document.querySelectorAll('.kaspi-tab-content').forEach(c => c.style.display = 'none');
  
  if(tabId === 'general') document.getElementById('kTabGeneral').style.display = 'block';
  if(tabId === 'api') document.getElementById('kTabApi').style.display = 'block';
}

// Ensure the profile name matches the connected store
document.addEventListener('DOMContentLoaded', () => {
  const shopName = localStorage.getItem('quareo_shop');
  if (shopName) {
    const el = document.getElementById('kShopName');
    if (el) el.textContent = shopName;
  }
});
"""
    with open('frontend/assets/dashboard.js', 'a', encoding='utf-8') as f:
        f.write(kaspi_js)

# Update PAGE_TITLES to match 'Мой профиль' instead of 'Подключение магазина'
js = js.replace("'connect': 'Подключение магазина'", "'connect': 'Информация о магазине'")
with open('frontend/assets/dashboard.js', 'w', encoding='utf-8') as f:
    f.write(js)
