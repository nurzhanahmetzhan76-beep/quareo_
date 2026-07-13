"""
Pre-migration DB bootstrap.

Alembic migrations for this project assume the base ORM tables
(users, ntin_products, products, subscriptions, ...) already exist —
they were historically created by ``Base.metadata.create_all()`` in the
app's lifespan, which only runs *after* `alembic upgrade head` in the
container's start command. On a brand-new database that ordering means
migrations fail immediately (ALTER/CREATE against tables that don't
exist yet).

Run this script before `alembic upgrade head` so all current model
tables exist first; the migrations then see everything already present
and simply no-op their guarded steps.
"""

from __future__ import annotations

import asyncio

from retailpool.database import engine
from retailpool.models.base import Base

# Import retailpool.main so every router (and therefore every model
# module it depends on) is loaded and registered on Base.metadata.
import retailpool.main  # noqa: F401


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("[OK] Base tables ensured.")


if __name__ == "__main__":
    asyncio.run(main())
