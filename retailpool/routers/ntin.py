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

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import async_session_factory, get_db
from retailpool.services.ntin_service import NtinService
from retailpool.models.ntin import NtinStatus
from retailpool.models.user import User
from retailpool.services.auth_service import get_current_user

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
    nkt_api_key: str | None = None


class SellerSettingsResponse(BaseModel):
    has_kaspi_key: bool = False
    kaspi_merchant_id: str | None = None
    kaspi_shop_name: str | None = None
    has_nkt_key: bool = False


class BulkImportRequest(BaseModel):
    products: list[NtinProductCreate]


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


@router.post("/requests/sync")
async def sync_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Sync statuses of all active requests from НКТ."""
    svc = NtinService(db)
    result = await svc.sync_nkt_requests(current_user.id)
    return {"status": "ok", "synced": result}


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
                has_nkt_key=bool(settings.nkt_api_key),
            )
