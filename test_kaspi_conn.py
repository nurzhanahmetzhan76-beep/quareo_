import asyncio
import httpx

async def test():
    token = 'test_token'
    headers = {
        'X-Auth-Token': token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get('https://kaspi.kz/shop/api/v2/products', headers=headers)
            print('STATUS:', resp.status_code)
            print('TEXT:', resp.text[:500])
    except Exception as e:
        print('ERROR:', type(e), str(e))

asyncio.run(test())
