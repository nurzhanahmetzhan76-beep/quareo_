import httpx

def test():
    try:
        r=httpx.get('https://api.zenrows.com/v1/', params={'url': 'https://www.ozon.ru/search/?text=iphone', 'apikey': 'c6bc7254d563bc03cad885311962fbcdedbf8606', 'js_render': 'true', 'antibot': 'true'}, timeout=60)
        print("Status:", r.status_code)
        print("Length:", len(r.text))
        if "abt-challenge" in r.text or "Shield" in r.text:
            print("BLOCKED")
        else:
            print("SUCCESS")
    except Exception as e:
        print("Exception:", e)

test()
