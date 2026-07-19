/* ============================================================
   Quareo Dashboard JS — Bulk NTIN automation engine
   ============================================================ */
const API = window.location.origin;

// Inject Auth headers into all API requests to fix 401 Unauthorized
const _dashFetch = window.fetch;
window.fetch = async function(...args) {
  let [resource, config] = args;
  if (typeof resource === 'string' && resource.startsWith(API + '/api/')) {
    config = config || {};
    config.headers = config.headers || {};
    if (typeof rpAuthHeaders === 'function') {
      Object.assign(config.headers, rpAuthHeaders());
    }
    args = [resource, config];
  }
  return _dashFetch(...args);
};
const ST = {
  draft:     { label: 'Черновик',     cls: 'st-draft' },
  ai_filled: { label: 'ИИ заполнен', cls: 'st-ai_filled' },
  ready:     { label: 'Готов',        cls: 'st-ai_filled' },
  submitted: { label: 'На модерации', cls: 'st-submitted' },
  revision:  { label: 'Доработка',   cls: 'st-revision' },
  approved:  { label: 'NTIN ✓',      cls: 'st-approved' },
  rejected:  { label: 'Отклонён',    cls: 'st-rejected' },
  revoked:   { label: 'Отозван',     cls: 'st-rejected' },
};
const PAGE_TITLES = {
  'connect': 'Информация о магазине',
  'ntin': 'NTIN Маркировка',
  'waybills': '📄 Накладные',
  'analytics': '📊 Аналитика',
  'calculator': '🧮 Калькулятор Kaspi'
};

let allProducts = []; // cached product list for filtering

/* ── Page switching ────────────────────────────────────────── */
function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sb-link').forEach(l => l.classList.remove('active'));
  const page = document.getElementById('page-' + id);
  if (page) page.classList.add('active');
  const link = document.querySelector('.sb-link[data-page="' + id + '"]');
  if (link) link.classList.add('active');
  document.getElementById('pageTitle').textContent = PAGE_TITLES[id] || id;
  if (id === 'ntin') { loadProducts(); loadStats(); }
  document.getElementById('sidebar').classList.remove('open');
}

