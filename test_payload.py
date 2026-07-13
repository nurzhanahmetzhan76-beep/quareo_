import asyncio
import os
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./dev.db'

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
        print('Token starts with:', token[:5])
        try:
            res = await client.update_price('117872614', 135)
            print('Success:', res)
        except Exception as e:
            if hasattr(e, 'response'):
                print(f"Error {e.response.status_code}: {e.response.text}")
            else:
                print('Error:', type(e), str(e))

asyncio.run(test())
