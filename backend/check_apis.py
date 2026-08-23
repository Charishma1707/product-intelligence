import requests, os, json
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(r'e:\unihack\product-intelligence\backend\.env'))

serper_key = os.getenv('SERPER_API_KEY', '')
groq_key = os.getenv('GROQ_API_KEY', '')

print(f"Serper key present: {bool(serper_key)} ({serper_key[:10]}...)")

# Test Serper
try:
    r = requests.post(
        'https://google.serper.dev/search',
        headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
        data=json.dumps({'q': 'Whirlpool WDTS7024RZ specifications', 'num': 3}),
        timeout=10
    )
    print(f"Serper HTTP status: {r.status_code}")
    data = r.json()
    organic = data.get('organic', [])
    print(f"Serper organic results: {len(organic)}")
    for item in organic[:3]:
        print(f"  -> {item.get('link')}")
except Exception as e:
    print(f"Serper ERROR: {e}")

print()

# Test Groq
print(f"Groq key present: {bool(groq_key)} ({groq_key[:15]}...)")
try:
    r = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={'Authorization': f'Bearer {groq_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'llama-3.1-8b-instant',
            'messages': [{'role': 'user', 'content': 'say ok'}],
            'max_tokens': 5
        },
        timeout=15
    )
    print(f"Groq HTTP status: {r.status_code}")
    if r.status_code == 200:
        print(f"Groq response: {r.json()['choices'][0]['message']['content']}")
    else:
        print(f"Groq error: {r.text[:300]}")
except Exception as e:
    print(f"Groq ERROR: {e}")

# Test DuckDuckGo fallback
print()
print("Testing DuckDuckGo fallback...")
try:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text('Whirlpool WDTS7024RZ specifications site:whirlpool.com', max_results=3))
    print(f"DDG results: {len(results)}")
    for r in results:
        print(f"  -> {r.get('href')}")
except Exception as e:
    print(f"DDG ERROR: {e}")
