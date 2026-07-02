"""
E2E Demo Script — tests the full co-buying flow via HTTP requests.

Demonstrates:
  1. Health check
  2. Seed a test product directly in DB
  3. Create a co-buying pool
  4. Two participants join the pool -> quorum reached -> auto-close
  5. Fetch the finalized invoice JSON

Run:
    python demo_e2e.py
"""

import asyncio
import os
import json
import uuid
import sys

# Force SQLite for local testing
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./dev.db"

import httpx

BASE = "http://127.0.0.1:8000"


async def seed_product():
    """Insert a test product directly into the DB and return its UUID."""
    from retailpool.database import async_session_factory
    from retailpool.models.product import Product

    async with async_session_factory() as session:
        product = Product(
            kaspi_id=f"demo-humidifier-{uuid.uuid4().hex[:6]}",
            title="Uvlajnitel vozduha Xiaomi Deerma DEM-F600",
            category_slug="air-humidifiers",
            url="https://kaspi.kz/shop/p/xiaomi-deerma-dem-f600-108923641/",
            price_min=18990,
            price_max=24990,
            photo_count=7,
            has_infographics=True,
            description_length=450,
            rating=4.6,
            review_count=340,
            seller_count=12,
        )
        session.add(product)
        await session.commit()
        print(f"  Product ID:   {product.id}")
        print(f"  Product Name: {product.title}")
        print(f"  Price:        {product.price_min} - {product.price_max} KZT")
        return product.id


async def main():
    print("=" * 60)
    print("  RetailPool AI v2.0 -- E2E Demo")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=BASE, timeout=10.0) as client:

        # ---- Step 1: Health Check ----
        print("\n[1] Health Check")
        resp = await client.get("/health")
        print(f"  Status: {resp.status_code}")
        print(f"  Body:   {resp.json()}")

        # ---- Step 2: Seed Product ----
        print("\n[2] Seeding test product into DB...")
        product_id = await seed_product()

        # ---- Step 3: Create Pool ----
        print("\n[3] Creating co-buying pool...")
        resp = await client.post("/pools/create", json={
            "product_id": str(product_id),
            "target_quantity": 10,
            "target_amount": 500000,
            "expires_in_hours": 48,
        })
        print(f"  Status: {resp.status_code}")
        pool_data = resp.json()
        pool_id = pool_data["id"]
        print(f"  Pool ID:         {pool_id}")
        print(f"  Target Quantity: {pool_data['target_quantity']} units")
        print(f"  Target Amount:   {pool_data['target_amount']} KZT")
        print(f"  Pool Status:     {pool_data['status']}")

        # ---- Step 4: Participant #1 joins ----
        print("\n[4] Participant #1 (Aidar) joins the pool...")
        resp = await client.post(f"/pools/{pool_id}/join", json={
            "user_id": "telegram_aidar_42",
            "quantity": 4,
            "amount": 200000,
        })
        join1 = resp.json()
        print(f"  Status: {resp.status_code}")
        print(f"  Current Qty:     {join1['pool']['current_quantity']} / {join1['pool']['target_quantity']}")
        print(f"  Current Amount:  {join1['pool']['current_amount']} / {join1['pool']['target_amount']} KZT")
        print(f"  Qty Progress:    {join1['quantity_progress_percent']}%")
        print(f"  Amount Progress: {join1['amount_progress_percent']}%")
        print(f"  Quorum Reached:  {join1['is_quorum_reached']}")
        print(f"  Pool Status:     {join1['pool']['status']}")

        # ---- Step 5: Participant #2 joins (reaches quorum!) ----
        print("\n[5] Participant #2 (Marat) joins -- should reach quorum!")
        resp = await client.post(f"/pools/{pool_id}/join", json={
            "user_id": "telegram_marat_99",
            "quantity": 6,
            "amount": 300000,
        })
        join2 = resp.json()
        print(f"  Status: {resp.status_code}")
        print(f"  Current Qty:     {join2['pool']['current_quantity']} / {join2['pool']['target_quantity']}")
        print(f"  Current Amount:  {join2['pool']['current_amount']} / {join2['pool']['target_amount']} KZT")
        print(f"  Qty Progress:    {join2['quantity_progress_percent']}%")
        print(f"  Amount Progress: {join2['amount_progress_percent']}%")
        print(f"  Quorum Reached:  {join2['is_quorum_reached']}")
        print(f"  Pool Status:     {join2['pool']['status']}")

        # ---- Step 6: Try joining closed pool (should fail) ----
        print("\n[6] Participant #3 (Dana) tries to join closed pool...")
        resp = await client.post(f"/pools/{pool_id}/join", json={
            "user_id": "telegram_dana_77",
            "quantity": 2,
            "amount": 100000,
        })
        print(f"  Status: {resp.status_code} (expected 400)")
        print(f"  Error:  {resp.json()['detail']}")

        # ---- Step 7: Get Invoice ----
        print("\n[7] Fetching finalized invoice JSON...")
        resp = await client.get(f"/pools/{pool_id}/invoice")
        print(f"  Status: {resp.status_code}")
        invoice = resp.json()

        print("\n" + "=" * 60)
        print("  INVOICE PAYLOAD (for Telegram Bot)")
        print("=" * 60)
        print(json.dumps(invoice, indent=2, ensure_ascii=False))
        print("=" * 60)

        # Summary
        print(f"\n  Invoice #:       {invoice['invoice_number']}")
        print(f"  Items:           {len(invoice['items'])}")
        print(f"  Subtotal:        {invoice['subtotal']} KZT")
        print(f"  Success Fee:     {invoice['success_fee_amount']} KZT ({invoice['success_fee']['applied_percent']}%)")
        print(f"  GRAND TOTAL:     {invoice['grand_total']} KZT")
        print(f"  Payment:         {invoice['payment_details']['payment_purpose']}")

    print("\n[OK] E2E Demo completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
