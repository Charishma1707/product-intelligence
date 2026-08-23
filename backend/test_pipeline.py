import requests, time

AUTH = ('admin', 'unihack')
BASE_URL = 'http://localhost:8000'

payload = {
    'brand': 'Siemens',
    'mpn': '3RT2015-1BB41',
    'description': 'Contactor',
    'force_review': False
}

print('Triggering pipeline...')
r = requests.post(f'{BASE_URL}/enrich/v2', json=payload, auth=AUTH)
if not r.ok:
    print(f"Error: {r.text}")
    exit(1)

data = r.json()
job_id = data.get('job_id')
status = data.get('status')
print(f"Job ID: {job_id}")
print(f"Initial Status: {status}")

while status.startswith('needs_review'):
    print(f"Resuming job {job_id} from {status}...")
    r = requests.post(f'{BASE_URL}/enrich/resume', json={'job_id': job_id, 'corrections': {}, 'reviewer': 'auto'}, auth=AUTH)
    if not r.ok:
        print(f"Resume Error: {r.text}")
        break
    data = r.json()
    status = data.get('status') or data.get('product', {}).get('status')
    print(f"New Status: {status}")

print(f"\nFinal Status: {status}")
print(f"MFR URL: {data.get('product', {}).get('mfr_url')}")
print(f"Spec Sheet: {data.get('product', {}).get('spec_sheet_url')}")

logs = data.get('product', {}).get('logs', [])
print(f"Logs: {len(logs)} entries")
for log in logs:
    if log.get('node') == 'retrieve':
        print(f"--- Retrieve Log ---\n{log.get('message')}\n--------------------")
