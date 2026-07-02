import asyncio
import redis.asyncio as aioredis

async def flush():
    print("Flushing...")
    client = await aioredis.from_url("redis://localhost:6379/0")
    await client.flushall()
    await client.close()
    print("Flushed!")

if __name__ == "__main__":
    asyncio.run(flush())
