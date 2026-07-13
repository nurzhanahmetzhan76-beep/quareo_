import asyncio
from retailpool.database import async_session_factory
from retailpool.services.crypto import decrypt_secret
from retailpool.models.ntin import UserSellerSettings
from sqlalchemy import select
from retailpool.services.kaspi_api import KaspiSellerClient

async def test():
    async with async_session_factory() as db:
        user = (await db.execute(select(UserSellerSettings))).scalars().first()
        token = decrypt_secret(user.kaspi_api_key)
        client = KaspiSellerClient(token)
        products = await client.get_products(page=0, size=2)
        import json
        print(json.dumps(products, indent=2))

asyncio.run(test())
