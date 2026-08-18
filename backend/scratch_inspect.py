import csv, sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\charishma\apicurio registry\unihack\product-intelligence\Unihack_ Expected Output - Delivery Format.csv'
with open(path, encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows)}")
print(f"Columns ({len(rows[0].keys())}):")
for i, k in enumerate(rows[0].keys()):
    print(f"  [{i:03d}] {k!r}")

print("\nFirst row sample:")
for k, v in list(rows[0].items())[:30]:
    if v and v.strip():
        print(f"  {k}: {v!r}")
