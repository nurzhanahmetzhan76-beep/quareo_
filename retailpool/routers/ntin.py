"""
NTIN Router — API endpoints for NTIN marking and НКТ integration.

Endpoints:
  - Product CRUD with NTIN status tracking
  - AI auto-fill (ТН ВЭД code + Kazakh translation)
  - Submit to НКТ
  - ТН ВЭД code search
  - User seller settings (API keys)
  - Stats dashboard
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Query, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import async_session_factory, get_db
from retailpool.services.ntin_service import NtinService
from retailpool.models.ntin import NtinStatus, NtinProduct
from sqlalchemy import select
from retailpool.models.user import User
from retailpool.services.auth_service import get_current_user
from fastapi.responses import StreamingResponse
import io
import openpyxl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ntin", tags=["NTIN Marking"])


# ═══════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════

class NtinProductCreate(BaseModel):
    title_ru: str = Field(..., min_length=2, max_length=512)
    description_ru: str | None = None
    barcode: str | None = None
    kaspi_sku: str | None = None
    brand: str | None = None
    country_of_origin: str | None = "Китай"
    unit_of_measure: str | None = "шт"
    weight_kg: float | None = None
    price: float | None = None
    image_url: str | None = None
    oktru_code: str | None = None


class NtinProductResponse(BaseModel):
    id: str
    title_ru: str
    title_kz: str | None = None
    description_ru: str | None = None
    description_kz: str | None = None
    barcode: str | None = None
    kaspi_sku: str | None = None
    ntin_code: str | None = None
    nkt_request_id: int | None = None
    oktru_code: str | None = None
    tn_ved_code: str | None = None
    tn_ved_name: str | None = None
    brand: str | None = None
    country_of_origin: str | None = None
    unit_of_measure: str | None = None
    weight_kg: float | None = None
    price: float | None = None
    image_url: str | None = None
    status: str
    revision_comment: str | None = None
    created_at: str
    updated_at: str
    submitted_at: str | None = None
    approved_at: str | None = None


class NtinProductUpdate(BaseModel):
    title_ru: str | None = None
    title_kz: str | None = None
    description_ru: str | None = None
    description_kz: str | None = None
    barcode: str | None = None
    tn_ved_code: str | None = None
    tn_ved_name: str | None = None
    oktru_code: str | None = None
    brand: str | None = None
    country_of_origin: str | None = None
    unit_of_measure: str | None = None
    weight_kg: float | None = None
    price: float | None = None


class TnVedSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)


class TnVedResult(BaseModel):
    code: str
    name: str


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)


class SellerSettingsRequest(BaseModel):
    kaspi_api_key: str | None = None
    kaspi_merchant_id: str | None = None
    kaspi_shop_name: str | None = None
    kaspi_xml_url: str | None = None
    nkt_api_key: str | None = None


class SellerSettingsResponse(BaseModel):
    has_kaspi_key: bool = False
    kaspi_merchant_id: str | None = None
    kaspi_shop_name: str | None = None
    kaspi_xml_url: str | None = None
    has_nkt_key: bool = False


class BulkImportRequest(BaseModel):
    products: list[NtinProductCreate]


class NtinTemplatesRequest(BaseModel):
    tpl_country: str | None = None
    tpl_brand: str | None = None
    tpl_unit: str | None = None
    tpl_qty: int | None = None


class NtinStatsResponse(BaseModel):
    total: int = 0
    draft: int = 0
    ai_filled: int = 0
    ready: int = 0
    submitted: int = 0
    revision: int = 0
    approved: int = 0
    rejected: int = 0


# ═══════════════════════════════════════════════════════════════════════════
# Helper: get mock user_id (will use real auth later)
# ═══════════════════════════════════════════════════════════════════════════

# Use a deterministic UUID for demo/MVP until auth is properly wired


def _safe_iso(dt) -> str | None:
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    try:
        return dt.isoformat()
    except AttributeError:
        return str(dt)

def _product_to_response(p) -> NtinProductResponse:
    # Ensure status is a string (in case it's an Enum object)
    status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
    
    return NtinProductResponse(
        id=str(p.id),
        title_ru=p.title_ru,
        title_kz=p.title_kz,
        description_ru=p.description_ru,
        description_kz=p.description_kz,
        barcode=p.barcode,
        kaspi_sku=p.kaspi_sku,
        ntin_code=p.ntin_code,
        nkt_request_id=p.nkt_request_id,
        oktru_code=p.oktru_code,
        tn_ved_code=p.tn_ved_code,
        tn_ved_name=p.tn_ved_name,
        brand=p.brand,
        country_of_origin=p.country_of_origin,
        unit_of_measure=p.unit_of_measure,
        weight_kg=p.weight_kg,
        price=p.price,
        image_url=p.image_url,
        status=status_val,
        revision_comment=p.revision_comment,
        created_at=_safe_iso(p.created_at) or "",
        updated_at=_safe_iso(p.updated_at) or "",
        submitted_at=_safe_iso(p.submitted_at),
        approved_at=_safe_iso(p.approved_at),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/products", response_model=list[NtinProductResponse])
async def list_products(status: str | None = None, current_user: User = Depends(get_current_user)):
    """List all NTIN products for the current user."""
    async with async_session_factory() as session:
        svc = NtinService(session)
        products = await svc.get_products(current_user.id, status_filter=status)
        return [_product_to_response(p) for p in products]


@router.get("/products/{product_id}", response_model=NtinProductResponse)
async def get_product(product_id: str, current_user: User = Depends(get_current_user)):
    """Get a single NTIN product."""
    async with async_session_factory() as session:
        svc = NtinService(session)
        product = await svc.get_product(uuid.UUID(product_id), current_user.id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return _product_to_response(product)


@router.post("/products", response_model=NtinProductResponse)
async def create_product(data: NtinProductCreate, current_user: User = Depends(get_current_user)):
    """Create a new NTIN product card."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            
            if current_user.email != "karimbai.ali10@mail.ru":
                stats = await svc.get_stats(current_user.id)
                plan_limits = {
                    "free": 2,
                    "start": 20,
                    "business": 100,
                    "unlimited": 200
                }
                user_plan = current_user.plan or "free"
                limit = plan_limits.get(user_plan.lower(), 0)
                if stats["total"] >= limit:
                    if user_plan.lower() == "free":
                         raise HTTPException(status_code=403, detail="Вы исчерпали лимит бесплатного тарифа (2 NTIN регистрации). Пожалуйста, выберите платный тариф.")
                    raise HTTPException(status_code=403, detail="Лимит NTIN регистраций исчерпан. Пожалуйста, обновите тариф.")
                    
            product = await svc.create_product(current_user.id, data.model_dump())
            return _product_to_response(product)


