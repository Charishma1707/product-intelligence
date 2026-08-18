"""
reset_pipeline.py — Complete clean-slate reset for the Product Intelligence Pipeline.
Deletes all previous jobs, sqlite DBs, chroma cache, knowledge graphs, logs, downloaded PDFs, outputs, and pycache.
"""

import os
import shutil
import glob
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent

def section(title):
    print(f"\n\033[1;34m{'='*55}\033[0m")
    print(f"\033[1;34m  {title}\033[0m")
    print(f"\033[1;34m{'='*55}\033[0m")

def ok(msg):   print(f"  \033[32m[DELETED]\033[0m  {msg}")
def skip(msg): print(f"  \033[33m[SKIP]\033[0m     {msg}")
def info(msg): print(f"  \033[36m[INFO]\033[0m     {msg}")

section("PIPELINE FULL CLEAN SLATE RESET")

# 1. Job store DBs (backend & root)
for path in [BACKEND / "job_store.db", ROOT / "job_store.db", BACKEND / "jobs.db", ROOT / "jobs.db"]:
    if path.exists():
        try:
            path.unlink()
            ok(f"DB: {path}")
        except Exception as e:
            skip(f"Could not delete {path}: {e}")
    else:
        skip(f"DB not found: {path.name}")

# 2. Chroma vector store caches (backend & root)
for path in [BACKEND / "data" / "chroma", ROOT / "data" / "chroma", ROOT / "data"]:
    if path.exists():
        try:
            shutil.rmtree(path)
            ok(f"Chroma/Data folder: {path}")
        except Exception as e:
            skip(f"Could not remove {path}: {e}")

# 3. Knowledge graph files
for path in [BACKEND / "data" / "knowledge_graph.graphml", ROOT / "data" / "knowledge_graph.graphml", BACKEND / "kg_dump.md"]:
    if path.exists():
        try:
            path.unlink()
            ok(f"Knowledge Graph: {path.name}")
        except Exception as e:
            skip(f"Could not remove {path}: {e}")

# 4. Storage / PDFs (downloaded datasheets)
pdf_dir = BACKEND / "storage" / "pdfs"
if pdf_dir.exists():
    for f in pdf_dir.glob("*"):
        if f.is_file():
            try:
                f.unlink()
                ok(f"Stored PDF: {f.name}")
            except Exception as e:
                skip(f"Could not remove {f.name}: {e}")

# 5. Previous CSV outputs and temporary dumps
for path in [
    BACKEND / "Master_Unilog_Output.csv",
    BACKEND / "test_direct_export.csv",
    BACKEND / "Unilog_Submission.csv",
    BACKEND / "dump.txt",
    BACKEND / "run.txt",
    BACKEND / "test_pipeline_quick.py"
]:
    if path.exists():
        try:
            path.unlink()
            ok(f"File: {path.name}")
        except Exception as e:
            skip(f"Could not delete {path.name}: {e}")

# 6. Logs directory
logs_dir = BACKEND / "logs"
if logs_dir.exists():
    try:
        shutil.rmtree(logs_dir)
        ok("backend/logs/")
    except Exception as e:
        skip(f"Could not remove logs: {e}")

# 7. Outputs directory
outputs_dir = BACKEND / "outputs"
if outputs_dir.exists():
    try:
        shutil.rmtree(outputs_dir)
        ok("backend/outputs/")
    except Exception as e:
        skip(f"Could not remove outputs: {e}")

# 8. Python caches across root and backend
for cache_dir in ROOT.rglob("__pycache__"):
    try:
        shutil.rmtree(cache_dir)
    except Exception:
        pass
ok("All __pycache__ directories in workspace")

# 9. HITL queue files
for hitl_file in BACKEND.glob("hitl_*.json"):
    try:
        hitl_file.unlink()
        ok(f"{hitl_file.name}")
    except Exception:
        pass

# 10. Recreate required clean empty directories
(BACKEND / "data").mkdir(exist_ok=True)
(BACKEND / "logs").mkdir(exist_ok=True)
(BACKEND / "outputs").mkdir(exist_ok=True)
(BACKEND / "storage" / "pdfs").mkdir(parents=True, exist_ok=True)
info("Recreated clean directories: backend/data/, backend/logs/, backend/outputs/, backend/storage/pdfs/")

section("DONE — Complete reset finished. All databases, caches, logs & KG cleared.")