/* ── Connect store ─────────────────────────────────────────── */
function switchConnectTab(tab, btn) {
  document.getElementById('connectPhone').style.display = tab === 'phone' ? '' : 'none';
  document.getElementById('connectEmail').style.display = tab === 'email' ? '' : 'none';
  btn.parentElement.querySelectorAll('.minitab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

async function connectStore() {
  const kaspiKey = document.getElementById('kaspiApiKey').value.trim();
  const nktKey = document.getElementById('nktApiKey').value.trim();
  const phone = document.getElementById('kaspiPhone').value.trim();
  const st = document.getElementById('connectStatus');

  if (!kaspiKey && !nktKey) { st.innerHTML = '<span style="color:#EF4444">Введите хотя бы один ключ</span>'; return; }

  try {
    const body = {};
    if (kaspiKey) body.kaspi_api_key = kaspiKey;
    if (nktKey) body.nkt_api_key = nktKey;
    if (phone) body.kaspi_merchant_id = phone;

    await fetch(API + '/api/ntin/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });

    localStorage.setItem('quareo_connected', '1');
    localStorage.setItem('quareo_shop', phone || 'Мой магазин');
    st.innerHTML = '<span style="color:#10B981">✓ Магазин успешно подключён!</span>';
    updateShopBadge();
    setTimeout(() => showPage('ntin'), 1000);
  } catch (e) {
    st.innerHTML = '<span style="color:#EF4444">Ошибка: ' + e.message + '</span>';
  }
}

function updateShopBadge() {
  const badge = document.getElementById('shopBadge');
  if (localStorage.getItem('quareo_connected')) {
    badge.style.display = 'flex';
    document.getElementById('shopNameBadge').textContent = localStorage.getItem('quareo_shop') || 'Магазин';
  }
}

/* ── Stats ─────────────────────────────────────────────────── */
async function loadUserProfile() {
  try {
    const r = await fetch(API + '/auth/me');
    
    // Set token from localStorage if available
    const extTokenInput = document.getElementById('extTokenInput');
    const extTokenInputProfile = document.getElementById('extTokenInputProfile');
    const realToken = localStorage.getItem('rp_token');
    if (extTokenInput) extTokenInput.value = realToken || 'Пожалуйста, авторизуйтесь для получения токена';
    if (extTokenInputProfile) extTokenInputProfile.value = realToken || 'Пожалуйста, авторизуйтесь для получения токена';

    if (r.ok) {
      const user = await r.json();
      const plan = user.plan || 'free';
      
      const planNames = { 'free': 'Free', 'start': 'Start', 'business': 'Business', 'unlimited': 'Unlimited', 'waybills': 'Накладные' };
      const badgeText = planNames[plan] || plan;
      
      const sbBadge = document.getElementById('sidebarPlanBadge');
      if (sbBadge) sbBadge.textContent = badgeText;
      
      const profBadge = document.getElementById('profilePlanBadge');
      if (profBadge) {
          profBadge.textContent = badgeText;
          if (plan === 'free') {
              profBadge.style.background = '#64748B';
          } else if (plan === 'business' || plan === 'unlimited') {
              profBadge.style.background = 'linear-gradient(135deg, #2563EB, #7C3AED)';
          } else {
              profBadge.style.background = '#10B981';
          }
      }
      
      const profFeatures = document.getElementById('profilePlanFeatures');
      if (profFeatures) {
          if (plan === 'free') {
              profFeatures.innerHTML = '<li>2 сканирования (Kaspi/WB)</li><li>1 AI-аналитика</li><li>Генерация 2-х NTIN</li>';
          } else if (plan === 'start') {
              profFeatures.innerHTML = '<li>Безлимитная генерация NTIN</li><li>Авто-заполнение ИИ для товаров</li>';
          } else if (plan === 'business') {
              profFeatures.innerHTML = '<li>Безлимитная генерация NTIN</li><li>Безлимитный доступ к сканеру Kaspi/WB</li><li>Доступ к AI-Аналитике</li>';
          } else if (plan === 'unlimited') {
              profFeatures.innerHTML = '<li>Полный безлимит на все инструменты</li><li>Доступ к Telegram-боту Quareo</li><li>Радар VIP связок</li>';
          } else if (plan === 'waybills') {
              profFeatures.innerHTML = '<li>Массовая печать накладных (PDF)</li>';
          }
      }
    }
  } catch(e) { console.error('Profile error', e); }
}

function copyExtToken(inputId) {
  const tokenInput = document.getElementById(inputId || 'extTokenInput');
  if (!tokenInput || !tokenInput.value) return;
  tokenInput.select();
  document.execCommand('copy');
  
  const btn = event.target;
  const oldText = btn.textContent;
  btn.textContent = 'Скопировано ✓';
  btn.style.color = '#10B981';
  setTimeout(() => {
    btn.textContent = oldText;
    btn.style.color = '';
  }, 2000);
}

async function loadScanHistory() {
  try {
    const r = await fetch(API + '/api/scanner/niches');
    if (!r.ok) return;
    const scans = await r.json();
    
    const historyList = document.getElementById('scanHistoryList');
    if (historyList) {
        if (!scans || scans.length === 0) {
            historyList.innerHTML = '<div style="font-size: 13px; color: #64748B; text-align: center; padding: 1rem 0;">История пуста</div>';
        } else {
            historyList.innerHTML = scans.slice(0, 3).map(s => {
                const dateStr = new Date(s.analyzed_at).toLocaleDateString('ru-RU');
                return `<div style="border: 1px solid #E2E8F0; padding: 12px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: 600; font-size: 14px; color: #0F172A;">${s.query}</div>
              <div style="font-size: 12px; color: #64748B;">${dateStr} • Оценка: ${s.score}</div>
            </div>
            <button class="btn-action" style="padding: 6px 12px; font-size: 12px;" onclick="window.location.href='scanner.html'">Смотреть</button>
          </div>`;
            }).join('');
        }
    }
    
    const latestScanBlock = document.getElementById('latestScanBlock');
    if (latestScanBlock) {
        if (!scans || scans.length === 0) {
            latestScanBlock.innerHTML = '<div style="font-size: 13px; color: #64748B; text-align: center; padding: 1rem 0;">Нет данных о сканированиях</div>';
        } else {
            const s = scans[0];
            const dateStr = new Date(s.analyzed_at).toLocaleDateString('ru-RU');
            latestScanBlock.innerHTML = `
        <div style="border: 1px solid #E2E8F0; padding: 16px; border-radius: 8px; background: #F8FAFC;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div>
              <div style="font-weight: bold; font-size: 16px; color: #0F172A;">${s.query}</div>
              <div style="font-size: 13px; color: #64748B; margin-top: 4px;">Сканирование от ${dateStr}</div>
            </div>
            <span style="background: #ECFDF5; color: #10B981; padding: 4px 10px; border-radius: 100px; font-size: 12px; font-weight: 600;">Завершено</span>
          </div>
          
          <div style="display: flex; gap: 2rem; margin-top: 16px; border-top: 1px solid #E2E8F0; padding-top: 16px;">
            <div>
              <div style="font-size: 12px; color: #64748B;">Niche Score</div>
              <div style="font-size: 16px; font-weight: 600; color: #0F172A;">${s.score}/100</div>
            </div>
            <div>
              <div style="font-size: 12px; color: #64748B;">Конкуренция</div>
              <div style="font-size: 16px; font-weight: 600; color: #10B981;">${s.sellers} прод.</div>
            </div>
            <div>
              <div style="font-size: 12px; color: #64748B;">Средняя цена</div>
              <div style="font-size: 16px; font-weight: 600; color: #0F172A;">${s.avg_price}</div>
            </div>
          </div>
          <button class="btn-action primary" style="margin-top: 16px;" onclick="window.location.href='scanner.html'">Открыть сканер</button>
        </div>`;
        }
    }
  } catch(e) { console.error('Scan history error', e); }
}

async function loadStats() {
  try {
    const r = await fetch(API + '/api/ntin/stats');
    if (!r.ok) return;
    const d = await r.json();
    document.getElementById('nsTotal').textContent = d.total || 0;
    document.getElementById('nsFilled').textContent = (d.ai_filled || 0) + (d.ready || 0);
    document.getElementById('nsSent').textContent = d.submitted || 0;
    document.getElementById('nsApproved').textContent = d.approved || 0;
    document.getElementById('nsRevision').textContent = (d.revision || 0) + (d.rejected || 0);
  } catch (e) { console.error('Stats error', e); }
}

/* ── Product list ──────────────────────────────────────────── */
async function loadProducts() {
  const wrap = document.getElementById('ntinTableWrap');
  try {
    const r = await fetch(API + '/api/ntin/products');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    allProducts = await r.json();
    renderProducts(allProducts);
  } catch (e) {
    wrap.innerHTML = '<div class="empty-state"><p style="color:#EF4444">Ошибка: ' + e.message + '</p></div>';
  }
}

function renderProducts(products) {
  const wrap = document.getElementById('ntinTableWrap');
  document.getElementById('filterCount').textContent = 'Найдено: ' + products.length;

  if (!products.length) {
    wrap.innerHTML = '<div class="empty-state"><div class="empty-icon">📦</div><p>Нет данных</p></div>';
    return;
  }

  let html = '<table class="ptable"><thead><tr>' +
    '<th style="width:36px"><input type="checkbox" class="check" onchange="toggleAll(this)"></th>' +
    '<th>№</th><th>Наименование</th><th>ТН ВЭД</th><th>NTIN</th><th>Статус</th><th>Действия</th>' +
    '</tr></thead><tbody>';

  products.forEach((p, i) => {
    const s = ST[p.status] || { label: p.status, cls: 'st-draft' };
    const kzLine = p.title_kz ? '<div class="prod-kz">KZ: ' + esc(p.title_kz) + '</div>' : '';
    const revLine = p.revision_comment ? '<div class="prod-kz" style="color:#991B1B">⚠ ' + esc(p.revision_comment) + '</div>' : '';

    html += '<tr>' +
      '<td><input type="checkbox" class="check prod-check" data-id="' + p.id + '" data-status="' + p.status + '"></td>' +
      '<td style="color:#94A3B8;font-size:12px">' + (i + 1) + '</td>' +
      '<td><div class="prod-name">' + esc(p.title_ru) + '</div>' + kzLine + revLine + '</td>' +
      '<td class="mono">' + (p.tn_ved_code || '—') + '</td>' +
      '<td class="mono ntin-val">' + (p.ntin_code || '—') + '</td>' +
      '<td><span class="status-pill ' + s.cls + '">' + s.label + '</span></td>' +
      '<td style="white-space:nowrap">' +
        (p.status === 'draft' ? '<button class="tbl-btn ai" onclick="aiFillOne(\'' + p.id + '\')" title="ИИ-заполнить">🤖</button> ' : '') +
        (['ai_filled','ready','revision'].includes(p.status) ? '<button class="tbl-btn submit" onclick="submitOne(\'' + p.id + '\')" title="Подать в НКТ">📤</button> ' : '') +
        '<button class="tbl-btn del" onclick="deleteOne(\'' + p.id + '\')" title="Удалить">✕</button>' +
      '</td></tr>';
  });
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

/* ── Search & filter ───────────────────────────────────────── */
function filterProducts() {
  const q = (document.getElementById('searchInput').value || '').toLowerCase();
  const status = document.getElementById('filterStatus').value;

  const filtered = allProducts.filter(p => {
    const matchSearch = !q || p.title_ru.toLowerCase().includes(q) ||
      (p.title_kz && p.title_kz.toLowerCase().includes(q)) ||
      (p.barcode && p.barcode.includes(q)) ||
      (p.tn_ved_code && p.tn_ved_code.includes(q));
    const matchStatus = !status || p.status === status;
    return matchSearch && matchStatus;
  });

  renderProducts(filtered);
}

function toggleAll(master) {
  document.querySelectorAll('.prod-check').forEach(c => c.checked = master.checked);
}

/* ── Single actions ────────────────────────────────────────── */
async function aiFillOne(id) {
  try { await fetch(API + '/api/ntin/products/' + id + '/ai-fill', { method: 'POST' }); }
  catch (e) { alert('Ошибка: ' + e.message); }
  loadProducts(); loadStats();
}
async function submitOne(id) {
  try { await fetch(API + '/api/ntin/products/' + id + '/submit', { method: 'POST' }); }
  catch (e) { alert('Ошибка: ' + e.message); }
  loadProducts(); loadStats();
}
async function deleteOne(id) {
  if (!confirm('Удалить товар?')) return;
  try { await fetch(API + '/api/ntin/products/' + id, { method: 'DELETE' }); }
  catch (e) { alert('Ошибка: ' + e.message); }
  loadProducts(); loadStats();
}

/* ── Modal ─────────────────────────────────────────────────── */
function addProductModal() { document.getElementById('addModal').style.display = 'flex'; }
function closeModal() { document.getElementById('addModal').style.display = 'none'; }

async function createProduct() {
  const data = {
    title_ru: document.getElementById('mTitleRu').value.trim(),
    description_ru: document.getElementById('mDescRu').value.trim() || null,
    barcode: document.getElementById('mBarcode').value.trim() || null,
    brand: document.getElementById('mBrand').value.trim() || null,
    price: parseFloat(document.getElementById('mPrice').value) || null,
    weight_kg: parseFloat(document.getElementById('mWeight').value) || null,
  };
  if (!data.title_ru) { alert('Введите название товара'); return; }

  try {
    const r = await fetch(API + '/api/ntin/products', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Ошибка'); }
  } catch (e) { alert('Ошибка: ' + e.message); return; }

  closeModal();
  ['mTitleRu','mDescRu','mBarcode','mBrand','mPrice','mWeight'].forEach(id => document.getElementById(id).value = '');
  loadProducts(); loadStats();
}

/* ═══════════════════════════════════════════════════════════════
   BULK OPERATIONS
   ═══════════════════════════════════════════════════════════════ */

function showProgress(label, current, total) {
  document.getElementById('bulkProgress').style.display = '';
  document.getElementById('bulkLabel').textContent = label;
  document.getElementById('bulkCount').textContent = current + '/' + total;
  document.getElementById('bulkBarFill').style.width = (total ? (current / total * 100) : 0) + '%';
}
function hideProgress() { document.getElementById('bulkProgress').style.display = 'none'; }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ── Bulk import demo ──────────────────────────────────────── */
async function bulkImportDemo() {
  const btn = document.getElementById('btnImport');
  btn.disabled = true; btn.textContent = '⏳ Импорт...';

  const items = [
    { title_ru: 'Увлажнитель воздуха Xiaomi Smart Humidifier 2 Lite', brand: 'Xiaomi', price: 24900, weight_kg: 1.8 },
    { title_ru: 'Беспроводные наушники Apple AirPods Pro 2', brand: 'Apple', price: 112500, weight_kg: 0.05 },
    { title_ru: 'Фитнес-браслет Xiaomi Smart Band 8', brand: 'Xiaomi', price: 18200, weight_kg: 0.03 },
    { title_ru: 'Робот-пылесос Dreame D10s Pro', brand: 'Dreame', price: 149900, weight_kg: 3.7 },
    { title_ru: 'Электрический чайник Tefal Safe Tea 1.7L', brand: 'Tefal', price: 14500, weight_kg: 1.1 },
    { title_ru: 'Портативная колонка JBL Flip 6', brand: 'JBL', price: 42900, weight_kg: 0.55 },
    { title_ru: 'Кофемашина DeLonghi Magnifica S', brand: 'DeLonghi', price: 245000, weight_kg: 9.5 },
    { title_ru: 'Электросамокат Ninebot KickScooter Max G2', brand: 'Ninebot', price: 349000, weight_kg: 19.3 },
    { title_ru: 'Повербанк Baseus Adaman 20000mAh', brand: 'Baseus', price: 12900, weight_kg: 0.42 },
    { title_ru: 'Кабель USB-C Lightning Apple 1m', brand: 'Apple', price: 8900, weight_kg: 0.03 },
  ];

  for (let i = 0; i < items.length; i++) {
    showProgress('📥 Импорт товаров из Kaspi...', i + 1, items.length);
    try {
      await fetch(API + '/api/ntin/products', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(items[i])
      });
    } catch (e) { console.error('Import error:', e); }
    await sleep(150);
  }

  hideProgress();
  btn.disabled = false; btn.textContent = '📥 Импорт';
  loadProducts(); loadStats();
}

/* ── Bulk AI Fill ──────────────────────────────────────────── */
async function bulkAiFill() {
  const btn = document.getElementById('btnAiFill');
  btn.disabled = true; btn.textContent = '⏳ Заполняю...';

  const r = await fetch(API + '/api/ntin/products');
  const products = await r.json();
  const drafts = products.filter(p => p.status === 'draft');

  if (!drafts.length) {
    alert('Нет черновиков для заполнения');
    btn.disabled = false; btn.textContent = '🤖 ИИ-заполнить все'; return;
  }

  for (let i = 0; i < drafts.length; i++) {
    showProgress('🤖 ИИ заполняет ТН ВЭД + перевод на KZ...', i + 1, drafts.length);
    try { await fetch(API + '/api/ntin/products/' + drafts[i].id + '/ai-fill', { method: 'POST' }); }
    catch (e) { console.error(e); }
    await sleep(200);
  }

  hideProgress();
  btn.disabled = false; btn.textContent = '🤖 ИИ-заполнить все';
  loadProducts(); loadStats();
}

/* ── Bulk Submit to НКТ ────────────────────────────────────── */
async function bulkSubmitNkt() {
  const btn = document.getElementById('btnSubmitAll');
  btn.disabled = true; btn.textContent = '⏳ Подаю...';

  const r = await fetch(API + '/api/ntin/products');
  const products = await r.json();
  const ready = products.filter(p => ['ai_filled', 'ready', 'revision'].includes(p.status));

  if (!ready.length) {
    alert('Нет товаров для подачи');
    btn.disabled = false; btn.textContent = '📤 Подать все в НКТ'; return;
  }

  if (!confirm('Отправить ' + ready.length + ' товар(ов) в НКТ?')) {
    btn.disabled = false; btn.textContent = '📤 Подать все в НКТ'; return;
  }

  for (let i = 0; i < ready.length; i++) {
    showProgress('📤 Подача в Национальный каталог...', i + 1, ready.length);
    try { await fetch(API + '/api/ntin/products/' + ready[i].id + '/submit', { method: 'POST' }); }
    catch (e) { console.error(e); }
    await sleep(300);
  }

  hideProgress();
  btn.disabled = false; btn.textContent = '📤 Подать все в НКТ';
  loadProducts(); loadStats();
}

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  updateShopBadge();
  
  // Handle direct links to specific pages
  const hash = window.location.hash.replace('#', '');
  if (hash && PAGE_TITLES[hash]) {
    showPage(hash);
  } else {
    showPage('connect');
    loadProducts();
    loadStats();
  }
  
  loadUserProfile();
  loadScanHistory();
});

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
  
  if (document.getElementById('calcPrice')) {
    calculateProfit();
  }
});

