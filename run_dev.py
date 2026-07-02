"""
RetailPool AI — Local Development Runner.

Runs the FastAPI app with SQLite for quick local testing
without Docker/PostgreSQL. Creates tables automatically.

Usage:
    python run_dev.py
    → Open http://localhost:8000/docs
"""

import asyncio
import os
import sys

# Force SQLite for local dev (no PostgreSQL needed)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./dev.db"

# Now import after env is set
from retailpool.database import engine
from retailpool.models.base import Base

# Import all models so Base.metadata knows about them
import retailpool.models.product  # noqa: F401
import retailpool.models.pool     # noqa: F401
import retailpool.models.user     # noqa: F401
import retailpool.models.ntin     # noqa: F401


async def init_db():
    """Create all tables in the dev SQLite database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Database tables created in dev.db")


if __name__ == "__main__":
    # Create tables
    asyncio.run(init_db())

    # Launch uvicorn
    import uvicorn
    print("\n>>> Starting RetailPool AI v2.0 (DEV MODE)")
    print(">>> Frontend:   http://localhost:8000/")
    print(">>> Login:      http://localhost:8000/login")
    print(">>> Register:   http://localhost:8000/register")
    print(">>> Swagger UI: http://localhost:8000/docs")
    print(">>> ReDoc:      http://localhost:8000/redoc")
    print("-" * 50)
    uvicorn.run(
        "retailpool.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
