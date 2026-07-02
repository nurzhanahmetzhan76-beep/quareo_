"""
Tests for Co-Buying Pool endpoints and Invoice generation.
Uses in-memory SQLite for fast testing without PostgreSQL.
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from retailpool.main import app
from retailpool.database import get_db
from retailpool.models.base import Base
from retailpool.models.product import Product

# ── In-memory SQLite engine for tests ────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session_factory = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def seed_product() -> uuid.UUID:
    """Insert a test product and return its ID."""
    async with test_session_factory() as session:
        product = Product(
            kaspi_id="test-humidifier-001",
            title="Увлажнитель воздуха Xiaomi Mi Smart",
            category_slug="air-humidifiers",
            url="https://kaspi.kz/shop/p/test-001/",
            price_min=25000,
            price_max=30000,
            photo_count=5,
            rating=4.5,
            review_count=120,
        )
        session.add(product)
        await session.commit()
        return product.id


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════
# Pool CRUD Tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_pool(client: AsyncClient, seed_product: uuid.UUID):
    """POST /pools/create should return 201 with pool data."""
    resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 50,
        "target_amount": 1500000,
        "expires_in_hours": 48,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert data["target_quantity"] == 50
    assert data["current_quantity"] == 0


@pytest.mark.asyncio
async def test_join_pool(client: AsyncClient, seed_product: uuid.UUID):
    """POST /pools/{id}/join should add participant and update totals."""
    # Create pool
    create_resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 10,
        "target_amount": 300000,
        "expires_in_hours": 24,
    })
    pool_id = create_resp.json()["id"]

    # Join
    join_resp = await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "telegram_user_42",
        "quantity": 3,
        "amount": 90000,
    })
    assert join_resp.status_code == 200
    data = join_resp.json()
    assert len(data["participants"]) == 1
    assert data["pool"]["current_quantity"] == 3
    assert data["is_quorum_reached"] is False


@pytest.mark.asyncio
async def test_quorum_reached(client: AsyncClient, seed_product: uuid.UUID):
    """Pool should auto-close when quorum is reached."""
    create_resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 5,
        "target_amount": 150000,
        "expires_in_hours": 24,
    })
    pool_id = create_resp.json()["id"]

    # Join with enough to reach quorum
    resp = await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "user_big_buyer",
        "quantity": 5,
        "amount": 150000,
    })
    data = resp.json()
    assert data["is_quorum_reached"] is True
    assert data["pool"]["status"] == "closed"


@pytest.mark.asyncio
async def test_get_pool_status(client: AsyncClient, seed_product: uuid.UUID):
    """GET /pools/{id}/status should return progress percentages."""
    create_resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 100,
        "target_amount": 3000000,
        "expires_in_hours": 72,
    })
    pool_id = create_resp.json()["id"]

    # Add a participant
    await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "user_1",
        "quantity": 25,
        "amount": 750000,
    })

    status_resp = await client.get(f"/pools/{pool_id}/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["quantity_progress_percent"] == 25.0
    assert data["amount_progress_percent"] == 25.0
    assert data["is_quorum_reached"] is False


@pytest.mark.asyncio
async def test_duplicate_join_rejected(client: AsyncClient, seed_product: uuid.UUID):
    """Same user should not be able to join a pool twice."""
    create_resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 10,
        "target_amount": 300000,
        "expires_in_hours": 24,
    })
    pool_id = create_resp.json()["id"]

    await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "same_user",
        "quantity": 2,
        "amount": 60000,
    })

    dup_resp = await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "same_user",
        "quantity": 1,
        "amount": 30000,
    })
    assert dup_resp.status_code == 400


@pytest.mark.asyncio
async def test_join_closed_pool_rejected(client: AsyncClient, seed_product: uuid.UUID):
    """Joining a closed pool (quorum reached) should be rejected."""
    create_resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 2,
        "target_amount": 60000,
        "expires_in_hours": 24,
    })
    pool_id = create_resp.json()["id"]

    # Close the pool by reaching quorum
    await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "closer",
        "quantity": 2,
        "amount": 60000,
    })

    # Try to join after closed
    resp = await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "latecomer",
        "quantity": 1,
        "amount": 30000,
    })
    assert resp.status_code == 400
    assert "not open" in resp.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# Invoice Endpoint Tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invoice_for_closed_pool(client: AsyncClient, seed_product: uuid.UUID):
    """GET /pools/{id}/invoice should return full JSON payload for closed pool."""
    create_resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 5,
        "target_amount": 125000,
        "expires_in_hours": 48,
    })
    pool_id = create_resp.json()["id"]

    # Reach quorum
    await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "buyer_a",
        "quantity": 3,
        "amount": 75000,
    })
    await client.post(f"/pools/{pool_id}/join", json={
        "user_id": "buyer_b",
        "quantity": 2,
        "amount": 50000,
    })

    # Fetch invoice
    invoice_resp = await client.get(f"/pools/{pool_id}/invoice")
    assert invoice_resp.status_code == 200
    data = invoice_resp.json()

    # Verify structure
    assert data["invoice_number"].startswith("INV-")
    assert data["pool_id"] == pool_id
    assert len(data["items"]) == 2
    assert len(data["participants"]) == 2
    assert data["subtotal"] > 0
    assert data["success_fee_amount"] > 0
    assert data["grand_total"] == data["subtotal"] + data["success_fee_amount"]
    assert data["success_fee"]["applied_percent"] >= 3.0
    assert data["payment_details"]["recipient_name"] == "RetailPool AI"


@pytest.mark.asyncio
async def test_invoice_for_open_pool_rejected(client: AsyncClient, seed_product: uuid.UUID):
    """Invoice generation should fail for pools that are still open."""
    create_resp = await client.post("/pools/create", json={
        "product_id": str(seed_product),
        "target_quantity": 100,
        "target_amount": 3000000,
        "expires_in_hours": 72,
    })
    pool_id = create_resp.json()["id"]

    invoice_resp = await client.get(f"/pools/{pool_id}/invoice")
    assert invoice_resp.status_code == 400
    assert "not closed" in invoice_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invoice_for_nonexistent_pool(client: AsyncClient):
    """Invoice for a non-existent pool should return 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/pools/{fake_id}/invoice")
    assert resp.status_code == 404
