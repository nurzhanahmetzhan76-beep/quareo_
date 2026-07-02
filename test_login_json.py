import httpx
try:
    resp = httpx.post("http://127.0.0.1:8000/api/auth/login", json={"email": "karimbai.ali10@mail.ru", "password": "password"})
    print("Status API:", resp.status_code)
    print("Body API:", resp.text)
    
    resp2 = httpx.post("http://127.0.0.1:8000/auth/login", json={"email": "karimbai.ali10@mail.ru", "password": "password"})
    print("Status:", resp2.status_code)
    print("Body:", resp2.text)
except Exception as e:
    print("Error:", e)
