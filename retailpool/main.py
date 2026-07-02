"""
RetailPool AI v2.0 — FastAPI Application Entry Point.

Features:
  - Lifespan management (DB, Redis)
  - JWT Authentication + API Key middleware
  - CORS
  - Static frontend serving
  - Health check
  - Pool, Scanner, Documents & Auth routers
"""

from __future__ import annotations

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Security, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from retailpool.config import settings
from retailpool.database import engine
from retailpool.routers.pools import router as pools_router
from retailpool.routers.scanner import router as scanner_router
from retailpool.routers.documents import router as documents_router
from retailpool.routers.auth import router as auth_router
from retailpool.routers.scan_api import router as scan_api_router
from retailpool.routers.subscriptions import router as subscriptions_router
from retailpool.routers.ntin import router as ntin_router
from retailpool.routers.repricing import router as repricing_router
from retailpool.routers.analytics import router as analytics_router
from retailpool.routers.reviews import router as reviews_router
from retailpool.routers.waybills import router as waybills_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)

# Path to frontend directory
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ═══════════════════════════════════════════════════════════════════════════
# Lifespan — startup / shutdown hooks
# ═══════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup / shutdown hooks.

    NOTE: Database tables are managed by Alembic migrations.
    Run `alembic upgrade head` before starting the server.
    """
    logger.info("Starting RetailPool AI v2.0 ...")
    logger.info("Database: %s", settings.DATABASE_URL[:50] + "...")
    logger.info("Frontend dir: %s (exists: %s)", FRONTEND_DIR, FRONTEND_DIR.exists())

    # Auto-create tables (including new Subscription table)
    from retailpool.models.base import Base
    from retailpool.models import subscription  # noqa: F401 — register model
    from retailpool.bot import models as _bot_models  # noqa: F401 — register bot models
    from retailpool.models import ntin as _ntin_models  # noqa: F401 — register NTIN models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured.")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("RetailPool AI shut down.")


# ═══════════════════════════════════════════════════════════════════════════
# API Key Security (MVP — static token, kept for service-to-service)
# ═══════════════════════════════════════════════════════════════════════════

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


import secrets

async def get_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """Validate the static API key from request headers."""
    if api_key and secrets.compare_digest(api_key, settings.API_KEY):
        return api_key
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or missing API key",
    )


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="RetailPool AI v2.0",
    description=(
        "Omnichannel analytics & co-buying platform. "
        "Kaspi niche scanning + cooperative purchasing engine."
    ),
    version="2.0.0-mvp",
    lifespan=lifespan,
)

# CORS (allow all for MVP; restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ──────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(pools_router)
app.include_router(scanner_router)
app.include_router(documents_router)
app.include_router(scan_api_router)
app.include_router(subscriptions_router)
app.include_router(ntin_router)
app.include_router(repricing_router)
app.include_router(analytics_router)
app.include_router(reviews_router)
app.include_router(waybills_router)


# ── Static assets (CSS, JS) ─────────────────────────────────────────────
if FRONTEND_DIR.exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


# ── Health check (no auth required) ──────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check() -> dict:
    return {"status": "ok", "service": "retailpool-ai", "version": "2.0.0-mvp"}


# ── Protected endpoint example (API key) ─────────────────────────────────

@app.get("/protected", tags=["System"])
async def protected_route(api_key: str = Security(get_api_key)) -> dict:
    """Example protected endpoint — requires X-API-Key header."""
    return {"status": "authenticated", "message": "API key is valid"}


# ═══════════════════════════════════════════════════════════════════════════
# Frontend HTML page routes
# ═══════════════════════════════════════════════════════════════════════════

def _serve_page(filename: str):
    """Return a FileResponse for a frontend HTML page."""
    filepath = FRONTEND_DIR / filename
    if filepath.exists():
        return FileResponse(str(filepath), media_type="text/html")
    raise HTTPException(status_code=404, detail="Page not found")


# ── Page route mapping: (clean_path, html_filename) ─────────────────────
_PAGE_ROUTES = [
    ("/",            "index.html"),
    ("/scanner",     "scanner.html"),
    ("/pools-page",  "pools.html"),
    ("/pricing",     "pricing.html"),
    ("/checkout",    "checkout.html"),
    ("/auth",        "auth.html"),
    ("/ntin",        "ntin.html"),
    ("/kaspi-bot",   "kaspi-bot.html"),
    ("/analytics",   "analytics.html"),
    ("/reviews",     "reviews.html"),
    ("/waybills",    "waybills.html"),
    ("/dashboard",   "dashboard.html"),
]

for _path, _filename in _PAGE_ROUTES:
    # Register clean path
    app.get(_path, tags=["Frontend"], include_in_schema=False)(
        lambda f=_filename: _serve_page(f)
    )
    # Also register .html path so frontend links work too
    if _path != "/":
        app.get(f"/{_filename}", tags=["Frontend"], include_in_schema=False)(
            lambda f=_filename: _serve_page(f)
        )

# Also handle index.html explicitly
@app.get("/index.html", tags=["Frontend"], include_in_schema=False)
async def serve_index_html():
    return _serve_page("index.html")


# Also handle pools.html directly (since some pages link to it)
@app.get("/pools.html", tags=["Frontend"], include_in_schema=False)
async def serve_pools_html():
    return _serve_page("pools.html")
