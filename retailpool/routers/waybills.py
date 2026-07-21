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
            for pdf_name in pdf_files:
                pdf_bytes = z.read(pdf_name)
                sort_date = (99, 99)
                product_val = ""
                quantity_val = 999
                
                if sort != "none":
                    try:
                        reader = PdfReader(io.BytesIO(pdf_bytes))
                        text = reader.pages[0].extract_text() or ""
                        
                        if sort in ["date", "product", "quantity"]:
                            # Normalize whitespace to make regex matching more predictable
                            text_clean = re.sub(r'\s+', ' ', text)
                            
                            date_match = re.search(r"(?:дата доставки|доставки)[\s:]*(\d{1,2})\s*([а-яА-ЯёЁa-zA-Z]+)", text_clean, re.IGNORECASE)
                            if date_match:
                                sort_date = parse_date(date_match.group(1), date_match.group(2))
                                
                            prod_match = re.search(r"1\s*\.\s*(.*?)(?=\s+\d+\s*шт|\s+Итого|$)", text_clean, re.IGNORECASE)
                            if prod_match:
                                product_val = prod_match.group(1).strip()
                                        
                            qty_matches = re.findall(r"(\d+)\s*шт", text_clean, re.IGNORECASE)
                            if qty_matches:
                                quantity_val = sum(int(q) for q in qty_matches)
                    except Exception as e:
                        logger.warning(f"Error parsing PDF text for {pdf_name}: {e}")
                
                parsed_files.append({
                    "name": pdf_name,
                    "bytes": pdf_bytes,
                    "date": sort_date,
                    "product": product_val,
                    "quantity": quantity_val
                })
            
            def get_order_id(name):
                match = re.search(r'\d+', name)
                return int(match.group()) if match else 0

            if sort == "date":
                parsed_files.sort(key=lambda x: (x["date"][0], x["date"][1], x["product"]))
            elif sort == "product":
                parsed_files.sort(key=lambda x: (x["product"], x["date"][0], x["date"][1]))
            elif sort == "quantity":
                parsed_files.sort(key=lambda x: (x["quantity"], x["date"][0], x["date"][1]))
            elif sort == "time":
                parsed_files.sort(key=lambda x: get_order_id(x["name"]))

            all_pages = []
            
            # Read and extract the top-left quadrant of all pages in sorted order
            for item in parsed_files:
                reader = PdfReader(io.BytesIO(item["bytes"]))
                for page in reader.pages:
                    # Kaspi default label is on top-left of A4
                    # Crop to A6 size (top-left quadrant)
                    # Original A4: (0, 0) to (595.276, 842.0)
                    # Target: (0, 421.0) to (297.638, 842.0)
                    page.mediabox.upper_right = (297.638, 842.0)
                    page.mediabox.lower_left = (0, 421.0)
                    
                    # Also update cropbox to match
                    page.cropbox.upper_right = (297.638, 842.0)
                    page.cropbox.lower_left = (0, 421.0)
                    
                    all_pages.append(page)
                    
            if format == "thermal":
                # For thermal printer, just output the cropped A6 pages
                # Translate to (0,0) origin for better compatibility
                for p in all_pages:
                    # Shift down by 421
                    p.add_transformation(Transformation().translate(tx=0, ty=-421.0))
                    # Adjust box to 0-based
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
                        # Top Left - No translation needed, it's already at y=421
                        merged_page.merge_page(chunk[0])
                    if len(chunk) > 1:
                        # Top Right - Shift Right by 297.638
                        chunk[1].add_transformation(Transformation().translate(tx=297.638, ty=0))
                        merged_page.merge_page(chunk[1])
                    if len(chunk) > 2:
                        # Bottom Left - Shift Down by 421
                        chunk[2].add_transformation(Transformation().translate(tx=0, ty=-421.0))
                        merged_page.merge_page(chunk[2])
                    if len(chunk) > 3:
                        # Bottom Right - Shift Right and Down
                        chunk[3].add_transformation(Transformation().translate(tx=297.638, ty=-421.0))
                        merged_page.merge_page(chunk[3])
                        
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
