import asyncio
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct
from sqlalchemy import select

async def main():
    async with async_session_factory() as session:
        res = await session.execute(select(NtinProduct))
        products = res.scalars().all()
        for p in products:
            if p.title_ru is None:
                print(f"Product {p.id} has None title_ru")

if __name__ == "__main__":
    asyncio.run(main())
