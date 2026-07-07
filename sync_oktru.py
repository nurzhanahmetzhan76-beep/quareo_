import asyncio
import httpx
import sqlite3

# Simple sqlite script to bypass async ORM complexity for a fast script
db_path = "dev.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Make sure table exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS oktru_dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(64) UNIQUE,
    name_ru TEXT,
    name_kz TEXT,
    level INTEGER,
    search_vector TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

API_KEY = "test_api_key_12345"
cursor.execute("SELECT nkt_api_key FROM user_seller_settings WHERE nkt_api_key IS NOT NULL AND nkt_api_key != 'test_api_key_12345' LIMIT 1")
row = cursor.fetchone()
if row:
    API_KEY = row[0]
else:
    print("NO REAL API KEY FOUND IN DB! Using fallback... (will likely fail)")

base_url = "https://nationalcatalog.kz/gwp/portal/api/v1/dictionaries/OKTRU/items"
headers = {"X-API-KEY": API_KEY, "Accept": "application/json"}

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        page = 1
        total_saved = 0
        while True:
            print(f"Fetching page {page}...")
            url = f"{base_url}?page={page}&size=1000"
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 422 and "size" in resp.text:
                     # fallback to 100
                     url = f"{base_url}?page={page}&size=100"
                     resp = await client.get(url, headers=headers)
                
                if resp.status_code == 429:
                    print("Hit rate limit (429). Sleeping for 60 seconds...")
                    await asyncio.sleep(60)
                    continue
                
                if resp.status_code != 200:
                    print(f"Error {resp.status_code}: {resp.text}")
                    break
                    
                data = resp.json()
                items = data.get("content", [])
                if not items:
                    print("No more items.")
                    break
                    
                for item in items:
                    code = item.get("code")
                    if not code: continue
                    level = str(code).count("-") + 1
                    name_ru = item.get("nameRu", "")
                    # only save level 4 codes to save space
                    if level == 4:
                        search_vector = name_ru.lower()
                        try:
                            cursor.execute(
                                "INSERT OR IGNORE INTO oktru_dictionary (code, name_ru, level, search_vector) VALUES (?, ?, ?, ?)",
                                (code, name_ru, level, search_vector)
                            )
                            total_saved += 1
                        except sqlite3.Error as e:
                            pass
                conn.commit()
                print(f"Page {page} done. Total saved level 4 codes: {total_saved}")
                page += 1
                
                # Sleep a bit to avoid rate limiting
                await asyncio.sleep(0.6)
                
            except Exception as e:
                print(f"Exception: {e}")
                break
        print(f"Sync complete! Saved {total_saved} OKTRU codes.")

if __name__ == "__main__":
    asyncio.run(main())
