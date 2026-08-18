import requests

url = "http://127.0.0.1:8000/enrich/v2"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Basic YWRtaW46dW5paGFjaw=="
}
data = {
    "brand": "SKF",
    "mpn": "6205-2RS1",
    "description": "Deep groove ball bearing 25x52x15mm sealed"
}
resp = requests.post(url, headers=headers, json=data, timeout=120)
print(resp.json())
