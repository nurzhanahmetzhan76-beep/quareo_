"""
Waybills API endpoints.
Processes Kaspi ZIP archives containing PDF waybills.
"""
from __future__ import annotations

import io
import zipfile
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
import re
from datetime import datetime
import fitz  # PyMuPDF

from retailpool.models.user import User
from retailpool.services.auth_service import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from retailpool.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/waybills", tags=["Waybills"])

A4_WIDTH = 595.276
A4_HEIGHT = 842.0

def get_month_num(month_str):
    if not month_str:
        return 99
    s = month_str.lower().strip(' .')
    if s.startswith("янв"): return 1
    if s.startswith("фев"): return 2
    if s.startswith("мар"): return 3
    if s.startswith("апр"): return 4
    if s.startswith("ма"): return 5
    if s.startswith("июн"): return 6
    if s.startswith("июл"): return 7
    if s.startswith("авг"): return 8
    if s.startswith("сен"): return 9
    if s.startswith("окт"): return 10
    if s.startswith("ноя"): return 11
    if s.startswith("дек"): return 12
    return 99

def parse_date(day_str, month_str):
    day = int(day_str) if day_str.isdigit() else 99
    month = get_month_num(month_str)
    return (month, day)

@router.post("/process")
async def process_waybills(
    file: UploadFile = File(...),
    format: str = Form(...),
    sort: str = Form("none"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Takes a ZIP file of Kaspi waybills/labels and converts them.
    format: 'thermal' (1 per page) or 'a4' (4 per page)
    sort: 'none', 'date', or 'product'
    """
    user_plan = (current_user.plan or "free").lower()
    
    plan_limits = {
        "free": 1,
        "накладные": 999999,
        "waybills": 999999,
        "start": 999999,
        "старт": 999999,
        "business": 999999,
        "бизнес": 999999,
        "unlimited": 999999,
        "безлимит": 999999,
        "агентство": 999999
    }
    
    if user_plan not in plan_limits and current_user.email != "karimbai.ali10@mail.ru":
        raise HTTPException(status_code=403, detail="Доступ к накладным доступен только для авторизованных планов.")

    limit = plan_limits.get(user_plan, 0)
    if getattr(current_user, 'waybills_used', 0) >= limit and current_user.email != "karimbai.ali10@mail.ru":
        if user_plan == "free":
            raise HTTPException(
                status_code=403,
                detail="Вы исчерпали лимит бесплатного тарифа (1 генерация накладных). Пожалуйста, выберите платный тариф."
            )
        raise HTTPException(
            status_code=403,
            detail="Лимит накладных по вашему тарифу исчерпан."
        )

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Пожалуйста, загрузите ZIP архив.")
        
    zip_data = await file.read()
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
    if len(zip_data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 50 МБ).")
    writer = PdfWriter()
    
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            pdf_files = [f for f in z.namelist() if f.lower().endswith('.pdf')]
            
            if not pdf_files:
                raise HTTPException(status_code=400, detail="ZIP архив не содержит PDF файлов.")
                
            parsed_files = []
            for idx, pdf_name in enumerate(pdf_files):
                pdf_bytes = z.read(pdf_name)
                
                metadata = {
                    "original_index": idx,
                    "order_time": datetime.min,
                    "delivery_date": datetime.min,
                    "quantity": 1,
                    "product_name": ""
                }
                
                if sort != "none" and sort != "no_sort":
                    try:
                        # Используем PyMuPDF (fitz) для надежного извлечения текста
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        text = doc[0].get_text("text") or ""
                        doc.close()
                        
                        # Убираем лишние пробелы для надежности Regex
                        text_clean = re.sub(r'\s+', ' ', text)
                        
                        # 1. Парсинг даты доставки ("план дата доставки: 27 июл.")
                        # Ожидаемый паттерн: "дата доставки: 27 июл." или просто "27 июл"
                        alt_date = re.search(r"(\d{1,2})[\s\.]+(янв|фев|мар|апр|ма[яй]|июн|июл|авг|сен|окт|ноя|дек)", text_clean, re.IGNORECASE)
                        if alt_date:
                            metadata["delivery_date"] = parse_date(alt_date.group(1), alt_date.group(2))
                        else:
                            # (99, 99) улетит в конец списка
                            metadata["delivery_date"] = (99, 99)
                                
                        # 2. Дата заказа - на термоэтикетках её часто нет, используем номер заказа из имени файла как order_time fallback
                        order_id_match = re.search(r'\d+', pdf_name)
                        if order_id_match:
                            metadata["order_time"] = int(order_id_match.group())
                        else:
                            metadata["order_time"] = 999999999
                            
                        # 3. Наименование товара ("1. Гребень 12x3 см ........................... 1 шт.")
                        prod_match = re.search(r"1\s*[\.\,]\s*(.*?)(?=\s+\d+\s*шт|\.{3,}|$)", text_clean, re.IGNORECASE)
                        if prod_match:
                            metadata["product_name"] = re.sub(r'\.{3,}', '', prod_match.group(1)).strip()
                        else:
                            metadata["product_name"] = "Неизвестный товар"
                            
                        # 4. Парсинг количества
                        qty_match = re.search(r"(\d+)\s*шт", text_clean, re.IGNORECASE)
                        if qty_match:
                            metadata["quantity"] = int(qty_match.group(1))
                            
                    except Exception as e:
                        logger.warning(f"Error parsing PDF text for {pdf_name}: {e}")
                        metadata["delivery_date"] = (99, 99)
                        metadata["order_time"] = 999999999
                
                parsed_files.append({
                    "name": pdf_name,
                    "bytes": pdf_bytes,
                    **metadata
                })
            
            # Маппинг старых значений из фронтенда на новые, если они остались старыми
            sort_map = {
                "none": "no_sort",
                "time": "order_time_oldest_first",
                "date": "delivery_date_nearest",
                "quantity": "quantity_asc",
                "product": "group_by_product",
            }
            mapped_sort = sort_map.get(sort, sort)

            if mapped_sort == "order_time_oldest_first":
                parsed_files.sort(key=lambda x: x["order_time"])
            elif mapped_sort == "delivery_date_nearest":
                parsed_files.sort(key=lambda x: x["delivery_date"])
            elif mapped_sort == "quantity_asc":
                parsed_files.sort(key=lambda x: (x["quantity"], x["product_name"]))
            elif mapped_sort == "group_by_product":
                parsed_files.sort(key=lambda x: (x["product_name"], x["quantity"]))
            else:
                parsed_files.sort(key=lambda x: x["original_index"])

            all_pages = []
            
            # Read and extract all pages in sorted order
            for item in parsed_files:
                reader = PdfReader(io.BytesIO(item["bytes"]))
                for page in reader.pages:
                    orig_w = float(page.mediabox.right - page.mediabox.left)
                    
                    if orig_w > 400:
                        # Kaspi default label is on top-left of A4
                        # Crop to A6 size (top-left quadrant)
                        page.mediabox.upper_right = (297.638, 842.0)
                        page.mediabox.lower_left = (0, 421.0)
                        page.cropbox.upper_right = (297.638, 842.0)
                        page.cropbox.lower_left = (0, 421.0)
                        is_a4 = True
                    else:
                        is_a4 = False
                        
                    all_pages.append((page, is_a4))
                    
            if format == "thermal":
                # For thermal printer, just output the cropped A6 pages
                for p, is_a4 in all_pages:
                    if is_a4:
                        # Shift down by 421 and adjust to 0-based
                        p.add_transformation(Transformation().translate(tx=0, ty=-421.0))
                        p.mediabox.upper_right = (297.638, 421.0)
                        p.mediabox.lower_left = (0, 0)
                        p.cropbox.upper_right = (297.638, 421.0)
                        p.cropbox.lower_left = (0, 0)
                    writer.add_page(p)
                    
            elif format == "a4":
                # Group by 4 and merge onto new A4 pages
                for i in range(0, len(all_pages), 4):
                    chunk = all_pages[i:i+4]
                    merged_page = PageObject.create_blank_page(width=A4_WIDTH, height=A4_HEIGHT)
                    
                    if len(chunk) > 0:
                        p, is_a4 = chunk[0]
                        # If it's already a thermal label, we might need to shift it up to y=421
                        if not is_a4:
                            p.add_transformation(Transformation().translate(tx=0, ty=421.0))
                        merged_page.merge_page(p)
                    if len(chunk) > 1:
                        p, is_a4 = chunk[1]
                        if is_a4:
                            p.add_transformation(Transformation().translate(tx=297.638, ty=0))
                        else:
                            p.add_transformation(Transformation().translate(tx=297.638, ty=421.0))
                        merged_page.merge_page(p)
                    if len(chunk) > 2:
                        p, is_a4 = chunk[2]
                        if is_a4:
                            p.add_transformation(Transformation().translate(tx=0, ty=-421.0))
                        else:
                            pass # Already at 0,0
                        merged_page.merge_page(p)
                    if len(chunk) > 3:
                        p, is_a4 = chunk[3]
                        if is_a4:
                            p.add_transformation(Transformation().translate(tx=297.638, ty=-421.0))
                        else:
                            p.add_transformation(Transformation().translate(tx=297.638, ty=0))
                        merged_page.merge_page(p)
                        
                    writer.add_page(merged_page)
            else:
                raise HTTPException(status_code=400, detail="Неверный формат печати.")
                
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Некорректный ZIP архив. Попробуйте скачать заново с Kaspi.")
    except Exception as e:
        logger.exception("Waybill processing failed")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")
        
    out_pdf = io.BytesIO()
    writer.write(out_pdf)
    out_pdf.seek(0)
    
    if current_user.email != "karimbai.ali10@mail.ru":
        current_user.waybills_used = getattr(current_user, 'waybills_used', 0) + 1
        await db.commit()
    
    return StreamingResponse(
        out_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=waybills_{format}.pdf",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
