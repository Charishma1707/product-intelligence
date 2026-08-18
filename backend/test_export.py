from exporter import export_to_unilog_format
from pipeline.job_store import list_jobs
from main import _state_to_record

states = list_jobs(status="complete", limit=5)
records = [_state_to_record(s) for s in states]

if not records:
    print("No complete records found to export.")
else:
    csv_str = export_to_unilog_format(records)
    with open("test_direct_export.csv", "w", encoding="utf-8") as f:
        f.write(csv_str)
    print("Exported successfully.")
