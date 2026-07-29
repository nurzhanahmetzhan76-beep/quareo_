/* Smart Print UI.  It deliberately keeps the existing PDF endpoint and formats. */

let archiveAnalysis = null;
let currentDownloadUrl = null;

function waybillApiError(response) {
  return response.json().catch(() => ({})).then((body) => {
    throw new Error(body.detail || `HTTP ${response.status}`);
  });
}

async function handleZipSelect(event) {
  const file = event.target.files[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.zip')) {
    alert('Пожалуйста, выберите ZIP-архив.');
    event.target.value = '';
    return;
  }

  selectedFile = file;
  archiveAnalysis = null;
  document.getElementById('smartPrintToggle').checked = true;
  document.getElementById('uploadTitle').textContent = `Выбран файл: ${file.name}`;
  document.getElementById('formatSelection').style.display = 'none';
  document.getElementById('resultArea').style.display = 'none';
  document.getElementById('analysisLoadingArea').style.display = 'block';

  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await fetch(RP_API_BASE + '/api/waybills/analyze', {
      method: 'POST',
      headers: { ...rpAuthHeaders() },
      body: formData,
    });
    if (!response.ok) await waybillApiError(response);

    archiveAnalysis = await response.json();
    document.getElementById('analysisLoadingArea').style.display = 'none';
    document.getElementById('formatSelection').style.display = 'block';
    renderArchiveAnalysis();
    loadWaybillHistory();
  } catch (error) {
    alert('Ошибка при проверке архива: ' + error.message);
    resetForm();
  }
}

function selectedPrintCount() {
  if (!archiveAnalysis) return 0;
  return document.getElementById('smartPrintToggle').checked
    ? archiveAnalysis.new
    : archiveAnalysis.total;
}

function updateSmartPrintAction() {
  if (!archiveAnalysis) return;
  const smartPrint = document.getElementById('smartPrintToggle').checked;
  const printCount = selectedPrintCount();
  const noNew = smartPrint && archiveAnalysis.new === 0;
  const suffix = smartPrint ? 'новых' : 'всех';

  document.getElementById('noNewMessage').style.display = noNew ? 'block' : 'none';
  document.getElementById('printTitle').textContent = noNew
    ? 'Новых накладных для печати нет'
    : `Распечатать ${printCount} ${suffix} накладных`;

  const thermalButton = document.getElementById('btnFormatThermal');
  const a4Button = document.getElementById('btnFormatA4');
  thermalButton.disabled = noNew;
  a4Button.disabled = noNew;
  thermalButton.textContent = `🖨️ Термопринтер — печать ${printCount}`;
  a4Button.textContent = `📄 A4 (4 на листе) — печать ${printCount}`;
}

function renderArchiveAnalysis() {
  document.getElementById('archiveTotal').textContent = archiveAnalysis.total;
  document.getElementById('archiveProcessed').textContent = archiveAnalysis.already_processed;
  document.getElementById('archiveNew').textContent = archiveAnalysis.new;
  updateSmartPrintAction();
}

function resetForm() {
  selectedFile = null;
  archiveAnalysis = null;
  document.getElementById('smartPrintToggle').checked = true;
  document.getElementById('zipInput').value = '';
  document.getElementById('uploadTitle').textContent = 'Загрузите ZIP-архив с накладными Kaspi';
  document.getElementById('formatSelection').style.display = 'none';
  document.getElementById('analysisLoadingArea').style.display = 'none';
  document.getElementById('loadingArea').style.display = 'none';
  document.getElementById('resultArea').style.display = 'none';
  document.getElementById('uploadArea').style.display = 'block';
}

async function processWaybills(format) {
  if (!selectedFile || !archiveAnalysis) return;
  const smartPrint = document.getElementById('smartPrintToggle').checked;
  if (smartPrint && archiveAnalysis.new === 0) return;

  document.getElementById('uploadArea').style.display = 'none';
  document.getElementById('formatSelection').style.display = 'none';
  document.getElementById('loadingArea').style.display = 'block';

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('format', format);
  formData.append('sort', 'time');
  formData.append('smart_print', String(smartPrint));

  try {
    const response = await fetch(RP_API_BASE + '/api/waybills/process', {
      method: 'POST',
      headers: { ...rpAuthHeaders() },
      body: formData,
    });
    if (!response.ok) await waybillApiError(response);

    const blob = await response.blob();
    if (currentDownloadUrl) URL.revokeObjectURL(currentDownloadUrl);
    currentDownloadUrl = URL.createObjectURL(blob);
    const printed = Number(response.headers.get('X-Waybills-Printed')) || selectedPrintCount();

    document.getElementById('loadingArea').style.display = 'none';
    document.getElementById('resultArea').style.display = 'block';
    document.getElementById('resultText').textContent = `PDF сформирован: ${printed} накладных готовы к печати.`;

    const link = document.getElementById('downloadLink');
    link.href = currentDownloadUrl;
    link.download = `waybills_${format}_${Date.now()}.pdf`;
    link.textContent = `⬇️ Скачать PDF (${printed})`;
    loadWaybillHistory();
  } catch (error) {
    alert('Ошибка при обработке: ' + error.message);
    resetForm();
  }
}

function formatHistoryTime(isoDate) {
  const date = new Date(isoDate);
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString('ru-KZ', { hour: '2-digit', minute: '2-digit' });
}

async function loadWaybillHistory() {
  try {
    const response = await fetch(RP_API_BASE + '/api/waybills/history', {
      headers: { ...rpAuthHeaders() },
    });
    if (!response.ok) return;

    const entries = await response.json();
    const empty = document.getElementById('historyEmpty');
    const list = document.getElementById('historyList');
    list.replaceChildren();
    if (!entries.length) {
      empty.style.display = 'flex';
      list.style.display = 'none';
      return;
    }

    for (const entry of entries) {
      const item = document.createElement('div');
      item.className = 'waybills-history-item';
      const time = document.createElement('time');
      time.textContent = formatHistoryTime(entry.created_at);
      const outcome = document.createElement('strong');
      outcome.textContent = entry.new > 0 ? `+${entry.new} новых` : 'Нет новых';
      const details = document.createElement('span');
      details.textContent = `Архив: ${entry.total}; уже обработано: ${entry.already_processed}`;
      item.append(time, outcome, details);
      list.append(item);
    }
    empty.style.display = 'none';
    list.style.display = 'grid';
  } catch (_) {
    // The working area remains usable when history cannot be loaded.
  }
}

document.addEventListener('DOMContentLoaded', loadWaybillHistory);
