import requests

url = "https://download.schneider-electric.com/files?p_Doc_Ref=LC1D09BD_Datasheet"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers)
print("Status:", resp.status_code)
print("Content-Type:", resp.headers.get("Content-Type"))
print("Length:", len(resp.content))
