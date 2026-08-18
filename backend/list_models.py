import requests
import os
from dotenv import load_dotenv
load_dotenv("c:\\charishma\\apicurio registry\\unihack\\product-intelligence\\backend\\.env")
gemini_key = os.getenv("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
res = requests.get(url)
models = res.json().get("models", [])
for m in models:
    if "flash" in m["name"]:
        print(m["name"])
