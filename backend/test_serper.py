import os, requests, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path('e:/unihack/product-intelligence/backend/.env'), override=True)
api_key = os.getenv("SERPER_API_KEY")

print(f"Loaded SERPER_API_KEY: {api_key[:8]}...{api_key[-4:] if api_key else 'NONE'}")

if not api_key:
    print("SERPER_API_KEY is not set in .env!")
else:
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": "Schneider LC1D09M7 datasheet", "num": 3})
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    
    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        print(f"Status Code: {resp.status_code}")
        print(f"Response Body: {resp.text}")
    except Exception as e:
        print(f"Request Error: {e}")
