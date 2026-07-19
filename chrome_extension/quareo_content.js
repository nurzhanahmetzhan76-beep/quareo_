/* 
  quareo_content.js
  Внедряется на страницу Quareo (localhost:8000 или quareo.pro).
  Слушает события от нашего дашборда и передает их в background.js
*/

// Слушаем события отправленные из ntin.html
window.addEventListener("message", function(event) {
  // Убеждаемся, что событие от нашего окна
  if (event.source !== window) return;

  if (event.data.type && event.data.type === "QUAREO_BIND_NTIN") {
    console.log("Расширение получило данные для Kaspi:", event.data.payload);
    
    // Отправляем данные в background.js (Service Worker)
    chrome.runtime.sendMessage(
      { type: "BIND_IN_KASPI", payload: event.data.payload },
      function(response) {
        // Возвращаем ответ обратно на страницу (успех или ошибка)
        window.postMessage({ type: "QUAREO_BIND_RESULT", result: response }, "*");
      }
    );
  }
});
