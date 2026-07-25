"""
Kaspi Seller API client for product price management.

Handles:
  - Fetching merchant product catalog
  - Updating product prices via Seller API
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

KASPI_SELLER_API_BASE = "https://kaspi.kz/shop/api/v2"


class KaspiSellerClient:
    """Async client for Kaspi Seller API."""

    def __init__(self, api_token: str) -> None:
        self._token = api_token
        self._headers = {
            "X-Auth-Token": api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    async def get_products(self, page: int = 0, size: int = 100) -> list[dict[str, Any]]:
        """Fetch merchant's active products from Kaspi Seller API.

        Returns a list of product dicts with keys like:
          - masterSku, name, price, etc.
        """
        url = f"{KASPI_SELLER_API_BASE}/products"
        params = {"page[number]": page, "page[size]": size}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def get_all_products(self, size: int = 100) -> list[dict[str, Any]]:
        """Fetch ALL merchant's products by paginating through Kaspi Seller API."""
        url = f"{KASPI_SELLER_API_BASE}/products"
        all_products = []
        page = 0
        
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params = {"page[number]": page, "page[size]": size}
                resp = await client.get(url, headers=self._headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                items = data.get("data", [])
                if not items:
                    break
                    
                all_products.extend(items)
                
                # Check pagination metadata
                meta = data.get("meta", {})
                page_count = meta.get("pageCount", 1)
                
                page += 1
                if page >= page_count:
                    break
                    
        return all_products

    async def update_price(self, master_sku: str, new_price: float) -> dict[str, Any]:
        """Update the price of a product via Kaspi Seller API.

        Args:
            master_sku: The Kaspi masterSku of the product.
            new_price: The new price in KZT.

        Returns:
            API response dict.
        """
        url = f"{KASPI_SELLER_API_BASE}/products"
        payload = {
            "data": {
                "type": "MasterProduct",
                "attributes": {
                    "masterSku": master_sku,
                    "price": int(new_price),
                }
            }
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(url, headers=self._headers, json=payload)
            resp.raise_for_status()
            result = resp.json()

            logger.info(
                "Kaspi price updated: SKU=%s new_price=%s",
                master_sku, int(new_price)
            )
            return result

    async def get_orders(
        self,
        status: str | None = None,
        creation_date_ge_ms: int | None = None,
        creation_date_le_ms: int | None = None,
        page: int = 0,
        size: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetch orders from Kaspi Seller API, optionally filtered by status/date.

        Returns (orders, total_count) where total_count comes from the API's
        pagination metadata (used to compute cancellation rate cheaply).
        """
        url = f"{KASPI_SELLER_API_BASE}/orders"
        params: dict[str, Any] = {"page[number]": page, "page[size]": size}
        if status:
            params["filter[orders][status]"] = status
        if creation_date_ge_ms is not None:
            params["filter[orders][creationDate][$ge]"] = creation_date_ge_ms
        if creation_date_le_ms is not None:
            params["filter[orders][creationDate][$le]"] = creation_date_le_ms

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            total = data.get("meta", {}).get("totalCount", len(data.get("data", [])))
            return data.get("data", []), total

    async def get_cancellation_rate(self, days: int = 30) -> dict[str, Any]:
        """Compute the order cancellation rate over the last `days` days.

        Uses the totalCount from pagination metadata for both the full
        order count and the CANCELLED subset — avoids downloading every
        order just to count them.
        """
        import time

        now_ms = int(time.time() * 1000)
        since_ms = now_ms - days * 24 * 60 * 60 * 1000

        _, total = await self.get_orders(
            creation_date_ge_ms=since_ms, creation_date_le_ms=now_ms, size=1,
        )
        _, cancelled = await self.get_orders(
            status="CANCELLED",
            creation_date_ge_ms=since_ms, creation_date_le_ms=now_ms, size=1,
        )

        rate = (cancelled / total * 100) if total > 0 else 0.0
        return {"total": total, "cancelled": cancelled, "rate_percent": round(rate, 2)}

    async def get_negative_reviews(
        self, since_ms: int | None = None, page: int = 0, size: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch reviews rated 3 stars or less (Kaspi's own NEGATIVE bucket).

        If since_ms is given, only reviews approved after that timestamp
        are returned (caller should further filter by exact rating, e.g. ==1).
        """
        import time

        url = f"{KASPI_SELLER_API_BASE}/merchantreviews/"
        now_ms = int(time.time() * 1000)
        start_ms = since_ms if since_ms is not None else now_ms - 30 * 24 * 60 * 60 * 1000

        params = {
            "page[number]": page,
            "page[size]": size,
            "filter[merchantreviews][quality]": "NEGATIVE",
            "filter[merchantreviews][approvedDate][$ge]": start_ms,
            "filter[merchantreviews][approvedDate][$le]": now_ms,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def test_connection(self) -> bool:
        """Verify the API token is valid by fetching first page of products."""
        try:
            products = await self.get_products(page=0, size=1)
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("Kaspi API token test failed: %s", e.response.status_code)
            return False
        except Exception as e:
            logger.warning("Kaspi API connection failed: %s", e)
            return False
