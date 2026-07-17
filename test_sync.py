import asyncio
import httpx

async def test():
    # Attempt to login and call the endpoint
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # First register/login to get a token
        res = await client.post("/api/auth/register", json={
            "email": "testsync2@example.com",
            "password": "password123",
            "full_name": "Test Sync 2"
        })
        token = res.json().get("access_token")
        if not token:
            print("Register failed:", res.json())
            return

        # Setup kaspi_xml_url
        await client.post("/api/ntin/settings", json={
            "kaspi_xml_url": "https://kaspi.kz"
        }, headers={"Authorization": f"Bearer {token}"})

        # Call sync
        res = await client.post("/api/repricing/sync", headers={"Authorization": f"Bearer {token}"})
        print(res.status_code)
        print(res.text[:1000])

asyncio.run(test())