/* ── Kaspi Calculator Logic ───────────────────────────────── */
function getDeliveryCost(price, weight, zone, category) {
  if (category === 'tire_light') {
    return zone === 'city' ? 1217 : zone === 'kz' ? 1913 : 1565;
  }
  if (category === 'tire_heavy') {
    return zone === 'city' ? 4871 : zone === 'kz' ? 7016 : 6669;
  }

  if (price <= 10000) {
    if (price <= 1000) return 57;
    if (price <= 3000) return 173;
    if (price <= 5000) return 231;
    if (price <= 10000) return zone === 'city' ? 811 : 927;
  } else {
    if (weight <= 5) return zone === 'city' ? 1275 : zone === 'kz' ? 1507 : 1971;
    if (weight <= 15) return zone === 'city' ? 1565 : zone === 'kz' ? 1971 : 2146;
    if (weight <= 30) return zone === 'city' ? 2667 : zone === 'kz' ? 4175 : 3653;
    if (weight <= 60) return zone === 'city' ? 3363 : zone === 'kz' ? 6553 : 4175;
    if (weight <= 100) return zone === 'city' ? 4813 : zone === 'kz' ? 9917 : 6495;
    return zone === 'city' ? 7481 : zone === 'kz' ? 13919 : 9801;
  }
}

