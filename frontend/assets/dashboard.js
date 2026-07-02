/* ============================================================
   Quareo Dashboard JS — Bulk NTIN automation engine
   ============================================================ */
const API = window.location.origin;
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
  connect: 'Подключение магазина', ntin: 'NTIN Маркировка',
  robot: 'Робот-репрайсер', analytics: 'Аналитика магазина',
  products: 'Товары без продавцов', cost: 'Себестоимость',
  reviews: 'Отзывы', waybills: 'Накладные',
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
  // Load NTIN data on startup since it's the default page
  loadProducts();
  loadStats();
});
