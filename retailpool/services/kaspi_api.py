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
