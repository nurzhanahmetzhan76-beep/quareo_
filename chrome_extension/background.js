/*
  background.js — Service Worker
  Выполняется в фоне браузера. Координирует работу расширения.
*/

// ── NTIN привязка (существующая логика) ─────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "BIND_IN_KASPI") {
    const products = request.payload.products;
    console.log("Начинаю привязку NTIN в Kaspi. Товаров:", products.length);

    bindProductsInKaspi(products)
      .then(res => sendResponse({ success: true, message: "Успешно привязано", details: res }))
      .catch(err => sendResponse({ success: false, message: err.message }));
    return true;
  }
});


async function bindProductsInKaspi(products) {
  const tabs = await chrome.tabs.query({ url: "*://*.kaspi.kz/*" });
  if (tabs.length === 0) {
    throw new Error("Не найдена открытая вкладка Kaspi. Пожалуйста, откройте https://kaspi.kz/mc в соседней вкладке.");
  }
  
  const kaspiTabId = tabs[0].id;
  const merchantUid = "17768037";

  const results = await chrome.scripting.executeScript({
    target: { tabId: kaspiTabId },
    func: async (productsToProcess, mUid) => {
      let processed = 0;
      let debugLogs = [];
      
      for (const product of productsToProcess) {
        if (!product.sku || !product.barcode) continue;
        
        const searchUrl = `https://mc.shop.kaspi.kz/bff/offer-view/list?m=${mUid}&p=0&l=10&a=true&t=${encodeURIComponent(product.sku)}`;
        try {
          const searchRes = await fetch(searchUrl, {
            method: "GET",
            headers: { "Accept": "application/json" },
            credentials: "include"
          });
          
          if (!searchRes.ok) {
            debugLogs.push(`SKU ${product.sku}: Ошибка поиска. Статус ${searchRes.status}`);
            continue;
          }
          
          const text = await searchRes.text();
          if (!text) {
            debugLogs.push(`SKU ${product.sku}: Пустой ответ от поиска`);
            continue;
          }
          const searchData = JSON.parse(text);
          const items = searchData.data || [];
          
          if (items.length === 0) {
            debugLogs.push(`SKU ${product.sku}: Товар не найден в Каспи`);
            continue;
          }
          
          const targetItem = items[0];
          const masterSku = targetItem.masterSku || targetItem.sku || targetItem.masterId || targetItem.id;
          
          if (!masterSku) {
            debugLogs.push(`SKU ${product.sku}: Не найден masterSku. Ключи: ${Object.keys(targetItem).join(", ")}`);
            continue;
          }
          
          const saveUrl = "https://mc.shop.kaspi.kz/merchant-nct/mc/nct/batch/force-save/by-master-sku";
          const savePayload = {
            merchantUid: mUid,
            items: [{
              masterSku: String(masterSku),
              barcode: product.barcode,
              ntin: product.barcode,
              gtin: null
            }]
          };
          
          const saveRes = await fetch(saveUrl, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Accept": "application/json"
            },
            credentials: "include",
            body: JSON.stringify(savePayload)
          });
          
          if (saveRes.ok) {
              processed++;
              debugLogs.push(`SKU ${product.sku}: Успешно сохранен NTIN ${product.barcode}`);
          } else {
              debugLogs.push(`SKU ${product.sku}: Ошибка POST API. Статус ${saveRes.status}`);
          }
        } catch (e) {
          debugLogs.push(`SKU ${product.sku}: Ошибка сети: ${e.message}`);
        }
      }
      
      return { processed, logs: debugLogs };
    },
    args: [products, merchantUid]
  });

  const tabResult = results[0].result;
  return { processed: tabResult.processed, status: "OK", logs: tabResult.logs };
}
