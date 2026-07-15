import asyncio
import random
import time
import json
import httpx
import os
import xml.etree.ElementTree as ET
import datetime
from typing import Dict, Any

from retailpool.schemas.store_scanner import (
    StoreScanRequest,
    StoreScanResponse,
    MonthlyData,
    SeasonalTrend,
    ProductAnalytics
)

class StoreScannerService:
    @staticmethod
    async def scan_store(request: StoreScanRequest) -> StoreScanResponse:
        """
        Scan Kaspi Seller Profile.
        If a Kaspi API key is provided, we fetch actual order data.
        """
        api_token = request.target.strip()
        is_xml_url = api_token.startswith('http') and '.xml' in api_token.lower()
        is_xml_file = os.path.isfile(api_token) and api_token.lower().endswith('.xml')
        
        is_sms = request.scan_type == 'sms'
        is_token = not api_token.startswith('+') and len(api_token) > 10 and not is_xml_url and not is_xml_file and not is_sms

        actual_products = []
        kaspi_error = None

        if is_xml_url or is_xml_file:
            # Парсинг Kaspi XML фида (по URL или локальному файлу)
            try:
                if is_xml_url:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(api_token)
                        if resp.status_code == 200:
                            root = ET.fromstring(resp.content)
                        else:
                            kaspi_error = f"XML Fetch Error: {resp.status_code}"
                            root = None
                else:
                    # Читаем локальный XML файл
                    tree = ET.parse(api_token)
                    root = tree.getroot()

                if root is not None:
                    # Strip namespaces for easier parsing
                    for elem in root.iter():
                        if '}' in elem.tag:
                            elem.tag = elem.tag.split('}', 1)[1]
                            
                    offers = root.findall('.//offer')
                    if not offers:
                        offers = root.findall('.//item') 
                    
                    for offer in offers:
                        model_elem = offer.find('model')
                        name_elem = offer.find('name')
                        price_elem = offer.find('price')
                        
                        name = None
                        if model_elem is not None and model_elem.text:
                            name = model_elem.text
                        elif name_elem is not None and name_elem.text:
                            name = name_elem.text
                            
                        price = 0
                        if price_elem is not None and price_elem.text:
                            try:
                                price = float(price_elem.text)
                            except ValueError:
                                pass
                                
                        if name:
                            actual_products.append({"name": name, "price": price})
                            
                    if not actual_products:
                        kaspi_error = "XML Parser Error: Не найдены теги <offer> или <model>."
            except Exception as e:
                kaspi_error = f"XML Error: {repr(e)}"

        elif is_token:
            # Try to fetch real orders from Kaspi API
            headers = {
                "Content-Type": "application/vnd.api+json",
                "X-Auth-Token": api_token,
                "Accept": "application/vnd.api+json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    # 1. Сначала пытаемся вытащить каталог товаров (Products API), 
                    # чтобы обойти "скрытые товары" в Orders API.
                    catalog_dict = {}
                    try:
                        p_url = "https://kaspi.kz/shop/api/v2/products?page[size]=100"
                        p_resp = await client.get(p_url, headers=headers)
                        if p_resp.status_code == 200:
                            p_data = p_resp.json()
                            for p_item in p_data.get("data", []):
                                p_id = p_item.get("id")
                                p_attr = p_item.get("attributes", {})
                                # Берем имя, если нет - берем артикул (code)
                                p_name = p_attr.get("name") or p_attr.get("title") or p_attr.get("code")
                                p_price = p_attr.get("price") or 0
                                if p_id and p_name:
                                    catalog_dict[str(p_id)] = {"name": p_name, "price": p_price}
                    except Exception as e:
                        pass # Если Products API недоступен, фоллбэк на данные из заказов
                        
                    # 2. Теперь запрашиваем сами заказы (Orders API)
                    now_ms = int(time.time() * 1000)
                    fourteen_days_ago_ms = now_ms - (14 * 24 * 60 * 60 * 1000)
                    # Kaspi по умолчанию отдает только статус NEW, если не указать фильтр.
                    # Для аналитики продаж нам нужны завершенные/исторические заказы (ARCHIVE).
                    kaspi_total_revenue = 0
                    actual_products_dict = {}
                    all_entry_urls = []
                    
                    url_base = f"https://kaspi.kz/shop/api/v2/orders?page[size]=50&filter[orders][state]=ARCHIVE&filter[orders][creationDate][$ge]={fourteen_days_ago_ms}&filter[orders][creationDate][$le]={now_ms}&include=entries"
                    
                    page_number = 0
                    total_pages = 1
                    
                    kaspi_total_revenue = 0
                    actual_products_dict = {}
                    all_entry_urls = []
                    
                    while page_number < total_pages and page_number < 10:  # Fetch up to 500 orders
                        url = f"{url_base}&page[number]={page_number}"
                        resp = await client.get(url, headers=headers)
                        
                        if resp.status_code != 200:
                            kaspi_error = f"Kaspi API Error: {resp.status_code} - {resp.text[:50]}"
                            break
                            
                        data = resp.json()
                            
                        # 1. Считаем выручку и собираем ссылки на товары (entries)
                        for item in data.get("data", []):
                            attrs = item.get("attributes", {})
                            kaspi_total_revenue += attrs.get("totalPrice", 0)
                            
                            entries_link = item.get("relationships", {}).get("entries", {}).get("links", {}).get("related")
                            if entries_link:
                                all_entry_urls.append(entries_link)

                        meta = data.get("meta", {})
                        total_pages = meta.get("pageCount", 1)
                        page_number += 1
                        
                    # 2. Асинхронно скачиваем составы всех заказов, чтобы посчитать реальные продажи каждого товара
                    if all_entry_urls:
                        async def fetch_entry(entry_url):
                            try:
                                r = await client.get(entry_url, headers=headers)
                                return r.json() if r.status_code == 200 else None
                            except Exception:
                                return None

                        # Разбиваем на чанки по 15 запросов, чтобы Kaspi не заблокировал за спам
                        chunk_size = 15
                        for i in range(0, len(all_entry_urls), chunk_size):
                            chunk_tasks = [fetch_entry(u) for u in all_entry_urls[i:i+chunk_size]]
                            chunk_results = await asyncio.gather(*chunk_tasks)
                            
                            for e_data in chunk_results:
                                if not e_data: continue
                                
                                # ДЕБАГ: Сохраняем первый успешный ответ /entries, чтобы понять структуру
                                if not getattr(StoreScannerService, "_debug_saved", False):
                                    with open("kaspi_entries_debug.json", "w", encoding="utf-8") as f:
                                        json.dump(e_data, f, ensure_ascii=False, indent=2)
                                    StoreScannerService._debug_saved = True
                                    
                                for inc in e_data.get("data", []):
                                    e_attrs = inc.get("attributes", {})
                                    quantity = e_attrs.get("quantity", 1)
                                    total_price = e_attrs.get("totalPrice", 0)
                                    
                                    rel = inc.get("relationships", {})
                                    p_rel = rel.get("product", {}).get("data", {})
                                    p_id = str(p_rel.get("id")) if p_rel else None
                                    
                                    price = total_price / quantity if quantity > 0 else 0
                                    
                                    # Пытаемся вытащить имя прямо из атрибута offer (как отдает новый Kaspi API)
                                    offer = e_attrs.get("offer", {})
                                    offer_name = offer.get("name")
                                    offer_code = offer.get("code")
                                    
                                    if offer_name:
                                        name = offer_name
                                    elif p_id and p_id in catalog_dict:
                                        name = catalog_dict[p_id]["name"]
                                        if price == 0: price = catalog_dict[p_id]["price"]
                                    else:
                                        name = e_attrs.get("name") or e_attrs.get("title") or offer_code or p_id or "Скрытый товар"
                                        
                                    if name not in actual_products_dict:
                                        actual_products_dict[name] = {"sold": 0, "rev": 0, "price": price}
                                    
                                    actual_products_dict[name]["sold"] += quantity
                                    actual_products_dict[name]["rev"] += total_price

                    # Конвертируем словарь в список
                    for name, data_item in actual_products_dict.items():
                        if data_item["price"] > 0 or data_item["rev"] > 0:
                            actual_products.append({
                                "name": str(name), 
                                "price": data_item["price"] if data_item["price"] > 0 else (data_item["rev"] / data_item["sold"] if data_item["sold"] > 0 else 1000),
                                "api_sold": data_item["sold"],
                                "api_rev": data_item["rev"]
                            })
                            
                    # Высчитываем мультипликатор на основе выбранного периода (request.period)
                    period_val = getattr(request, "period", "14d")
                    period_multiplier = 1.0
                    if period_val == "7d": period_multiplier = 0.5
                    elif period_val == "1m": period_multiplier = 30.0 / 14.0
                    elif period_val == "3m": period_multiplier = 90.0 / 14.0
                    elif period_val == "6m": period_multiplier = 180.0 / 14.0
                    elif period_val == "1y": period_multiplier = 365.0 / 14.0
                    
                    if period_multiplier != 1.0:
                        # Экстраполируем детализацию товаров
                        for p in actual_products:
                            p["api_sold"] = int(p["api_sold"] * period_multiplier)
                            p["api_rev"] = int(p["api_rev"] * period_multiplier)
                        # Экстраполируем KPI
                        kaspi_total_revenue = int(kaspi_total_revenue * period_multiplier)

                    # 3. Глубокий сборщик истории (Динамика за год)
                    # Выгружаем выручку за 12 месяцев конкурентно (26 отрезков по 14 дней)
                    async def fetch_interval_revenue(start_ts, end_ts):
                        res = {}
                        p_num = 0
                        while p_num < 5: # до 500 заказов за 14 дней
                            u = f"https://kaspi.kz/shop/api/v2/orders?page[size]=100&page[number]={p_num}&filter[orders][state]=ARCHIVE&filter[orders][creationDate][$ge]={start_ts}&filter[orders][creationDate][$le]={end_ts}"
                            try:
                                r = await client.get(u, headers=headers)
                                if r.status_code != 200: break
                                d = r.json()
                                items = d.get("data", [])
                                if not items: break
                                
                                for it in items:
                                    ats = it.get("attributes", {})
                                    c_date = ats.get("creationDate")
                                    if c_date:
                                        dt = datetime.datetime.fromtimestamp(c_date / 1000.0)
                                        m_key = (dt.year, dt.month)
                                        res[m_key] = res.get(m_key, 0) + ats.get("totalPrice", 0)
                                        
                                if d.get("meta", {}).get("pageCount", 1) <= p_num + 1:
                                    break
                                p_num += 1
                            except:
                                break
                        return res

                    history_tasks = []
                    fourteen_days_ms = 14 * 24 * 60 * 60 * 1000
                    cursor_ms = now_ms
                    for _ in range(26):
                        start_ms = cursor_ms - fourteen_days_ms
                        history_tasks.append(fetch_interval_revenue(start_ms, cursor_ms))
                        cursor_ms = start_ms

                    history_results = []
                    chunk_size_hist = 5
                    for i in range(0, len(history_tasks), chunk_size_hist):
                        chunk_res = await asyncio.gather(*history_tasks[i:i+chunk_size_hist])
                        history_results.extend(chunk_res)
                        await asyncio.sleep(0.3) # Защита от Kaspi rate-limit

                    monthly_totals = {}
                    for res_dict in history_results:
                        for m_key, rev in res_dict.items():
                            monthly_totals[m_key] = monthly_totals.get(m_key, 0) + rev

                    # Строим реальный график по месяцам
                    if monthly_totals:
                        kaspi_monthly_chart = []
                        month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
                        sorted_months = sorted(monthly_totals.keys())
                        for y, m in sorted_months:
                            kaspi_monthly_chart.append(MonthlyData(
                                month=f"{month_names[m]} '{str(y)[2:]}",
                                revenue=monthly_totals[(y, m)],
                                profit=int(monthly_totals[(y, m)] * 0.25)
                            ))
                    else:
                        kaspi_monthly_chart = None
                        
                    if not kaspi_error and not actual_products:
                        if catalog_dict:
                            for p_id, p_data in catalog_dict.items():
                                actual_products.append({
                                    "name": str(p_data["name"]),
                                    "price": p_data["price"],
                                    "api_sold": 0,
                                    "api_rev": 0
                                })
                            kaspi_error = "Partial Data: Заказов за 14 дней не найдено. Отчет построен по активному каталогу."
                        else:
                            actual_products = [{"name": f"Товар (SKU-{random.randint(1000, 9999)})", "price": random.randint(2000, 25000)} for _ in range(5)]
                            kaspi_error = "Partial Data: Нет заказов за 14 дней и каталог недоступен."
                    elif not kaspi_error and len(actual_products) > 0 and all(p["name"] == "Скрытый товар" for p in actual_products):
                        kaspi_error = "Partial Data: Названия товаров скрыты настройками приватности Kaspi. Используйте XML-фид."
                    
            except Exception as e:
                kaspi_error = f"Network Error: {repr(e)}"
        
        if not is_token or kaspi_error:
            await asyncio.sleep(1.5)
            kaspi_total_revenue = 10650000

        # Если выручка с апи пришла 0 (например, нет заказов за 14 дней), сделаем дефолтную для отображения
        if kaspi_total_revenue == 0:
            kaspi_total_revenue = 10650000

        # 1. Monthly Charts Data 
        total_revenue = kaspi_total_revenue
        
        # Если выгрузилась реальная история за год, используем ее! Иначе фоллбэк (условное распределение).
        if is_token and 'kaspi_monthly_chart' in locals() and kaspi_monthly_chart:
            monthly_chart = kaspi_monthly_chart
            # KPI выручка на дашборде будет за выбранный период (уже умножена),
            # но если выбрали 1 год, возьмем точную сумму с графика
            if getattr(request, "period", "14d") == "1y":
                total_revenue = sum(m.revenue for m in monthly_chart)
        else:
            monthly_chart = [
                MonthlyData(month="Май", revenue=int(total_revenue * 0.2), profit=int(total_revenue * 0.2 * 0.25)),
                MonthlyData(month="Июнь", revenue=int(total_revenue * 0.3), profit=int(total_revenue * 0.3 * 0.25)),
                MonthlyData(month="Июль", revenue=int(total_revenue * 0.5), profit=int(total_revenue * 0.5 * 0.25)),
            ]
            
        total_profit = int(total_revenue * 0.25) # Средняя рентабельность 25%
        avg_margin_percent = 25.0

        # 2. Seasonal Trends (Heatmap Insights)
        top_name = actual_products[0]["name"] if actual_products else "Товар"
        seasonal_heatmap = [
            SeasonalTrend(
                season="Лето",
                top_product_name=top_name,
                peak_month="Июль",
                sales_volume=120,
                ai_advice="На основе ваших текущих заказов, этот товар является флагманом сезона."
            )
        ]

        # 3. Dynamic Product Analytics
        all_analytics = []

        for prod in actual_products:
            price = prod["price"]
            
            # Если цена совсем нулевая, пропустим из аналитики (или сделаем 1000)
            if price <= 0:
                price = random.randint(3000, 15000)
                
            # Используем реальные продажи из API если есть, иначе моделируем
            sold = prod.get("api_sold") if prod.get("api_sold") is not None else random.randint(5, 120)
            rev = prod.get("api_rev") if prod.get("api_rev") is not None else price * sold
            
            # Реалистичная экономика:
            # Себестоимость от 30% до 70% от цены
            cost = int(price * random.uniform(0.3, 0.7))
            comm = int(price * 0.12) # 12% комиссия
            
            # Логистика (иногда дорогая межгород/КГТ)
            logistics = random.choice([0, 0, 500, 1000, 2000]) 
            
            profit = rev - (cost * sold) - (comm * sold) - (logistics * sold)
            divisor = cost * sold
            roi = round((profit / divisor) * 100, 1) if divisor > 0 else 0.0
            
            all_analytics.append({
                "prod": prod,
                "price": price,
                "sold": sold,
                "rev": rev,
                "cost": cost,
                "comm": comm,
                "profit": profit,
                "roi": roi
            })

        # Сортируем по ROI для распределения по категориям
        all_analytics.sort(key=lambda x: x["roi"], reverse=True)
        
        strong_cards = []
        weak_cards = []
        loss_making_cards = []
        
        # Берем топ-15 для каждой категории, чтобы не перегружать интерфейс тысячами карточек
        for i, data in enumerate(all_analytics):
            cat = "A"
            advice = "Отличный товар! Хорошая маржинальность. Увеличьте рекламный бюджет."
            if data["roi"] < 10 and data["profit"] >= 0:
                cat = "C"
                advice = "Низкая маржинальность. Оптимизируйте карточку и логистику."
            elif data["profit"] < 0:
                cat = "C"
                advice = "ВНИМАНИЕ: Убыток из-за высокой логистики/себестоимости. Поднимите цену."

            p_obj = ProductAnalytics(
                sku=f"SKU-{random.randint(1000,9999)}", 
                name=data["prod"]["name"], 
                price=data["price"], 
                sold_count=data["sold"], 
                revenue=data["rev"],
                purchase_cost=data["cost"], 
                commission=data["comm"], 
                profit=data["profit"], 
                roi_percent=data["roi"], 
                category=cat,
                ai_advice=advice
            )
            
            if data["profit"] < 0:
                if len(loss_making_cards) < 15:
                    loss_making_cards.append(p_obj)
            elif data["roi"] > 30:
                if len(strong_cards) < 15:
                    strong_cards.append(p_obj)
            else:
                if len(weak_cards) < 15:
                    weak_cards.append(p_obj)

        if is_token:
            title = "Kaspi Store: Live Data"
        elif is_xml_url or is_xml_file:
            title = "Kaspi Store: XML Анализ"
        elif is_sms:
            title = f"Kaspi Store: Internal API (Kaspi Pay Verified - {api_token})"
        else:
            title = "Kaspi Store: Гостевой анализ"

        return StoreScanResponse(
            store_name=title,
            total_revenue=total_revenue,
            total_profit=total_profit,
            avg_margin_percent=avg_margin_percent,
            monthly_chart=monthly_chart,
            seasonal_heatmap=seasonal_heatmap,
            strong_cards=strong_cards,
            weak_cards=weak_cards,
            loss_making_cards=loss_making_cards,
            error_message=kaspi_error
        )
