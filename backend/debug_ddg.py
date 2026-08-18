import requests
from bs4 import BeautifulSoup
import urllib.parse

def _search_web_html(query: str, max_results: int = 2) -> list:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    data = {"q": query}
    try:
        res = requests.post("https://html.duckduckgo.com/html/", data=data, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        urls = []
        for a in soup.find_all("a", class_="result__url"):
            href = a.get("href")
            if href:
                if "uddg=" in href:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    if "uddg" in parsed:
                        urls.append(parsed["uddg"][0])
                else:
                    urls.append(href)
        return urls[:max_results]
    except Exception as e:
        print(f"Error: {e}")
        return []

print(_search_web_html("Siemens 3RT2015-1BB41 datasheet", 2))
