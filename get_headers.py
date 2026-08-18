import csv
with open('Expected_Output_Sheet.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader)
    print(f"Total Headers: {len(headers)}")
    print(headers[:30])
    print(headers[-30:])
