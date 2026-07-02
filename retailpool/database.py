"""
RetailPool AI v2.0 — Async Database Layer.

Provides async SQLAlchemy engine, session factory,
and a FastAPI dependency for DB session injection.

Primary DB: PostgreSQL (via asyncpg)
Test DB: SQLite (via aiosqlite) — configured in tests/conftest.py
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from retailpool.config import settings

# ---------------------------------------------------------------------------
# Engine & session factory (created once at import time)
# ---------------------------------------------------------------------------
_engine_kwargs: dict = {"echo": False}

# SQLite needs special handling for async
if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
else:
    # PostgreSQL connection pool settings
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session and ensure it is closed after use."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
