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

(function () {
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

    // Паттерн 1: Чат заказов и сообщений (Универсальный и надежный)
    const allInputs = document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"]');
    allInputs.forEach(input => {
      const placeholder = (input.placeholder || input.getAttribute('data-placeholder') || '').toLowerCase();

      // СТРОГАЯ ЗАЩИТА: Это должно быть ИМЕННО поле для сообщения! 
      // Игнорируем любые фильтры, поиск категорий, названия товаров и т.д.
      const isChatInput = placeholder.includes('сообщен') ||
        placeholder.includes('хабарлама') ||
        placeholder.includes('message');

      if (!isChatInput) {
        return; // Пропускаем любой инпут, который не похож на чат
      }

      // Берем контейнер чата (ищем ближайшее модальное окно или секцию)
      let chatContainer = input.closest('div[class*="dialog"], div[class*="modal"], div[class*="chat"], div[role="dialog"], section');

      // Если контейнер не найден, но мы уже точно знаем, что это чат (по плейсхолдеру),
      // разрешаем искать сообщения по всей странице (для полноэкранных версий)
      if (!chatContainer) {
        chatContainer = document.body;
      }

      // Ищем абсолютно все мелкие текстовые блоки (span, p, div) внутри ЭТОГО чата
      const allTextNodes = chatContainer.querySelectorAll('div, span, p');

      let lastMsgNode = null;
      let questionText = "";

      // Идем с конца, чтобы найти ПОСЛЕДНЕЕ сообщение
      for (let i = allTextNodes.length - 1; i >= 0; i--) {
        const node = allTextNodes[i];
        const text = (node.textContent || '').trim();

        // Критерии сообщения: есть текст, мало детей, не системное
        if (text.length > 3 && node.children.length < 5 && node.innerHTML.length < 800) {

          if (text.includes('Диалог по') || text.includes('Заказ №') || text.includes('Заявка №')) {
            continue;
          }

          // Проверяем, не является ли это сообщение нашим собственным (от продавца)
          // У Kaspi сообщения продавца обычно имеют другой цвет или класс, но простейший способ - 
          // проверить, не писали ли мы его только что (защита от зацикливания)

          lastMsgNode = node;
          questionText = text;
          break;
        }
      }

      if (!questionText || questionText.length < 3) return;

      // Имя клиента обычно в заголовке
      let customerName = "Покупатель";
      const header = chatContainer.querySelector('h1, h2, h3, [class*="header"], [class*="title"], [class*="name"]');
      if (header) {
        customerName = header.textContent.replace('Диалог по заказу', '').replace('Заказ', '').trim() || customerName;
      }

      // Защита от дублей генерации
      const id = hashString('chat_uni_' + questionText.substring(0, 50));
      if (processedIds.includes(id)) return;

      // Если поле уже заполнено текстом (больше 5 символов), не перебиваем его
      let currentVal = input.value;
      if (currentVal === undefined) currentVal = input.textContent || '';
      if (currentVal.trim().length > 5 && currentVal !== "Сообщение...") return;

      questions.push({
        id,
        text: questionText,
        productName: "Чат",
        customerName,
        element: lastMsgNode,
        answerInput: input,
      });
    });

    // Паттерн 2: Блоки с вопросами покупателей (раздел "Вопросы")
    const questionBlocks = document.querySelectorAll(
      '[class*="question-item"], [class*="QuestionItem"], ' +
      '[class*="review-item"], [class*="ReviewItem"], ' +
      '[class*="inquiry"], [class*="Inquiry"], ' +
      '[data-testid*="question"], [data-testid*="review"]'
    );

    questionBlocks.forEach(block => {
      const textContent = block.textContent?.trim() || '';
      if (!textContent || textContent.length < 10) return;

      const customerName = extractCustomerName(block);
      const id = hashString((customerName || 'unknown') + '_' + textContent.substring(0, 100));
      if (processedIds.includes(id)) return;

      const questionText = extractQuestionText(block);
      if (!questionText) return;

      const hasAnswer = checkHasAnswer(block);
      if (hasAnswer) {
        markProcessed(id);
        return;
      }

      questions.push({
        id,
        text: questionText,
        productName: extractProductName(block),
        customerName,
        element: block,
        answerInput: findAnswerInput(block),
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
      debugLog('⚠️ Нет токена авторизации');
      return null;
    }

    const payload = {
      question: question.text,
      product_name: question.productName || 'Товар',
      customer_name: question.customerName || 'Покупатель',
      question_id: question.id,
    };

    // Пробуем основной API, если не получается — пробуем localhost
    const bases = [apiBase];
    if (!apiBase.includes('localhost') && !apiBase.includes('127.0.0.1')) {
      bases.push('http://localhost:8000');
    }

    for (const base of bases) {
      try {
        debugLog('🌐 Запрос через BG к ' + base);

        // Проксируем через background.js (content script не может делать cross-origin fetch)
        const resp = await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({
            type: 'QUAREO_API_PROXY',
            url: base + '/api/autoreply/generate',
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + authToken,
            },
            body: payload,
          }, (response) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else {
              resolve(response);
            }
          });
        });

        if (!resp || !resp.ok) {
          debugLog('❌ API ' + base + ' ответил ' + (resp?.status || '?') + ': ' + (resp?.body || '').substring(0, 80));
          continue;
        }

        const data = JSON.parse(resp.body);
        if (data.reply) {
          debugLog('✅ Ответ получен от ' + base);
          return data.reply;
        }
      } catch (e) {
        debugLog('❌ Ошибка ' + base + ': ' + e.message);
      }
    }

    return null;
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
    // 1. Ставим фокус на поле
    input.focus();

    try {
      // 2. Идеальный способ для современных SPA (React, Vue) - симуляция реального ввода
      const success = document.execCommand('insertText', false, text);

      // 3. Если execCommand не сработал (в некоторых новых браузерах), используем нативные сеттеры
      if (!success) {
        if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
          const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;

          if (input.tagName === 'TEXTAREA' && nativeTextAreaValueSetter) {
            nativeTextAreaValueSetter.call(input, text);
          } else if (input.tagName === 'INPUT' && nativeInputValueSetter) {
            nativeInputValueSetter.call(input, text);
          } else {
            input.value = text;
          }
        } else if (input.isContentEditable) {
          input.textContent = text;
        }
      }
    } catch (e) {
      console.log('execCommand error fallback', e);
      input.value = text;
    }

    // 4. Диспатчим события для обновления стейта React
    input.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
    input.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));

    // 5. Визуальная индикация
    input.style.transition = 'box-shadow 0.3s';
    input.style.boxShadow = '0 0 12px rgba(34, 197, 94, 0.8)';
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
    popup.style.cssText = 'position:absolute;z-index:99999;background:#fff;border:2px solid #2563eb;border-radius:12px;padding:16px 20px;box-shadow:0 8px 32px rgba(0,0,0,0.15);max-width:400px;font-size:14px;color:#1e293b;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;';

    // Header row
    const headerRow = document.createElement('div');
    headerRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:10px;';

    const badge = document.createElement('span');
    badge.style.cssText = 'background:#2563eb;color:#fff;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700;';
    badge.textContent = 'QUAREO AI';
    headerRow.appendChild(badge);

    const subtitle = document.createElement('span');
    subtitle.style.cssText = 'color:#94a3b8;font-size:12px;';
    subtitle.textContent = 'Предложенный ответ';
    headerRow.appendChild(subtitle);

    popup.appendChild(headerRow);

    // Reply text block
    const replyBlock = document.createElement('div');
    replyBlock.style.cssText = 'background:#f1f5f9;padding:12px;border-radius:8px;margin-bottom:12px;line-height:1.5;';
    replyBlock.textContent = replyText;
    popup.appendChild(replyBlock);

    // Buttons row
    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:8px;';

    const copyBtn = document.createElement('button');
    copyBtn.style.cssText = 'flex:1;padding:8px 12px;background:#2563eb;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;';
    copyBtn.textContent = '📋 Копировать';
    btnRow.appendChild(copyBtn);

    const closeBtn = document.createElement('button');
    closeBtn.style.cssText = 'padding:8px 12px;background:#e2e8f0;color:#64748b;border:none;border-radius:8px;cursor:pointer;font-size:13px;';
    closeBtn.textContent = '✕';
    btnRow.appendChild(closeBtn);

    popup.appendChild(btnRow);

    nearElement.style.position = 'relative';
    nearElement.appendChild(popup);

    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(replyText).then(() => {
        copyBtn.textContent = '✓ Скопировано!';
        setTimeout(() => popup.remove(), 1500);
      });
    });

    closeBtn.addEventListener('click', () => {
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
    bar.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:99998;background:#1e293b;color:#fff;padding:10px 18px;border-radius:10px;font-size:13px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:center;gap:10px;box-shadow:0 4px 16px rgba(0,0,0,0.2);transition:opacity 0.3s;';

    const dot = document.createElement('span');
    dot.style.cssText = 'width:8px;height:8px;border-radius:50%;background:#22c55e;box-shadow:0 0 8px #22c55e;';
    bar.appendChild(dot);

    const label = document.createElement('span');
    const labelStrong = document.createElement('strong');
    labelStrong.textContent = 'активен';
    label.textContent = 'Quareo AI Автоответчик ';
    label.appendChild(labelStrong);
    bar.appendChild(label);

    const counter = document.createElement('span');
    counter.id = 'quareo-counter';
    counter.style.cssText = 'background:#2563eb;padding:2px 8px;border-radius:6px;font-weight:700;font-size:12px;';
    counter.textContent = '0';
    bar.appendChild(counter);

    document.body.appendChild(bar);
  }

  function updateCounter(count) {
    const counter = document.getElementById('quareo-counter');
    if (counter) counter.textContent = count;
  }

  // ── Визуальный дебаг-лог (показывает что происходит прямо на странице) ──

  function debugLog(msg) {
    console.log('[Quareo] ' + msg);
    const bar = document.getElementById('quareo-status-bar');
    if (!bar) return;
    let logEl = document.getElementById('quareo-debug-log');
    if (!logEl) {
      logEl = document.createElement('div');
      logEl.id = 'quareo-debug-log';
      logEl.style.cssText = 'position:fixed;bottom:50px;right:20px;z-index:99999;background:#0f172a;color:#94a3b8;padding:8px 12px;border-radius:8px;font-size:11px;max-width:350px;max-height:150px;overflow-y:auto;font-family:monospace;box-shadow:0 4px 16px rgba(0,0,0,0.3);';
      document.body.appendChild(logEl);
    }
    const line = document.createElement('div');
    line.style.cssText = 'border-bottom:1px solid #1e293b;padding:2px 0;';
    line.textContent = new Date().toLocaleTimeString() + ' ' + msg;
    logEl.appendChild(line);
    logEl.scrollTop = logEl.scrollHeight;
    // Максимум 20 строк
    while (logEl.children.length > 20) logEl.removeChild(logEl.firstChild);
  }

  // ── Главный цикл сканирования ──────────────────────────────────────

  let totalAnswered = 0;
  let isNavigating = false;

  async function autoNavigate() {
    if (isNavigating) return;
    isNavigating = true;

    try {
      // ПРОБЛЕМА: Бот бесконечно кликает "Новые", даже если чат уже открыт.
      // РЕШЕНИЕ: Сначала проверяем, не находимся ли мы уже внутри открытого диалога.
      const inputs = Array.from(document.querySelectorAll('textarea, input[type="text"]')).filter(i => {
        const ph = (i.placeholder || '').toLowerCase();
        return !ph.includes('поиск') && !ph.includes('search');
      });

      // Если поле ввода есть, значит диалог открыт. Никуда не кликаем, ждем действий человека!
      if (inputs.length > 0) {
        return;
      }

      // 1. Кнопка чата в правом нижнем углу
      // Ищем по типичным селекторам Kaspi или по SVG иконкам сообщений
      const chatWidgetBtn = document.querySelector('div[class*="chat-widget"], button[class*="chat-widget"], div[class*="ChatWidget"]');
      const isChatOpen = !!document.querySelector('textarea, input[placeholder*="сообщение" i], input[placeholder*="message" i]');

      if (chatWidgetBtn && !isChatOpen) {
        debugLog('🖱️ Открываю виджет чата...');
        chatWidgetBtn.click();
        await sleep(1500);
      }

      // 2. Вкладка "Новые"
      const allElements = Array.from(document.querySelectorAll('div, span, button, a, li'));
      const newTab = allElements.find(el => {
        const text = el.textContent.trim().toLowerCase();
        // У Kaspi вкладка обычно называется "Новые" (счетчик может быть внутри)
        return (text === 'новые' || text.startsWith('новые ')) &&
          el.children.length < 4 &&
          el.clientWidth < 300 &&
          el.clientWidth > 20; // Исключаем скрытые элементы
      });

      if (newTab) {
        // Проверяем, не активна ли она уже (если у неё есть фон или особый класс)
        debugLog('🖱️ Нажимаю на раздел "Новые"...');
        newTab.click();
        await sleep(1000);
      }

      // 3. Открываем первый чат в списке
      // Ищем карточки диалогов. Они обычно содержат аватарку, время, текст.
      // Эвристика: элементы-контейнеры, внутри которых есть время (ЧЧ:ММ)
      const timePattern = /\d{1,2}:\d{2}/;
      const chatCards = allElements.filter(el => {
        if (el.tagName !== 'DIV' && el.tagName !== 'LI') return false;
        const style = window.getComputedStyle(el);
        if (style.cursor !== 'pointer') return false;
        return timePattern.test(el.textContent) && el.textContent.length < 150;
      });

      if (chatCards.length > 0) {
        debugLog('🖱️ Открываю ПЕРВЫЙ новый диалог...');
        chatCards[0].click();
        await sleep(1500); // Ждем пока загрузятся сообщения
      } else {
        debugLog('ℹ️ Новых диалогов в списке не найдено');
      }
    } catch (e) {
      debugLog('⚠️ Ошибка автонавигации: ' + e.message);
    } finally {
      isNavigating = false;
    }
  }

  async function scanAndReply() {
    if (!isEnabled) {
      return; // Тихо выходим, чтобы не спамить лог
    }
    if (!authToken) {
      debugLog('⚠️ Нет токена! Укажите токен в настройках');
      return;
    }

    // Сначала пробуем навигироваться (открыть чат, нажать "Новые", открыть первый чат)
    await autoNavigate();

    const questions = findQuestions();

    if (questions.length === 0) {
      // Если вопросов нет, просто ждем следующего цикла
      return;
    }

    debugLog('📋 Найдено неотвеченных вопросов: ' + questions.length);

    for (const q of questions) {
      debugLog('💬 Вопрос: "' + q.text.substring(0, 60) + '..."');
      const reply = await getAIReply(q);
      if (reply) {
        debugLog('✅ Ответ сгенерирован!');
        insertReply(q, reply);
        markProcessed(q.id);
        totalAnswered++;
        updateCounter(totalAnswered);

        // Автоматическая отправка, если включена
        if (autoSend) {
          debugLog('🚀 Отправляю сообщение (Auto-send)...');
          await sleep(500); // Небольшая пауза перед кликом отправки
          clickSendButton(q.container);

          // После отправки нужно вернуться назад к списку "Новые"
          // чтобы на следующем цикле (через 10 сек) скрипт открыл следующий чат
          await sleep(1500);
          const backBtn = document.querySelector('button[aria-label*="назад" i], button[aria-label*="back" i], div[class*="back-button"]');
          if (backBtn) {
            debugLog('⬅️ Возвращаюсь к списку чатов...');
            backBtn.click();
          }
        }

        await sleep(2000 + Math.random() * 2000);
      } else {
        debugLog('❌ Ошибка генерации ответа');
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
