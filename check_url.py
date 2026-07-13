import urllib.request
try:
    print(urllib.request.urlopen('http://localhost:8000/wb_scanner.html').getcode())
except Exception as e:
    print(e)
