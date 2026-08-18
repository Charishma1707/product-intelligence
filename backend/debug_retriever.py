import os, sys, logging
sys.path.insert(0, '.')
logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv('.env')

from pipeline.retriever import _search_web, _fetch_url, _HARDCODED_PDF_URLS

brand, mpn = 'Siemens', '3RT2015-1BB41'

print("=== STEP 1: URL Selection ===")
if mpn in _HARDCODED_PDF_URLS:
    urls = [_HARDCODED_PDF_URLS[mpn]]
    print("Using hardcoded URL:", urls)
else:
    urls = _search_web(brand, mpn, max_results=3)
    print("Serper URLs:", urls)

print()
print("=== STEP 2: Fetching each URL ===")
for url in urls[:2]:
    print("Fetching:", url)
    try:
        chunks = _fetch_url(url)
        print(f"  -> Got {len(chunks)} chunks")
        for c in chunks[:2]:
            src = c.get("source_type", "?")
            txt = c.get("text", "")[:200]
            print(f"     source_type={src} text_len={len(c.get('text',''))}")
            print(f"     snippet: {txt}")
    except Exception as e:
        import traceback
        print(f"  -> FAILED: {e}")
        traceback.print_exc()
