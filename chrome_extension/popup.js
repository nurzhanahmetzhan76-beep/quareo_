  // ── State ────────────────────────────────────────────────────────────
  let settings = {
    enabled: true,
    autoSend: false,
    tone: 'friendly',
    storeDesc: '',
    customInstr: '',
    token: '',
    apiBase: 'https://quareo.pro',
  };

  // ── Load settings ───────────────────────────────────────────────────
  chrome.storage.local.get(
    ['quareo_enabled', 'quareo_auto_send', 'quareo_token', 'quareo_api_base',
     'quareo_tone', 'quareo_store_desc', 'quareo_custom_instr', 'quareo_answered'],
    (data) => {
      settings.enabled = data.quareo_enabled !== false;
      settings.autoSend = data.quareo_auto_send === true;
      settings.token = data.quareo_token || '';
      settings.apiBase = data.quareo_api_base || 'https://quareo.pro';
      settings.tone = data.quareo_tone || 'friendly';
      settings.storeDesc = data.quareo_store_desc || '';
      settings.customInstr = data.quareo_custom_instr || '';

      // Update UI
      updateUI();
      document.getElementById('answeredCount').textContent = data.quareo_answered || 0;

      // Check token
      if (settings.token) {
        document.getElementById('authStatus').className = 'auth-status ok';
        document.getElementById('authStatus').textContent = '✓ Токен сохранён';
        document.getElementById('tokenInput').value = '••••••••••••••••';
      } else {
        document.getElementById('authStatus').className = 'auth-status no';
        document.getElementById('authStatus').textContent = '✗ Токен не задан';
      }

      // Check Kaspi tab
      chrome.tabs.query({ url: "*://*.kaspi.kz/*" }, (tabs) => {
        document.getElementById('kaspiStatus').textContent = tabs.length > 0 ? '✓' : '✗';
        document.getElementById('kaspiStatus').style.color = tabs.length > 0 ? '#22c55e' : '#ef4444';
      });
    }
  );

  function updateUI() {
    // Toggles
    document.getElementById('toggleEnabled').className = 'toggle' + (settings.enabled ? ' on' : '');
    document.getElementById('toggleAutoSend').className = 'toggle' + (settings.autoSend ? ' on' : '');

    // Status bar
    const statusBar = document.getElementById('statusBar');
    const statusText = document.getElementById('statusText');
    if (settings.enabled && settings.token) {
      statusBar.className = 'status-bar on';
      statusText.textContent = 'Автоответчик активен';
    } else if (!settings.token) {
      statusBar.className = 'status-bar off';
      statusText.textContent = 'Нужна авторизация';
    } else {
      statusBar.className = 'status-bar off';
      statusText.textContent = 'Автоответчик выключен';
    }

    // Form values
    document.getElementById('toneSelect').value = settings.tone;
    document.getElementById('storeDesc').value = settings.storeDesc;
    document.getElementById('customInstr').value = settings.customInstr;
  }

  // ── Actions ─────────────────────────────────────────────────────────

  function toggleSetting(key) {
    if (key === 'enabled') {
      settings.enabled = !settings.enabled;
      chrome.storage.local.set({ quareo_enabled: settings.enabled });
    } else if (key === 'autoSend') {
      settings.autoSend = !settings.autoSend;
      chrome.storage.local.set({ quareo_auto_send: settings.autoSend });
    }
    updateUI();
    notifyContentScript();
  }

  document.getElementById('rowEnabled').addEventListener('click', () => toggleSetting('enabled'));
  document.getElementById('rowAutoSend').addEventListener('click', () => toggleSetting('autoSend'));

  document.getElementById('saveTokenBtn').addEventListener('click', () => {
    const val = document.getElementById('tokenInput').value.trim();
    if (!val) {
      document.getElementById('authStatus').className = 'auth-status no';
      document.getElementById('authStatus').textContent = '✗ Пожалуйста, вставьте токен сначала!';
      return;
    }
    if (val !== '••••••••••••••••') {
      settings.token = val;
      chrome.storage.local.set({ quareo_token: val });
      document.getElementById('authStatus').className = 'auth-status ok';
      document.getElementById('authStatus').textContent = '✓ Токен сохранён';
      document.getElementById('tokenInput').value = '••••••••••••••••';
      updateUI();
      notifyContentScript();
    } else {
      document.getElementById('authStatus').className = 'auth-status ok';
      document.getElementById('authStatus').textContent = '✓ Токен уже сохранён';
    }
  });

  document.getElementById('saveBtn').addEventListener('click', () => {
    settings.tone = document.getElementById('toneSelect').value;
    settings.storeDesc = document.getElementById('storeDesc').value;
    settings.customInstr = document.getElementById('customInstr').value;

    chrome.storage.local.set({
      quareo_tone: settings.tone,
      quareo_store_desc: settings.storeDesc,
      quareo_custom_instr: settings.customInstr,
    });

    // Also update server-side settings
    if (settings.token) {
      fetch(settings.apiBase + '/api/autoreply/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + settings.token,
        },
        body: JSON.stringify({
          tone: settings.tone,
          auto_send: settings.autoSend,
          store_description: settings.storeDesc,
          custom_instructions: settings.customInstr,
        }),
      }).catch(console.error);
    }

    const btn = document.getElementById('saveBtn');
    btn.textContent = '✓ Сохранено!';
    btn.style.background = '#22c55e';
    setTimeout(() => {
      btn.textContent = '💾 Сохранить настройки';
      btn.style.background = '#3b82f6';
    }, 1500);

    notifyContentScript();
  });

  document.getElementById('scanBtn').addEventListener('click', () => {
    chrome.tabs.query({ url: "*://*.kaspi.kz/*" }, (tabs) => {
      if (tabs.length === 0) {
        alert('Откройте вкладку с кабинетом продавца Kaspi (kaspi.kz/mc)');
        return;
      }
      chrome.tabs.sendMessage(tabs[0].id, { type: 'QUAREO_SCAN_NOW' }, (resp) => {
        if (chrome.runtime.lastError) {
          alert('Связь с Kaspi не установлена!\n\nПожалуйста, ОБНОВИТЕ ВКЛАДКУ Kaspi (F5), чтобы загрузилась новая версия расширения.');
          return;
        }
        if (resp && resp.ok) {
          document.getElementById('answeredCount').textContent = resp.answered;
          const btn = document.getElementById('scanBtn');
          btn.textContent = '✓ Сканирование завершено';
          setTimeout(() => { btn.textContent = '🔍 Сканировать сейчас'; }, 2000);
        }
      });
    });
  });

  function notifyContentScript() {
    chrome.tabs.query({ url: "*://*.kaspi.kz/*" }, (tabs) => {
      tabs.forEach(tab => {
        chrome.tabs.sendMessage(tab.id, { type: 'QUAREO_UPDATE_SETTINGS' }, (resp) => {
           if (chrome.runtime.lastError) {
             // Игнорируем ошибку при фоновом обновлении
           }
        });
      });
    });
  }
