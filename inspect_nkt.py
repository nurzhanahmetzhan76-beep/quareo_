import asyncio
import os
import json
from sqlalchemy import select
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct
from retailpool.services.ntin_service import NtinService

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./dev.db"

async def check_nkt_draft():
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(NtinProduct.status == "revision").limit(1)
        product = (await session.execute(stmt)).scalars().first()
        if not product:
            print("No product in revision")
            return
            
        print(f"Checking product {product.id} (NKT ID: {product.nkt_request_id})")
        
        service = NtinService(session)
        api_key = await service._get_nkt_api_key(product.user_id)
        
        import httpx
        base_url = "https://nationalcatalog.kz/gwp"
        headers = service._build_nkt_headers(api_key)
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base_url}/portal/api/v1/products/requests/{product.nkt_request_id}/details",
                headers=headers,
            )
            with open('nkt_response.json', 'w', encoding='utf-8') as f:
                json.dump(resp.json(), f, indent=2, ensure_ascii=False)
            print("Done, saved to nkt_response.json")

asyncio.run(check_nkt_draft())
