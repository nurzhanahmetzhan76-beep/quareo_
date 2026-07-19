/*
  kaspi_content.js
  Инжектируется в страницу Kaspi Кабинет Продавца (kaspi.kz/mc).
  
  Задачи:
  1. Сканирует страницу на наличие новых вопросов покупателей
  2. Отправляет вопросы на сервер Quareo для генерации ИИ-ответа
  3. Вставляет ответ в поле и (опционально) автоматически отправляет
  
  ВАЖНО: Расширение работает ТОЛЬКО когда вкладка Kaspi открыта в браузере.
  Если вкладка закрыта — сканирование останавливается.
*/

(function() {
  'use strict';

  const SCAN_INTERVAL = 10000; // Проверять каждые 10 секунд
  const PROCESSED_KEY = 'quareo_processed_questions';

  let isEnabled = false;
  let autoSend = false;
  let apiBase = '';
  let authToken = '';

  // ── Загрузка настроек из chrome.storage ──────────────────────────────

  function loadSettings() {
    return new Promise(resolve => {
      chrome.storage.local.get(
        ['quareo_enabled', 'quareo_auto_send', 'quareo_api_base', 'quareo_token'],
        (data) => {
          isEnabled = data.quareo_enabled !== false; // default: true
          autoSend = data.quareo_auto_send === true;
          apiBase = data.quareo_api_base || 'https://quareo.pro';
          authToken = data.quareo_token || '';
          resolve();
        }
      );
    });
  }

  // ── Получение обработанных вопросов ──────────────────────────────────

  function getProcessedIds() {
    try {
      return JSON.parse(localStorage.getItem(PROCESSED_KEY) || '[]');
    } catch { return []; }
  }

  function markProcessed(id) {
    const ids = getProcessedIds();
    ids.push(id);
    // Храним последние 500
    if (ids.length > 500) ids.splice(0, ids.length - 500);
    localStorage.setItem(PROCESSED_KEY, JSON.stringify(ids));
  }

  // ── Поиск вопросов на странице ──────────────────────────────────────

  function findQuestions() {
    const questions = [];
    const processedIds = getProcessedIds();

    // Kaspi merchant cabinet может иметь разные структуры.
    // Ищем блоки с вопросами по общим паттернам.
    
    // Паттерн 1: Блоки с вопросами покупателей (раздел "Вопросы")
    const questionBlocks = document.querySelectorAll(
      '[class*="question"], [class*="Question"], ' +
      '[class*="review-item"], [class*="ReviewItem"], ' +
      '[class*="inquiry"], [class*="Inquiry"], ' +
      '[class*="chat-message"], [class*="ChatMessage"], ' +
      '[class*="conversation-item"], [class*="message-item"], ' +
      '[data-testid*="question"], [data-testid*="review"], [data-testid*="chat-message"]'
    );

    questionBlocks.forEach(block => {
      const textContent = block.textContent?.trim() || '';
      if (!textContent || textContent.length < 10) return;

      // Ищем имя покупателя
      const customerName = extractCustomerName(block);

      const id = hashString((customerName || 'unknown') + '_' + textContent.substring(0, 100));
      if (processedIds.includes(id)) return;

      // Ищем текст вопроса
      const questionText = extractQuestionText(block);
      if (!questionText) return;

      // Ищем название товара
      const productName = extractProductName(block);

      // Проверяем, есть ли уже ответ
      const hasAnswer = checkHasAnswer(block);
      if (hasAnswer) {
        markProcessed(id);
        return;
      }

      // Ищем поле для ввода ответа
      const answerInput = findAnswerInput(block);

      questions.push({
        id,
        text: questionText,
        productName,
        customerName,
        element: block,
        answerInput,
      });
    });

    return questions;
  }

  function extractQuestionText(block) {
    // Пробуем разные селекторы для текста вопроса
    const selectors = [
      '[class*="question-text"]', '[class*="questionText"]',
      '[class*="review-text"]', '[class*="reviewText"]',
      '[class*="message-text"]', '[class*="messageText"]',
      '[class*="chat-text"]', '[class*="chat-message-text"]', '[class*="bubble"]',
      '[class*="body"]', '[class*="content"]',
      'p', '.text',
    ];

    for (const sel of selectors) {
      const el = block.querySelector(sel);
      if (el && el.textContent.trim().length > 5) {
        return el.textContent.trim();
      }
    }

    // Fallback: берём весь текст блока, но обрезаем
    const full = block.textContent?.trim();
    if (full && full.length > 10 && full.length < 500) {
      return full;
    }
    return null;
  }

  function extractProductName(block) {
    const selectors = [
      '[class*="product-name"]', '[class*="productName"]',
      '[class*="product-title"]', '[class*="productTitle"]',
      '[class*="item-name"]', '[class*="itemName"]',
      'h3', 'h4',
    ];
    for (const sel of selectors) {
      const el = block.querySelector(sel);
      if (el) return el.textContent.trim();
    }
    return null;
  }

  function extractCustomerName(block) {
    const selectors = [
      '[class*="author"]', '[class*="Author"]',
      '[class*="customer"]', '[class*="Customer"]',
      '[class*="user-name"]', '[class*="userName"]',
    ];
    for (const sel of selectors) {
      const el = block.querySelector(sel);
      if (el) return el.textContent.trim();
    }
    return null;
  }

  function checkHasAnswer(block) {
    const answerSelectors = [
      '[class*="answer"]', '[class*="Answer"]',
      '[class*="reply"]', '[class*="Reply"]',
      '[class*="response"]', '[class*="Response"]',
    ];
    for (const sel of answerSelectors) {
      const el = block.querySelector(sel);
      if (el && el.textContent.trim().length > 5) return true;
    }
    return false;
  }

  function findAnswerInput(block) {
    // Ищем textarea или input для ответа
    const inputs = block.querySelectorAll('textarea, input[type="text"], [contenteditable="true"]');
    if (inputs.length > 0) return inputs[0];

    // Ищем кнопку "Ответить", чтобы открыть поле
    const replyBtn = block.querySelector(
      'button[class*="reply"], button[class*="Reply"], ' +
      'button[class*="answer"], button[class*="Answer"], ' +
      'button[class*="send"], button[class*="Send"], ' +
      'a[class*="reply"], a[class*="answer"]'
    );
    if (replyBtn) return { type: 'button', element: replyBtn };

    return null;
  }

  // ── Запрос ИИ-ответа с сервера ──────────────────────────────────────

  async function getAIReply(question) {
    if (!authToken) {
      console.warn('[Quareo] Нет токена авторизации. Настройте расширение.');
      return null;
    }

    try {
      const resp = await fetch(apiBase + '/api/autoreply/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + authToken,
        },
        body: JSON.stringify({
          question: question.text,
          product_name: question.productName,
          customer_name: question.customerName,
          question_id: question.id,
        }),
      });

      if (!resp.ok) {
        console.error('[Quareo] Ошибка API:', resp.status);
        return null;
      }

      const data = await resp.json();
      return data.reply;
    } catch (e) {
      console.error('[Quareo] Ошибка сети:', e);
      return null;
    }
  }

  // ── Вставка ответа в поле ──────────────────────────────────────────

  function insertReply(question, replyText) {
    const input = question.answerInput;
    if (!input) {
      console.log('[Quareo] Не найдено поле для ответа. Вопрос:', question.text.substring(0, 50));
      showFloatingReply(question.element, replyText);
      return;
    }

    if (input.type === 'button') {
      // Сначала кликнуть кнопку "Ответить", потом вставить текст
      input.element.click();
      setTimeout(() => {
        const newInput = question.element.querySelector('textarea, input[type="text"], [contenteditable="true"]');
        if (newInput) {
          setInputValue(newInput, replyText);
          if (autoSend) {
            setTimeout(() => clickSendButton(question.element), 500);
          }
        }
      }, 800);
    } else {
      setInputValue(input, replyText);
      if (autoSend) {
        setTimeout(() => clickSendButton(question.element), 500);
      }
    }
  }

  function setInputValue(input, text) {
    if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
      input.value = text;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    } else if (input.contentEditable === 'true') {
      input.textContent = text;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    // Highlight the field so seller notices
    input.style.boxShadow = '0 0 8px rgba(37, 99, 235, 0.5)';
    setTimeout(() => { input.style.boxShadow = ''; }, 3000);
  }

  function clickSendButton(block) {
    const sendBtn = block.querySelector(
      'button[type="submit"], button[class*="send"], button[class*="Send"], ' +
      'button[class*="submit"], button[class*="Submit"]'
    );
    if (sendBtn) {
      sendBtn.click();
      console.log('[Quareo] Ответ отправлен автоматически');
    }
  }

  // ── Всплывающее окно с ответом (если поле не найдено) ───────────────

  function showFloatingReply(nearElement, replyText) {
    const popup = document.createElement('div');
    popup.style.cssText = `
      position: absolute; z-index: 99999;
      background: #fff; border: 2px solid #2563eb;
      border-radius: 12px; padding: 16px 20px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.15);
      max-width: 400px; font-size: 14px; color: #1e293b;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    `;
    popup.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
        <span style="background: #2563eb; color: #fff; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;">QUAREO AI</span>
        <span style="color: #94a3b8; font-size: 12px;">Предложенный ответ</span>
      </div>
      <div style="background: #f1f5f9; padding: 12px; border-radius: 8px; margin-bottom: 12px; line-height: 1.5;">${escapeHtml(replyText)}</div>
      <div style="display: flex; gap: 8px;">
        <button id="quareo-copy-btn" style="flex:1;padding:8px 12px;background:#2563eb;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;">📋 Копировать</button>
        <button id="quareo-close-btn" style="padding:8px 12px;background:#e2e8f0;color:#64748b;border:none;border-radius:8px;cursor:pointer;font-size:13px;">✕</button>
      </div>
    `;

    nearElement.style.position = 'relative';
    nearElement.appendChild(popup);

    popup.querySelector('#quareo-copy-btn').addEventListener('click', () => {
      navigator.clipboard.writeText(replyText).then(() => {
        popup.querySelector('#quareo-copy-btn').textContent = '✓ Скопировано!';
        setTimeout(() => popup.remove(), 1500);
      });
    });

    popup.querySelector('#quareo-close-btn').addEventListener('click', () => {
      popup.remove();
    });

    // Auto-remove after 30s
    setTimeout(() => { if (popup.parentNode) popup.remove(); }, 30000);
  }

  // ── Статус-бар ──────────────────────────────────────────────────────

  function showStatusBar() {
    if (document.getElementById('quareo-status-bar')) return;

    const bar = document.createElement('div');
    bar.id = 'quareo-status-bar';
    bar.style.cssText = `
      position: fixed; bottom: 20px; right: 20px; z-index: 99998;
      background: #1e293b; color: #fff; padding: 10px 18px;
      border-radius: 10px; font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex; align-items: center; gap: 10px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);
      transition: opacity 0.3s;
    `;
    bar.innerHTML = `
      <span style="width:8px;height:8px;border-radius:50%;background:#22c55e;box-shadow:0 0 8px #22c55e;"></span>
      <span>Quareo AI Автоответчик <strong>активен</strong></span>
      <span id="quareo-counter" style="background:#2563eb;padding:2px 8px;border-radius:6px;font-weight:700;font-size:12px;">0</span>
    `;
    document.body.appendChild(bar);
  }

  function updateCounter(count) {
    const counter = document.getElementById('quareo-counter');
    if (counter) counter.textContent = count;
  }

  // ── Главный цикл сканирования ──────────────────────────────────────

  let totalAnswered = 0;

  async function scanAndReply() {
    if (!isEnabled) return;

    const questions = findQuestions();
    if (questions.length === 0) return;

    console.log(`[Quareo] Найдено ${questions.length} новых вопросов`);

    for (const q of questions) {
      const reply = await getAIReply(q);
      if (reply) {
        insertReply(q, reply);
        markProcessed(q.id);
        totalAnswered++;
        updateCounter(totalAnswered);
        console.log(`[Quareo] Ответ сгенерирован на: "${q.text.substring(0, 50)}..."`);
        // Пауза между ответами (чтобы не было подозрительно быстро)
        await sleep(2000 + Math.random() * 3000);
      }
    }
  }

  // ── Утилиты ─────────────────────────────────────────────────────────

  function hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash |= 0;
    }
    return 'q_' + Math.abs(hash).toString(36);
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  // ── Слушаем сообщения от popup/background ───────────────────────────

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'QUAREO_UPDATE_SETTINGS') {
      loadSettings().then(() => {
        sendResponse({ ok: true });
      });
      return true;
    }
    if (msg.type === 'QUAREO_GET_STATUS') {
      sendResponse({
        isEnabled,
        totalAnswered,
        currentPage: window.location.href,
      });
      return true;
    }
    if (msg.type === 'QUAREO_SCAN_NOW') {
      scanAndReply().then(() => {
        sendResponse({ ok: true, answered: totalAnswered });
      });
      return true;
    }
  });

  // ── Инициализация ───────────────────────────────────────────────────

  async function init() {
    await loadSettings();

    if (!isEnabled) {
      console.log('[Quareo] Автоответчик отключен в настройках');
      return;
    }

    console.log('[Quareo] 🚀 Автоответчик активирован на', window.location.href);
    showStatusBar();

    // Первый скан через 3 секунды (дать странице загрузиться)
    setTimeout(scanAndReply, 3000);

    // Периодическое сканирование
    setInterval(scanAndReply, SCAN_INTERVAL);

    // Также отслеживаем изменения DOM (SPA навигация)
    const observer = new MutationObserver(() => {
      // Debounce: не сканировать слишком часто при DOM изменениях
      clearTimeout(observer._debounce);
      observer._debounce = setTimeout(scanAndReply, 2000);
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  init();
})();
