import requests
import json

data = {
  "brand": "Fastenal",
  "mpn": "DWE402",
  "description": "",
  "part_manuf": "Fastenal",
  "e1_brand": "",
  "unilog_brand": "",
  "dib_brand": "",
  "provided_schema": None,
  "strict_schema": False
}
auth = ('admin', 'unihack')

try:
    print("Sending POST request to /enrich/v2...")
    res = requests.post("http://127.0.0.1:8000/enrich/v2", json=data, auth=auth)
    print(f"Status Code: {res.status_code}")
    
    response_json = res.json()
    
    # We specifically want to check if true brand was resolved to DeWalt
    # and if fields were extracted
    product = response_json.get("product", {})
    brand_resolved = product.get("brand_name")
    manufacturer = product.get("manufacturer_name")
    specs = product.get("specifications", {})
    
    print(f"\nResolved Brand: {brand_resolved}")
    print(f"Resolved Manufacturer: {manufacturer}")
    print(f"Extracted Fields ({len(specs)}):")
    for k, v in specs.items():
        val = v.get("value") if isinstance(v, dict) else getattr(v, "value", None)
        print(f"  - {k}: {val}")
        
    print("\nFull Response:")
    print(json.dumps(response_json, indent=2)[:1000] + "\n... (truncated)")

except Exception as e:
    print(f"Error: {e}")
