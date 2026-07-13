from curl_cffi import requests
import urllib.parse

def test():
    query = urllib.parse.quote("iphone")
    url = f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/search/?text={query}"
    r = requests.get(url, impersonate="chrome110", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    print("Status:", r.status_code)
    if r.status_code == 200:
        print("Success! JSON keys:", r.json().keys() if hasattr(r, 'json') and callable(getattr(r, 'json', None)) else r.text[:200])
    else:
        print("Blocked:", r.text[:300])

test()
