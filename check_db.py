import asyncio
from retailpool.database import async_session
from sqlalchemy import text

async def main():
    async with async_session() as session:
        # Check products
        res = await session.execute(text("SELECT sku, title FROM repricer_items LIMIT 5"))
        items = res.fetchall()
        print("Repricer Items:")
        for i in items:
            print(i)
            
        res2 = await session.execute(text("SELECT email, kaspi_token FROM users WHERE email='karimbai.ali10@mail.ru'"))
        user = res2.fetchone()
        print("User token:", user)
        
asyncio.run(main())
