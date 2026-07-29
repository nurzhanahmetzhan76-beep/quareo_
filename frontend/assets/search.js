/*
 * Quareo Search — real-time cross-marketplace search.
 * Fetches live results from /api/search (Kaspi + Wildberries scrapers).
 * Only renders fields the backend genuinely returns — no fabricated data.
 */
(function () {
  'use strict';

  const DEFAULT_QUERY = 'Dyson V15';
  const $ = (selector, root = document) => root.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
  const formatPrice = (value) => `${new Intl.NumberFormat('ru-RU').format(value)} ₸`;

  const API_BASE = (typeof RP_API_BASE !== 'undefined' ? RP_API_BASE : window.location.origin) + '/api/search';

  async function fetchSearchResult(query) {
    const url = `${API_BASE}?query=${encodeURIComponent(query)}`;
    const resp = await fetch(url);
    if (!resp.ok) {
      throw new Error(`Ошибка поиска (${resp.status})`);
    }
    return resp.json();
  }

  const LOGO_MAP = {
    kaspi: 'assets/logos/kaspi.png',
    wildberries: 'assets/logos/wb.png',
    ozon: 'assets/logos/ozon.png',
  };

  function marketplaceLogoKey(marketplace) {
    const key = (marketplace || '').toLowerCase();
    if (key.includes('kaspi')) return 'kaspi';
    if (key.includes('wildberries')) return 'wildberries';
    if (key.includes('ozon')) return 'ozon';
    return null;
  }

  function renderOffer(offer, index) {
    const ratingBlock = offer.rating
      ? `<span class="offer-card__rating">★ ${escapeHtml(offer.rating)}${offer.review_count ? ` (${escapeHtml(offer.review_count)})` : ''}</span>`
      : '';
    const logoKey = marketplaceLogoKey(offer.marketplace);
    const letterFallback = escapeHtml(offer.marketplace[0]);
    const markInner = logoKey
      ? `<img src="${LOGO_MAP[logoKey]}" alt="${escapeHtml(offer.marketplace)}" loading="lazy" onerror="this.replaceWith(document.createTextNode('${letterFallback}'))">`
      : letterFallback;
    return `<article class="q-card offer-card${offer.best ? ' offer-card--best' : ''}">
      ${offer.best ? '<span class="q-tag q-tag--success offer-card__badge">Лучшая цена</span>' : ''}
      <div class="offer-card__top"><span class="marketplace-name"><i class="marketplace-name__mark">${markInner}</i>${escapeHtml(offer.marketplace)}</span>${ratingBlock}</div>
      <h4 class="offer-card__title">${escapeHtml(offer.title)}</h4>
      <div class="offer-card__price">${formatPrice(offer.price_kzt)}</div>
      <div class="offer-card__details"><span>${escapeHtml(offer.seller || 'Продавец не указан')}</span></div>
      <a class="q-button${offer.best ? '' : ' q-button-secondary'}" href="${escapeHtml(offer.url)}" target="_blank" rel="noopener noreferrer">Перейти к предложению</a>
    </article>`;
  }

  function renderResults(result) {
    const { query, offers, sources_checked, coming_soon, message } = result;

    if (!offers || offers.length === 0) {
      return `
        <div class="result-heading">
          <div><p class="q-eyebrow">Результаты поиска</p><h2 class="q-section-title" id="results-title">По запросу «${escapeHtml(query)}» ничего не нашли</h2></div>
        </div>
        <article class="q-card">
          <p>${escapeHtml(message || 'Попробуйте другой запрос или проверьте написание.')}</p>
          <p style="margin-top:12px;color:var(--text-2, #8a8a99);font-size:13px;">Проверено: ${escapeHtml((sources_checked || []).join(', '))}</p>
        </article>`;
    }

    const comingSoonNote = coming_soon && coming_soon.length
      ? `<p class="result-heading__note">Скоро подключим: ${escapeHtml(coming_soon.join(', '))}</p>`
      : '';

    return `
      <div class="result-heading">
        <div><p class="q-eyebrow">Результаты поиска</p><h2 class="q-section-title" id="results-title">Предложения по запросу «${escapeHtml(query)}»</h2></div>
        <p class="result-heading__note">Реальные данные · ${escapeHtml((sources_checked || []).join(', '))}</p>
      </div>

      <section class="search-block" aria-labelledby="offers-title">
        <header class="search-block__header"><h3 class="search-block__title" id="offers-title">Найденные предложения</h3><p class="search-block__meta">${offers.length} предложений, отсортировано по цене</p></header>
        <div class="offers-grid">${offers.map(renderOffer).join('')}</div>
      </section>

      ${comingSoonNote ? `<section class="search-block"><p class="search-block__meta">${comingSoonNote}</p></section>` : ''}
    `;
  }

  function renderLoading() {
    return `<div class="result-heading"><div><p class="q-eyebrow">Ищем...</p><h2 class="q-section-title">Проверяем маркетплейсы</h2></div></div>
      <article class="q-card"><p>Это может занять несколько секунд — мы заходим на реальные страницы поиска.</p></article>`;
  }

  function renderError(err) {
    return `<div class="result-heading"><div><p class="q-eyebrow">Ошибка</p><h2 class="q-section-title">Не удалось выполнить поиск</h2></div></div>
      <article class="q-card"><p>${escapeHtml(err.message || 'Попробуйте ещё раз через минуту.')}</p></article>`;
  }

  async function showResults(query) {
    const resultRoot = $('#searchResults');
    const input = $('#productSearchInput');
    const normalizedQuery = query.trim() || DEFAULT_QUERY;
    input.value = normalizedQuery;

    resultRoot.setAttribute('aria-busy', 'true');
    resultRoot.innerHTML = renderLoading();

    try {
      const result = await fetchSearchResult(normalizedQuery);
      resultRoot.innerHTML = renderResults(result);
    } catch (err) {
      console.error('Quareo Search error:', err);
      resultRoot.innerHTML = renderError(err);
    } finally {
      resultRoot.setAttribute('aria-busy', 'false');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = $('#productSearchForm');
    const input = $('#productSearchInput');
    const submitButton = form?.querySelector('button[type="submit"]');

    showResults(input.value);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      showResults(input.value);
    });

    if (submitButton) {
      submitButton.addEventListener('click', (event) => {
        event.preventDefault();
        form.requestSubmit();
      });
    }

    document.querySelectorAll('[data-query]').forEach((button) => {
      button.addEventListener('click', () => {
        input.value = button.dataset.query;
        showResults(input.value);
      });
    });
  });
}());