@router.put("/products/{product_id}", response_model=NtinProductResponse)
async def update_product(product_id: str, data: NtinProductUpdate, current_user: User = Depends(get_current_user)):
    """Update an NTIN product card."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            product = await svc.get_product(uuid.UUID(product_id), current_user.id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")

            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(product, key, value)

            # If user manually edits after AI fill, mark as ready
            if product.status == NtinStatus.AI_FILLED:
                product.status = NtinStatus.READY

            return _product_to_response(product)


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(get_current_user)):
    """Delete an NTIN product card."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            product = await svc.get_product(uuid.UUID(product_id), current_user.id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            await session.delete(product)
            return {"status": "deleted", "id": product_id}


@router.post("/products/{product_id}/ai-fill", response_model=NtinProductResponse)
async def ai_fill_product(product_id: str, current_user: User = Depends(get_current_user)):
    """AI auto-fill: ТН ВЭД code + Kazakh translation."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            product = await svc.ai_fill_product(uuid.UUID(product_id), current_user.id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            return _product_to_response(product)


from fastapi import BackgroundTasks

async def _bg_mass_ai_fill(user_id: uuid.UUID):
    """Background task for mass AI fill. Commits each product separately."""
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(
            NtinProduct.user_id == user_id,
            NtinProduct.status == NtinStatus.DRAFT
        )
        result = await session.execute(stmt)
        drafts = result.scalars().all()
        
    for p in drafts:
        # Process each product in its own transaction
        async with async_session_factory() as session:
            async with session.begin():
                svc = NtinService(session)
                try:
                    await svc.ai_fill_product(p.id, user_id)
                except Exception as e:
                    logger.error("Error AI filling product %s: %s", p.id, e)

@router.post("/mass-ai-fill")
async def mass_ai_fill(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Start AI fill for all draft products in the background."""
    background_tasks.add_task(_bg_mass_ai_fill, current_user.id)
    return {"status": "ok", "message": "started"}