function calculateProfit() {
  const price = parseFloat(document.getElementById('calcPrice').value) || 0;
  const cost = parseFloat(document.getElementById('calcCost').value) || 0;
  const weight = parseFloat(document.getElementById('calcWeight').value) || 0;
  const zone = document.getElementById('calcZone').value;
  const category = document.getElementById('calcCategory').value;
  
  const commKaspiPerc = parseFloat(document.getElementById('calcCommKaspi').value) || 0;
  const commBankPerc = parseFloat(document.getElementById('calcCommBank').value) || 0;
  const packageCost = parseFloat(document.getElementById('calcPackage').value) || 0;

  const totalCommPerc = commKaspiPerc + commBankPerc;
  const commissionAmount = price * (totalCommPerc / 100);
  
  const delivery = getDeliveryCost(price, weight, zone, category);
  
  const profit = price - commissionAmount - delivery - packageCost - cost;
  
  const expenses = cost + delivery + packageCost;
  const margin = price > 0 ? (profit / price) * 100 : 0;
  const roi = expenses > 0 ? (profit / expenses) * 100 : 0;

  const fmt = (num) => Math.round(num).toLocaleString('ru-RU') + ' ₸';

  document.getElementById('resRevenue').textContent = fmt(price);
  document.getElementById('resCommission').textContent = '- ' + fmt(commissionAmount);
  document.getElementById('resDelivery').textContent = '- ' + fmt(delivery);
  document.getElementById('resPackage').textContent = '- ' + fmt(packageCost);
  document.getElementById('resCost').textContent = '- ' + fmt(cost);
  
  const elProfit = document.getElementById('resProfit');
  elProfit.textContent = fmt(profit);
  elProfit.style.color = profit > 0 ? '#10B981' : '#EF4444';

  const elMargin = document.getElementById('resMargin');
  elMargin.textContent = margin.toFixed(1) + '%';
  elMargin.style.color = margin > 15 ? '#3B82F6' : (margin > 0 ? '#F59E0B' : '#EF4444');

  const elRoi = document.getElementById('resRoi');
  elRoi.textContent = roi.toFixed(1) + '%';
  elRoi.style.color = roi > 30 ? '#8B5CF6' : (roi > 0 ? '#F59E0B' : '#EF4444');
}
