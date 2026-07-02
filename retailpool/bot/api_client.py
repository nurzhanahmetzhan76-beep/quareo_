"""
API Client — async httpx client to the RetailPool FastAPI backend.

All bot handlers use this client to interact with the existing REST API
instead of importing services directly (clean separation of concerns).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from retailpool.bot.config import bot_settings

logger = logging.getLogger(__name__)

# Reusable client (created once, shared across handlers)
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=bot_settings.API_BASE_URL,
            headers={"X-API-Key": bot_settings.API_KEY},
            timeout=60.0,
        )
    return _client


async def close_client() -> None:
    """Shutdown the shared httpx client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


class RetailPoolAPI:
    """Typed wrapper around the FastAPI backend endpoints."""

    # ── Pools ────────────────────────────────────────────────────────────

    @staticmethod
    async def get_open_pools() -> list[dict[str, Any]]:
        """Fetch all open co-buying pools."""
        r = await _get_client().get("/pools/open")
        r.raise_for_status()
        return r.json()

    @staticmethod
    async def get_pool_status(pool_id: str) -> dict[str, Any]:
        """Get full pool status with quorum progress."""
        r = await _get_client().get(f"/pools/{pool_id}/status")
        r.raise_for_status()
        return r.json()

    @staticmethod
    async def join_pool(
        pool_id: str, user_id: str, quantity: int, amount: float
    ) -> dict[str, Any]:
        """Join an existing pool."""
        r = await _get_client().post(
            f"/pools/{pool_id}/join",
            json={
                "user_id": user_id,
                "quantity": quantity,
                "amount": amount,
            },
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    async def create_pool(
        product_id: str,
        product_name: str,
        supplier_name: str,
        target_quantity: int,
        target_amount: float,
        expires_in_hours: int = 72,
    ) -> dict[str, Any]:
        """Create a new co-buying pool."""
        r = await _get_client().post(
            "/pools/create",
            json={
                "product_id": product_id,
                "product_name": product_name,
                "supplier_name": supplier_name,
                "target_quantity": target_quantity,
                "target_amount": target_amount,
                "expires_in_hours": expires_in_hours,
            },
        )
        r.raise_for_status()
        return r.json()

    # ── Scanner ──────────────────────────────────────────────────────────

    @staticmethod
    async def scan_niche(query: str) -> dict[str, Any]:
        """Run a niche scan via the /api/scan endpoint."""
        r = await _get_client().post(
            "/api/scan",
            json={"query": query},
        )
        r.raise_for_status()
        return r.json()

    # ── Documents ────────────────────────────────────────────────────────

    @staticmethod
    async def get_invoice(pool_id: str) -> dict[str, Any]:
        """Request invoice generation for a closed pool."""
        r = await _get_client().post(f"/documents/invoice/{pool_id}")
        r.raise_for_status()
        return r.json()

    # ── Health ───────────────────────────────────────────────────────────

    @staticmethod
    async def health_check() -> dict[str, Any]:
        """Check if the backend is alive."""
        r = await _get_client().get("/health")
        r.raise_for_status()
        return r.json()