async def _bg_mass_submit(user_id: uuid.UUID):
    """Background task for mass NKT submit."""
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(
            NtinProduct.user_id == user_id,
            NtinProduct.status == NtinStatus.AI_FILLED
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
    for p in products:
        async with async_session_factory() as session:
            async with session.begin():
                svc = NtinService(session)
                try:
                    await svc.submit_to_nkt(p.id, user_id)
                except Exception as e:
                    logger.error("Error submitting product %s: %s", p.id, e)

@router.post("/mass-submit")
async def mass_submit(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Start NKT submission for all AI-filled products in the background."""
    background_tasks.add_task(_bg_mass_submit, current_user.id)
    return {"status": "ok", "message": "started"}

@router.get("/export-excel")
async def export_excel(current_user: User = Depends(get_current_user)):
    """Export products with NTIN codes to Excel for Kaspi."""
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(
            NtinProduct.user_id == current_user.id,
            NtinProduct.ntin_code.isnot(None)
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NTIN Коды"
    ws.append(["Артикул (SKU)", "Название товара", "Новый Штрихкод (NTIN)"])
    
    for p in products:
        ws.append([
            p.kaspi_sku or "",
            p.title_ru or "",
            p.ntin_code or ""
        ])
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ntin_for_1c_moysklad.xlsx"}
    )

@router.get("/export-json")
async def export_json(current_user: User = Depends(get_current_user)):
    """Export products with NTIN codes to JSON for Chrome Extension."""
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(
            NtinProduct.user_id == current_user.id,
            NtinProduct.ntin_code.isnot(None)
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
    return {
        "products": [
            {"sku": p.kaspi_sku, "barcode": p.ntin_code} 
            for p in products if p.kaspi_sku and p.ntin_code
        ]
    }


@router.post("/products/{product_id}/submit", response_model=NtinProductResponse)
async def submit_product(product_id: str, current_user: User = Depends(get_current_user)):
    """Submit product card to НКТ for NTIN assignment."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            product = await svc.submit_to_nkt(uuid.UUID(product_id), current_user.id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            return _product_to_response(product)


@router.post("/products/{product_id}/check-status", response_model=NtinProductResponse)
async def check_product_status(product_id: str, current_user: User = Depends(get_current_user)):
    """Check the status of a submitted product in НКТ."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            product = await svc.check_nkt_status(uuid.UUID(product_id), current_user.id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            return _product_to_response(product)


async def _bg_sync_requests(user_id: uuid.UUID):
    """Background task for syncing NKT statuses."""
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(
            NtinProduct.user_id == user_id,
            NtinProduct.nkt_request_id.isnot(None),
            NtinProduct.status.in_([NtinStatus.SUBMITTED, NtinStatus.REVISION]),
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
    for p in products:
        async with async_session_factory() as session:
            async with session.begin():
                svc = NtinService(session)
                try:
                    await svc.check_nkt_status(p.id, user_id)
                except Exception as e:
                    logger.error("Error syncing NKT request %s: %s", p.id, e)

@router.post("/requests/sync")
async def sync_requests(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Sync statuses of all active requests from НКТ in the background."""
    background_tasks.add_task(_bg_sync_requests, current_user.id)
    return {"status": "ok", "message": "started"}


@router.post("/fetch-kaspi")
async def fetch_kaspi_products(current_user: User = Depends(get_current_user)):
    """Fetch Kaspi products from the user's XML feed."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            settings = await svc.get_settings(current_user.id)
            if not settings or not settings.kaspi_xml_url:
                raise HTTPException(status_code=400, detail="XML ссылка не указана в настройках")
            
            try:
                imported_count = await svc.fetch_kaspi_xml(current_user.id, settings.kaspi_xml_url)
                return {"status": "ok", "imported": imported_count}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка обработки XML: {str(e)}")


@router.post("/upload-kaspi")
async def upload_kaspi_products(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload Kaspi XML or Excel file."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            try:
                content = await file.read()
                imported_count = await svc.parse_kaspi_file(current_user.id, content, file.filename)
                return {"status": "ok", "imported": imported_count}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {str(e)}")


@router.get("/oktru/search")
async def search_oktru(
    q: str = Query(..., min_length=2, description="Поисковый запрос (например: копилка)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Поиск кодов ОКТРУ напрямую через API НКТ."""
    svc = NtinService(db)
    api_key = await svc._get_nkt_api_key(current_user.id)
    if not api_key or api_key == "test_api_key_12345":
        raise HTTPException(
            status_code=400,
            detail="Для поиска ОКТРУ необходимо указать реальный API-ключ НКТ в настройках."
        )

    import httpx
    import urllib.parse
    base_url = "https://nationalcatalog.kz/gwp"
    headers = {"X-API-KEY": api_key, "Accept": "application/json"}
    url = f"{base_url}/portal/api/v1/dictionaries/OKTRU/items?page=1&size=100&search={urllib.parse.quote(q)}"
    root_word = q.lower()[:5] if len(q) > 5 else q.lower()
    safe_root = root_word.replace("%", "\\%").replace("_", "\\_")
    
    def score_item(item):
        name_ru = str(item.get("nameRu", "")).lower()
        if q.lower() in name_ru:
            return 2
        if root_word in name_ru:
            return 1
        return 0

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("content", [])
                level4_items = [i for i in items if i.get("code") and str(i.get("code")).count("-") == 3]
                level4_items.sort(key=lambda x: score_item(x), reverse=True)
                display_items = level4_items if level4_items else items
                results = [{"code": item.get("code"), "name": item.get("nameRu", "")} for item in display_items[:20]]
            elif resp.status_code == 429:
                results = [] # Rate limit, rely entirely on local DB
            elif resp.status_code == 401:
                raise HTTPException(status_code=401, detail="API-ключ НКТ недействителен.")
            else:
                results = []
    except Exception:
        results = []

    # Fetch from local OKTRU dictionary
    from sqlalchemy import select
    from retailpool.models.ntin import OktruDictionary
    local_results = await db.execute(select(OktruDictionary).where(OktruDictionary.search_vector.like(f"%{safe_root}%")).limit(20))
    local_codes = local_results.scalars().all()
    
    added_codes = {r["code"] for r in results}
    
    for c in reversed(local_codes):
        if c.code not in added_codes:
            results.insert(0, {"code": c.code, "name": f"🗃️ БАЗА: {c.name_ru}"})
            added_codes.add(c.code)
            
    # INJECT KNOWN CODES
    from retailpool.services.ntin_service import _fuzzy_match_tn_ved
    db_matches = _fuzzy_match_tn_ved(q)
    for match in reversed(db_matches):
        if match.get("oktru_code") and match["oktru_code"] != "1106-0001-0001-100011943":
            if match["oktru_code"] not in added_codes:
                results.insert(0, {"code": match["oktru_code"], "name": f"✨ НАЙДЕНО ИИ: {match['name']}"})
                added_codes.add(match["oktru_code"])
            
    if not results:
        return {"results": [{"code": "", "name": "❌ НКТ временно недоступен (Лимит запросов), а в базе товар еще не найден."}]}
        
    return {"results": results}


@router.post("/bulk-import", response_model=list[NtinProductResponse])
async def bulk_import(data: BulkImportRequest, current_user: User = Depends(get_current_user)):
    """Bulk import products for NTIN processing."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            products = await svc.bulk_import(
                current_user.id,
                [p.model_dump() for p in data.products]
            )
            return [_product_to_response(p) for p in products]


@router.get("/stats", response_model=NtinStatsResponse)
async def get_stats(current_user: User = Depends(get_current_user)):
    """Get NTIN status counts for the current user."""
    async with async_session_factory() as session:
        svc = NtinService(session)
        stats = await svc.get_stats(current_user.id)
        return NtinStatsResponse(**stats)


# ── ТН ВЭД Search ───────────────────────────────────────────────────────

@router.post("/tn-ved/search", response_model=list[TnVedResult])
async def search_tn_ved(data: TnVedSearchRequest, current_user: User = Depends(get_current_user)):
    """Search ТН ВЭД ЕАЭС codes by product description."""
    results = NtinService.search_tn_ved(data.query)
    return [TnVedResult(**r) for r in results]


# ── Translation ─────────────────────────────────────────────────────────

@router.post("/translate")
async def translate_text(data: TranslateRequest, current_user: User = Depends(get_current_user)):
    """Translate Russian text to Kazakh."""
    kz = NtinService.translate_to_kazakh(data.text)
    return {"original": data.text, "translated": kz}


# ── Seller Settings ──────────────────────────────────────────────────────

@router.get("/settings", response_model=SellerSettingsResponse)
async def get_settings(current_user: User = Depends(get_current_user)):
    """Get current user's seller settings (keys masked)."""
    async with async_session_factory() as session:
        svc = NtinService(session)
        settings = await svc.get_settings(current_user.id)
        if not settings:
            return SellerSettingsResponse()
        return SellerSettingsResponse(
            has_kaspi_key=bool(settings.kaspi_api_key),
            kaspi_merchant_id=settings.kaspi_merchant_id,
            kaspi_shop_name=settings.kaspi_shop_name,
            kaspi_xml_url=settings.kaspi_xml_url,
            has_nkt_key=bool(settings.nkt_api_key),
        )


@router.post("/settings", response_model=SellerSettingsResponse)
async def save_settings(data: SellerSettingsRequest, current_user: User = Depends(get_current_user)):
    """Save seller API keys and settings."""
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            settings = await svc.save_settings(current_user.id, data.model_dump(exclude_unset=True))
            return SellerSettingsResponse(
                has_kaspi_key=bool(settings.kaspi_api_key),
                kaspi_merchant_id=settings.kaspi_merchant_id,
                kaspi_shop_name=settings.kaspi_shop_name,
                kaspi_xml_url=settings.kaspi_xml_url,
                has_nkt_key=bool(settings.nkt_api_key),
            )

@router.get("/templates", response_model=NtinTemplatesRequest)
async def get_templates(current_user: User = Depends(get_current_user)):
    async with async_session_factory() as session:
        svc = NtinService(session)
        settings = await svc.get_settings(current_user.id)
        if not settings:
            return NtinTemplatesRequest()
        return NtinTemplatesRequest(
            tpl_country=settings.tpl_country or "КИТАЙ",
            tpl_brand=settings.tpl_brand or "Отсутствует",
            tpl_unit=settings.tpl_unit or "шт",
            tpl_qty=settings.tpl_qty or 1
        )

@router.post("/templates", response_model=NtinTemplatesRequest)
async def save_templates(
    data: NtinTemplatesRequest,
    current_user: User = Depends(get_current_user)
):
    async with async_session_factory() as session:
        async with session.begin():
            svc = NtinService(session)
            settings = await svc.save_settings(current_user.id, data.model_dump(exclude_unset=True))
            return NtinTemplatesRequest(
                tpl_country=settings.tpl_country,
                tpl_brand=settings.tpl_brand,
                tpl_unit=settings.tpl_unit,
                tpl_qty=settings.tpl_qty
            )
