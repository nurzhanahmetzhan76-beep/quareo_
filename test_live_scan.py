"""
Fetch real blue ocean scan for 'робот пылесос' via the actual API endpoint
"""
import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # We need to call the actual FastAPI endpoint
        resp = await client.post("http://localhost:8000/api/blue_ocean/scan", json={"query": "робот пылесос"})
        
        with open("test_api_scan_results.json", "w", encoding="utf-8") as f:
            f.write(resp.text)
            
        print("Status code:", resp.status_code)

asyncio.run(main())
