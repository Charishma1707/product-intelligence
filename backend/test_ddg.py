import requests, urllib.parse, re

try:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text('Fluke 117 datasheet filetype:pdf', max_results=5))
        print('DDGS Found:', [r.get('href') for r in results])
except Exception as e:
    print('DDGS failed:', e)

resp = requests.get(
    f"https://html.duckduckgo.com/html/?q={urllib.parse.quote('Fluke 117 datasheet filetype:pdf')}",
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)
print('HTML DDG Status:', resp.status_code)
if resp.ok:
    print('HTML DDG Output:', resp.text[:200])
