import os, requests
from dotenv import load_dotenv

load_dotenv('.env')
groq_key = os.getenv('GROQ_API_KEY')

url = 'https://api.groq.com/openai/v1/chat/completions'
headers = {'Authorization': f'Bearer {groq_key}', 'Content-Type': 'application/json'}

def test_model(model):
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Output valid JSON with key "a".'}],
        'response_format': {'type': 'json_object'}
    }
    r = requests.post(url, headers=headers, json=payload, timeout=5)
    print(f'{model} JSON: {r.status_code}', r.text[:100] if r.status_code != 200 else '')

test_model('qwen/qwen3.6-27b')
test_model('llama3-8b-8192')
test_model('llama-3.1-8b-instant')
