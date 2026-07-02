"""
Scanner Router — REST API for triggering niche scans
and retrieving vulnerability analysis results.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.config import TARGET_CATEGORIES
from retailpool.database import get_db
from retailpool.models.product import NicheAnalysis
from retailpool.schemas.product import CategoryScanResult, NicheScoreOut
from retailpool.services.scanner_service import ScannerService

router = APIRouter(prefix="/scanner", tags=["Kaspi Niche Scanner"])


def _get_scanner_service(db: AsyncSession = Depends(get_db)) -> ScannerService:
    return ScannerService(db=db)


@router.post(
    "/scan",
    response_model=list[CategoryScanResult],
    summary="Trigger full scan of all target categories",
)
async def trigger_scan(
    svc: ScannerService = Depends(_get_scanner_service),
) -> list[CategoryScanResult]:
    """
    Launch a synchronous scan across all configured Kaspi categories.
    WARNING: This is a long-running operation (minutes).
    For production, trigger via background task or separate worker.
    """
    results = await svc.scan_all_categories()
    return results


@router.post(
    "/scan/{category_slug}",
    response_model=CategoryScanResult,
    summary="Scan a single category by slug",
)
async def trigger_category_scan(
    category_slug: str,
    svc: ScannerService = Depends(_get_scanner_service),
) -> CategoryScanResult:
    """Scan a specific category from the configured list."""
    cat = next(
        (c for c in TARGET_CATEGORIES if c["slug"] == category_slug),
        None,
    )
    if not cat:
        raise HTTPException(
            status_code=404,
            detail=f"Category '{category_slug}' not in target list. "
                   f"Available: {[c['slug'] for c in TARGET_CATEGORIES]}",
        )
    return await svc.scan_single_category(cat["url"], cat["slug"], cat["name"])


@router.get(
    "/niches",
    response_model=list[NicheScoreOut],
    summary="Get latest niche analysis results",
)
async def get_niches(
    vulnerable_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[NicheScoreOut]:
    """
    Retrieve saved niche analysis results from the database.
    Optionally filter to show only vulnerable niches.
    """
    stmt = select(NicheAnalysis).order_by(NicheAnalysis.analyzed_at.desc())
    if vulnerable_only:
        stmt = stmt.where(NicheAnalysis.is_vulnerable.is_(True))
    stmt = stmt.limit(100)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [NicheScoreOut.model_validate(r) for r in rows]


@router.get(
    "/categories",
    summary="List configured target categories",
)
async def list_categories() -> list[dict]:
    """Return the hardcoded list of target Kaspi categories."""
    return TARGET_CATEGORIES
