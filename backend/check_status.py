import sqlite3
import json

conn = sqlite3.connect('job_store.db')
c = conn.cursor()
c.execute("SELECT status, updated_at, error FROM jobs WHERE job_id='test-Siemens-3RT2015-1BB41'")
res = c.fetchall()
for row in res:
    print(f"Status: {row[0]}, Updated: {row[1]}, Error: {row[2]}")
