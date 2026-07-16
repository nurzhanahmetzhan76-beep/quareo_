/*
  background.js
  Выполняется в фоне браузера. Имеет доступ к кукам Kaspi.
*/

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "BIND_IN_KASPI") {
    const products = request.payload.products;
    
    console.log("Начинаю привязку NTIN в Kaspi. Товаров:", products.length);

    // Запускаем асинхронную функцию привязки
    bindProductsInKaspi(products)
      .then(res => sendResponse({ success: true, message: "Успешно привязано", details: res }))
      .catch(err => sendResponse({ success: false, message: err.message }));
      
    // Возвращаем true, чтобы указать, что ответ будет отправлен асинхронно
    return true; 
  }
});

async function bindProductsInKaspi(products) {
  // Ищем открытую вкладку Kaspi
  const tabs = await chrome.tabs.query({ url: "*://*.kaspi.kz/*" });
  if (tabs.length === 0) {
    throw new Error("Не найдена открытая вкладка Kaspi. Пожалуйста, откройте https://kaspi.kz/mc в соседней вкладке.");
  }
  
  const kaspiTabId = tabs[0].id;
  const merchantUid = "17768037"; // Ваш merchant ID

  // Выполняем весь код прямо внутри вкладки Kaspi, чтобы браузер подставил правильный Origin и Referer
  const results = await chrome.scripting.executeScript({
    target: { tabId: kaspiTabId },
    func: async (productsToProcess, mUid) => {
      let processed = 0;
      let debugLogs = [];
      
      for (const product of productsToProcess) {
        if (!product.sku || !product.barcode) continue;
        
        // 1. Ищем товар
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
          
          // 2. Сохраняем штрихкод
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
