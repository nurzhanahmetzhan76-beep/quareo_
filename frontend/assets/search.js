/*
 * Quareo Search UI data adapter.
 * Replace getMockSearchResult() with a future API client that returns the same
 * SearchResult shape; all rendering and layout can stay unchanged.
 */
(function () {
  'use strict';

  const DEFAULT_QUERY = 'Dyson V15';
  const $ = (selector, root = document) => root.querySelector(selector);
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
  const formatPrice = (value) => `${new Intl.NumberFormat('ru-RU').format(value)} ₸`;

  /** @returns {SearchResult} */
  function getMockSearchResult(query) {
    return {
      query: query || DEFAULT_QUERY,
      product: {
        name: 'Dyson V15 Detect Absolute',
        category: 'Вертикальные пылесосы',
        matchedOffers: 27,
        updatedAt: 'только что'
      },
      offers: [
        { marketplace: 'Kaspi', mark: 'K', price: 319990, oldPrice: 338990, saving: 'На 19 000 ₸ выгоднее среднего', seller: 'TechPoint', delivery: 'Завтра, бесплатно', best: true },
        { marketplace: 'Wildberries', mark: 'W', price: 327490, oldPrice: 339990, saving: 'На 11 500 ₸ выгоднее среднего', seller: 'Home Select', delivery: '2–3 дня' },
        { marketplace: 'Ozon', mark: 'O', price: 331990, oldPrice: 345990, saving: 'На 7 000 ₸ выгоднее среднего', seller: 'Electro Store', delivery: '3–5 дней' }
      ],
      seller: {
        name: 'TechPoint', rating: '4.9', reviews: '2 184 отзыва', delivery: 'Завтра', warranty: '12 месяцев', reliability: '98%', returnRate: '1.2%'
      },
      reviews: {
        positive: ['Тихий даже в турборежиме', 'Мощная уборка ковров', 'Качественная сборка'],
        negative: ['Тяжёлый для долгой уборки', 'Дорогие расходники'],
        conclusion: 'Отличный выбор для ежедневного использования.'
      },
      priceHistory: {
        labels: ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'сейчас'],
        values: [346, 340, 343, 334, 338, 328, 320],
        advice: 'Сейчас хорошее время для покупки.'
      },
      alternatives: [
        { name: 'Xiaomi G20 Max', description: 'Мощный беспроводной пылесос', match: 91, mark: 'X' },
        { name: 'Samsung Jet 85', description: 'Премиальная альтернатива', match: 88, mark: 'S' },
        { name: 'Bosch Unlimited 7', description: 'Для дома с животными', match: 84, mark: 'B' }
      ],
      score: {
        total: 96,
        factors: [
          { label: 'Цена', value: 98 },
          { label: 'Отзывы', value: 95 },
          { label: 'Надёжность', value: 97 },
          { label: 'Доставка', value: 91 },
          { label: 'Качество', value: 96 }
        ]
      }
    };
  }

  function createPriceChart(history) {
    const width = 520;
    const height = 180;
    const pad = { top: 17, right: 8, bottom: 25, left: 8 };
    const values = history.values;
    const min = Math.min(...values) - 4;
    const max = Math.max(...values) + 4;
    const x = (index) => pad.left + index * ((width - pad.left - pad.right) / (values.length - 1));
    const y = (value) => pad.top + (max - value) * ((height - pad.top - pad.bottom) / (max - min));
    const points = values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(' ');
    const area = `${pad.left},${height - pad.bottom} ${points} ${x(values.length - 1)},${height - pad.bottom}`;
    const grid = [0.2, 0.55, 0.9].map((ratio) => {
      const gridY = pad.top + (height - pad.top - pad.bottom) * ratio;
      return `<line class="price-chart__grid" x1="${pad.left}" x2="${width - pad.right}" y1="${gridY}" y2="${gridY}"/>`;
    }).join('');
    const labels = history.labels.map((label, index) => `<text class="price-chart__axis" x="${x(index)}" y="${height - 5}" text-anchor="middle">${label}</text>`).join('');
    const lastIndex = values.length - 1;

    return `<div class="price-chart" aria-label="График истории цены"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Цена снижается до текущего значения">${grid}<polygon class="price-chart__area" points="${area}"/><polyline class="price-chart__line" points="${points}"/><circle class="price-chart__dot" cx="${x(lastIndex)}" cy="${y(values[lastIndex])}" r="5"/>${labels}</svg></div>`;
  }

  function renderOffer(offer) {
    return `<article class="q-card offer-card${offer.best ? ' offer-card--best' : ''}">
      ${offer.best ? '<span class="q-tag q-tag--success offer-card__badge">Лучшая цена</span>' : ''}
      <div class="offer-card__top"><span class="marketplace-name"><i class="marketplace-name__mark">${escapeHtml(offer.mark)}</i>${escapeHtml(offer.marketplace)}</span><span class="offer-card__availability">В наличии</span></div>
      <div class="offer-card__price">${formatPrice(offer.price)} <small>за шт.</small></div>
      <span class="offer-card__saving">${escapeHtml(offer.saving)}</span>
      <div class="offer-card__details"><span>${escapeHtml(offer.seller)}</span><span>Доставка: ${escapeHtml(offer.delivery)}</span></div>
      <button class="q-button${offer.best ? '' : ' q-button-secondary'}" type="button" data-offer-link="${escapeHtml(offer.marketplace)}">Перейти к предложению</button>
    </article>`;
  }

  function renderScore(score) {
    return `<article class="q-card score-card">
      <h3>Quareo Score</h3>
      <p class="q-card__description">Итоговая оценка предложения</p>
      <div class="score-ring" style="--score:${score.total}%"><span class="score-ring__value">${score.total}<small>из 100</small></span></div>
      <ul class="score-list">${score.factors.map((factor) => `<li><span>${escapeHtml(factor.label)}</span><span class="q-progress" style="--q-progress:${factor.value}%"><span></span></span><b>${factor.value}</b></li>`).join('')}</ul>
    </article>`;
  }

  function renderResults(result) {
    const { product, offers, seller, reviews, priceHistory, alternatives, score } = result;
    return `
      <div class="result-heading">
        <div><p class="q-eyebrow">Результаты поиска</p><h2 class="q-section-title" id="results-title">Выгодные предложения для вас</h2></div>
        <p class="result-heading__note">Демо-данные · обновлено ${escapeHtml(product.updatedAt)}</p>
      </div>

      <article class="q-card product-summary">
        <div class="product-summary__visual" aria-hidden="true"></div>
        <div><p class="product-summary__eyebrow">${escapeHtml(product.category)}</p><h2>${escapeHtml(product.name)}</h2><div class="product-summary__meta"><span>${product.matchedOffers} предложений</span><span>3 маркетплейса</span></div></div>
        <span class="q-tag q-tag--success">Совпадение подтверждено</span>
      </article>

      <section class="search-block" aria-labelledby="offers-title">
        <header class="search-block__header"><h3 class="search-block__title" id="offers-title">Лучшие цены</h3><p class="search-block__meta">Топ-3 из ${product.matchedOffers} найденных предложений</p></header>
        <div class="offers-grid">${offers.map(renderOffer).join('')}</div>
      </section>

      <section class="search-block insights-grid" aria-label="Продавец и AI-анализ отзывов">
        <article class="q-card seller-card">
          <h3>Лучший продавец</h3><p class="q-card__description">Выбран по цене, сервису и надёжности</p>
          <div class="seller-card__top"><div class="seller-rating">${seller.rating}<small>из 5</small></div><div><p class="seller-name">${escapeHtml(seller.name)}</p><p class="seller-reviews">${escapeHtml(seller.reviews)}</p></div></div>
          <div class="seller-metrics"><div class="seller-metric"><span>Доставка</span><b>${escapeHtml(seller.delivery)}</b></div><div class="seller-metric"><span>Гарантия</span><b>${escapeHtml(seller.warranty)}</b></div><div class="seller-metric"><span>Надёжность</span><b>${escapeHtml(seller.reliability)}</b></div><div class="seller-metric"><span>Возвраты</span><b>${escapeHtml(seller.returnRate)}</b></div></div>
        </article>
        <article class="q-card review-card">
          <h3>AI-анализ отзывов</h3><p class="q-card__description">Главные темы из отзывов покупателей</p>
          <div class="review-card__content"><ul class="review-list"><h4>Плюсы</h4>${reviews.positive.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul><ul class="review-list review-list--negative"><h4>Минусы</h4>${reviews.negative.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>
          <p class="review-conclusion"><strong>Вывод.</strong> ${escapeHtml(reviews.conclusion)}</p>
        </article>
      </section>

      <section class="search-block analysis-grid" aria-label="История цены и оценка Quareo">
        <article class="q-card history-card"><h3>История цены</h3><p class="q-card__description">Цена на лучшее предложение за последние 6 месяцев</p><div class="history-card__body">${createPriceChart(priceHistory)}<aside class="purchase-advice"><span class="purchase-advice__label">AI-рекомендация</span><p>${escapeHtml(priceHistory.advice)}</p></aside></div></article>
        ${renderScore(score)}
      </section>

      <section class="search-block" aria-labelledby="alternatives-title">
        <header class="search-block__header"><h3 class="search-block__title" id="alternatives-title">Лучшие альтернативы</h3><p class="search-block__meta">Похожие товары с хорошими оценками</p></header>
        <div class="alternatives-grid">${alternatives.map((alternative) => `<article class="q-card alternative-card"><div class="alternative-card__icon">${escapeHtml(alternative.mark)}</div><div><h4>${escapeHtml(alternative.name)}</h4><p>${escapeHtml(alternative.description)}</p></div><span class="alternative-card__match">${alternative.match}% схожести</span></article>`).join('')}</div>
      </section>

      <section class="search-block" aria-label="Действие с выбранным предложением">
        <div class="q-card search-cta"><div><h2>Готовы купить выгоднее?</h2><p>Мы выбрали предложение с лучшим балансом цены, доставки и надёжности продавца.</p></div><button class="q-button" type="button" data-offer-link="Kaspi">Перейти к предложению</button></div>
      </section>`;
  }

  function showResults(query, options = {}) {
    const resultRoot = $('#searchResults');
    const input = $('#productSearchInput');
    const normalizedQuery = query.trim() || DEFAULT_QUERY;
    input.value = normalizedQuery;
    resultRoot.setAttribute('aria-busy', 'true');
    resultRoot.innerHTML = renderResults(getMockSearchResult(normalizedQuery));
    resultRoot.setAttribute('aria-busy', 'false');

    resultRoot.querySelectorAll('[data-offer-link]').forEach((button) => {
      button.addEventListener('click', () => {
        button.textContent = 'Ссылка появится с подключением маркетплейса';
        button.disabled = true;
      }, { once: true });
    });

    if (options.scroll) $('#search-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = $('#productSearchForm');
    const input = $('#productSearchInput');
    showResults(input.value);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      showResults(input.value, { scroll: true });
    });

    document.querySelectorAll('[data-query]').forEach((button) => {
      button.addEventListener('click', () => {
        input.value = button.dataset.query;
        showResults(input.value, { scroll: true });
      });
    });
  });
}());
