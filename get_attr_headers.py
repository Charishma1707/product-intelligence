import csv
with open('Expected_Output_Sheet.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader)
    for i, h in enumerate(headers):
        print(f"[{i}] {h}")
