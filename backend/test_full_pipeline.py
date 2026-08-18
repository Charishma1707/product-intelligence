"""
test_full_pipeline.py — End-to-end pipeline test with full HITL review.

Usage:
    .venv\\Scripts\\python test_full_pipeline.py

Color coding:
  GREEN  = high confidence (auto-approved)
  YELLOW = low confidence (flagged for human review)
  RED    = not found
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure backend root is on sys.path
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Set up clean logging (suppress noisy library logs)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("pipeline").setLevel(logging.INFO)

# ANSI colors
_R  = "\033[0m"
_B  = "\033[1m"
_G  = "\033[32m"
_Y  = "\033[33m"
_RE = "\033[31m"
_CY = "\033[36m"
_GR = "\033[90m"
_BL = "\033[34m"

def banner(title):
    print(f"\n{_B}{_BL}{'='*60}{_R}")
    print(f"{_B}{_BL}  {title}{_R}")
    print(f"{_B}{_BL}{'='*60}{_R}")

def phase(num, title):
    print(f"\n{_B}{_CY}  Phase {num}: {title}{_R}")
    print(f"  {_GR}{'-'*56}{_R}")

def ok(msg):    print(f"  {_G}{msg}{_R}")
def warn(msg):  print(f"  {_Y}{msg}{_R}")
def err(msg):   print(f"  {_RE}{msg}{_R}")
def info(msg):  print(f"  {_GR}{msg}{_R}")
def kv(k, v):   print(f"  {_CY}{k:<28}{_R} {v}")


def run_test(brand: str, mpn: str, description: str, interactive_hitl: bool = True):
    """Run the full pipeline for a single product and display results."""
    from pipeline.graph import build_graph, make_initial_state
    from pipeline.log_store import init_log_db, write_log, print_job_logs
    from pipeline.hitl import print_extraction_table, run_hitl_review, apply_overrides, save_hitl_result
    from pipeline.job_store import init_db, save_job, list_jobs

    init_log_db()
    init_db()

    job_id = f"job-{brand.lower()}-{mpn.lower()}-{datetime.now().strftime('%H%M%S')}"

    banner(f"PRODUCT ENRICHMENT PIPELINE")
    kv("Brand",   brand)
    kv("MPN",     mpn)
    kv("Desc",    description)
    kv("Job ID",  job_id)

    # ── Check LLM backend ──
    phase(0, "LLM Backend Check")
    import requests as _req
    try:
        _req.get("http://localhost:11434/api/tags", timeout=2)
        ok("Ollama is running — using LOCAL model (free, unlimited, no rate limits)")
    except Exception:
        warn("Ollama not running — using Gemini API (rate limited)")
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            ok(f"Gemini key found ({gemini_key[:12]}...)")
        else:
            err("No LLM backend available! Install Ollama or add GEMINI_API_KEY to .env")
            return

    write_log(job_id, "system", f"Pipeline started for {brand} {mpn}", "INFO",
              {"brand": brand, "mpn": mpn, "description": description})

    # ── Run the pipeline ──
    phase(1, "Running LangGraph Pipeline")
    print(f"  {_GR}Categorizing product, searching web, downloading datasheets,")
    print(f"  extracting specs... (this may take 30-60 seconds){_R}\n")

    graph = build_graph()
    state = make_initial_state(brand=brand, mpn=mpn, description=description, job_id=job_id)

    try:
        final = graph.invoke(state)
    except Exception as e:
        err(f"Pipeline crashed: {e}")
        write_log(job_id, "system", f"Pipeline crashed: {e}", "ERROR")
        return

    # ── Phase 1: Classification ──
    phase(1, "Classification")
    status = final.get("status", "unknown")
    color = _G if status == "complete" else _Y if status == "needs_review" else _RE
    kv("Status",     f"{color}{status}{_R}")
    kv("Category",   final.get("category") or "(not classified)")
    kv("Subcategory",final.get("subcategory") or "(none)")
    kv("Classpath",  final.get("classpath") or "(none)")
    kv("Expected fields", str(len(final.get("expected_fields", []))))

    # ── Phase 2: Data Retrieval ──
    phase(2, "Data Retrieval")
    docs = final.get("raw_documents", [])
    src_urls = final.get("source_urls", [])
    kv("Documents retrieved", str(len(docs)))
    kv("Source URLs", str(len(src_urls)))
    for url in src_urls[:5]:
        info(f"  {url}")
    if final.get("spec_sheet_url"):
        ok(f"Spec sheet: {final['spec_sheet_url']}")
    if final.get("product_image_url"):
        ok(f"Product image: {final['product_image_url']}")

    # ── Phase 3: Extraction Results (colored table) ──
    phase(3, "Extraction & Validation Results")
    specs = final.get("specifications", {})
    if not specs:
        err("No fields were extracted. Check LLM backend and data sources.")
    else:
        from pipeline.hitl import print_extraction_table
        flagged = print_extraction_table(job_id, brand, mpn, specs)

    # ── Phase 4: Knowledge Graph ──
    phase(4, "Knowledge Graph")
    kg_file = Path("data/knowledge_graph.graphml")
    if kg_file.exists():
        import networkx as nx
        G = nx.read_graphml(kg_file)
        kv("Nodes", str(G.number_of_nodes()))
        kv("Edges", str(G.number_of_edges()))
        prod_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "Product"]
        kv("Products indexed", str(len(prod_nodes)))
        ok("Knowledge graph updated with this product's validated specs")
    else:
        info("Knowledge graph not yet created")

    # ── Phase 5: Commerce Copy ──
    phase(5, "Generated Commerce Copy")
    kv("SEO Title",    final.get("short_desc") or "(not generated)")
    kv("Invoice Desc", final.get("invoice_desc") or "(not generated)")
    kv("Mobile Desc",  final.get("mobile_desc") or "(not generated)")
    long_desc = final.get("long_desc") or ""
    if long_desc:
        ok("Long description generated:")
        for line in long_desc[:300].split(". ")[:3]:
            info(f"  {line.strip()}.")
    bullets = final.get("item_features", [])
    kv("Feature bullets", str(len(bullets)))
    for b in bullets[:5]:
        info(f"  {b}")

    # ── Phase 6: HITL Review ──
    phase(6, "Human-in-the-Loop (HITL) Review")
    overall_conf = final.get("overall_confidence", 0.0)
    kv("Overall confidence", f"{overall_conf*100:.1f}%")

    overrides = {}
    if specs and interactive_hitl:
        if overall_conf < 0.80:
            warn(f"Confidence below 80% — HITL review required")
            overrides = run_hitl_review(job_id, brand, mpn, specs)
            if overrides:
                specs = apply_overrides(specs, overrides)
                ok(f"Applied {len(overrides)} human override(s)")
        else:
            ok("Confidence is high — HITL review skipped (auto-approved)")

    # ── Save output ──
    phase(7, "Saving Output")

    # Save HITL result as JSON
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    # Get job number
    all_jobs = list_jobs(limit=1000)
    job_num = len(all_jobs) + 1

    hitl_file = save_hitl_result(job_id, specs, overrides, outputs_dir)
    ok(f"Job JSON saved: {hitl_file}")

    # Save to DB
    final["specifications"] = specs
    save_job(final)

    # Write to CSV
    try:
        from exporter import export_to_unilog_format
        from pipeline.job_store import load_job

        job_records = []
        for j in list_jobs(status="complete", limit=1000):
            loaded = load_job(j["job_id"])
            if loaded:
                job_records.append(loaded)

        if job_records:
            csv_str = export_to_unilog_format(job_records)
            csv_path = Path("Master_Unilog_Output.csv")
            csv_path.write_text(csv_str, encoding="utf-8")
            ok(f"Master CSV updated: {csv_path} ({len(job_records)} job(s))")
    except Exception as e:
        warn(f"CSV export failed: {e}")

    write_log(job_id, "system", f"Pipeline complete. Confidence: {overall_conf:.2%}", "SUCCESS",
              {"job_number": job_num, "fields_extracted": len([s for s in specs.values()
               if (s.get("value") if isinstance(s, dict) else getattr(s, "value", None)) is not None])})

    # ── Audit trail ──
    phase(8, "Audit Trail")
    print_job_logs(job_id)

    # ── Summary ──
    banner("PIPELINE COMPLETE")
    kv("Job ID",      job_id)
    kv("Job Number",  f"#{job_num:04d}")
    kv("Status",      f"{_G}complete{_R}" if status != "failed" else f"{_RE}failed{_R}")
    kv("Output JSON", str(hitl_file))
    kv("Master CSV",  "Master_Unilog_Output.csv")
    print()

    return final


if __name__ == "__main__":
    # Check for interactive mode flag
    interactive = "--no-hitl" not in sys.argv

    # Run the test product
    run_test(
        brand="Siemens",
        mpn="3RT2015-1BB41",
        description="Contactor 3-pole 7A 24VDC coil",
        interactive_hitl=interactive,
    )
