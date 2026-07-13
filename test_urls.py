import urllib.request
import urllib.error

urls = [
    'http://localhost:8000/wb_scanner.html',
    'http://localhost:8000/wb_scanner',
    'http://localhost:8000/scanner/wb/search?query=test&max_items=10'
]

for url in urls:
    try:
        resp = urllib.request.urlopen(url)
        print(f"OK: {url} -> {resp.getcode()}")
    except urllib.error.HTTPError as e:
        print(f"ERR: {url} -> {e.code}")
    except Exception as e:
        print(f"ERR: {url} -> {e}")
