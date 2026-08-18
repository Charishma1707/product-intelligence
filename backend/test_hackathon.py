import requests
import json

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

print("Running Unilog Hackathon Pipeline Test...")
print(f"Input: {data['brand']} | {data['mpn']} | {data['description']}\n")

resp = requests.post(url, headers=headers, json=data, timeout=120)
result = resp.json()

if "product" in result:
    p = result["product"]
    print("===== HACKATHON DELIVERY FORMAT =====")
    print(f"Classpath:    {p.get('classpath')}")
    print(f"Invoice Desc: {p.get('invoice_desc')}")
    print(f"Mobile Desc:  {p.get('mobile_desc')}")
    print(f"Short Desc:   {p.get('short_desc')}")
    print(f"Long Desc:    {p.get('long_desc')}")
    print("\n===== EXTRACTED SPECIFICATIONS =====")
    specs = p.get('specifications', {})
    for key, spec in specs.items():
        if isinstance(spec, dict):
            val = spec.get('value')
            print(f" - {key}: {val}")
else:
    print("Error:", result)
