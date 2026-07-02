import httpx
try:
    resp = httpx.post("http://127.0.0.1:8000/auth/login", data={"username": "karimbai.ali10@mail.ru", "password": "password"})
    print("Status:", resp.status_code)
    print("Body:", resp.text)
except Exception as e:
    print("Error:", e)
