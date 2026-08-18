import json
import base64
import requests
import os
from dotenv import load_dotenv
load_dotenv("c:\\charishma\\apicurio registry\\unihack\\product-intelligence\\backend\\.env")
import fitz

doc = fitz.open("C:\\charishma\\apicurio registry\\unihack\\product-intelligence\\backend\\sample_data\\reference_docs\\SKF_6205-2RS1.pdf")
page = doc[0]
pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
img_bytes = pix.tobytes("png")
image_b64 = base64.b64encode(img_bytes).decode("utf-8")

gemini_key = os.getenv("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gemini_key}"

prompt = "Extract: inner_diameter, outer_diameter, width. Format: {\"field\": {\"value\": \"...\", \"table_location\": \"...\"}}"
from pipeline.extractor import _SYSTEM_PROMPT

full_prompt = _SYSTEM_PROMPT + "\n\n" + prompt
payload = {
    "contents": [{
        "parts": [
            {"text": full_prompt},
            {"inline_data": {"mime_type": "image/png", "data": image_b64}}
        ]
    }],
    "generationConfig": {
        "responseMimeType": "application/json",
        "temperature": 0.1
    }
}
res = requests.post(url, json=payload, timeout=60)
print(res.json())
