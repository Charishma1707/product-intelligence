"""
regenerate_output.py — Re-runs the 2 hackathon products through the fixed pipeline
and writes Master_Unilog_Output.csv.

Run from backend/ directory:
  .venv\Scripts\python regenerate_output.py
"""
import csv
import logging
import os
import sys
from pathlib import Path

# Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("regenerate")

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from pipeline.graph import build_graph, make_initial_state
from exporter import export_to_unilog_format

BASE = Path(__file__).parent

# ── Read hackathon input CSV ──────────────────────────────────────────────────
input_csv = BASE.parent / "Unihack_ Sample Dataset - Input.csv"
if not input_csv.exists():
    logger.error("Input CSV not found: %s", input_csv)
    sys.exit(1)

# We only process the 2 products that appear in the expected output
TARGET_MPNS = {"PDSH4816AF", "WDTS7024RZ"}

rows_to_process = []
with open(input_csv, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        mpn = (row.get("Mfg_Part_Num") or "").strip()
        if mpn in TARGET_MPNS:
            rows_to_process.append(row)
            logger.info("Queued: %s", mpn)

if not rows_to_process:
    logger.error("Could not find PDSH4816AF or WDTS7024RZ in input CSV!")
    sys.exit(1)

logger.info("Processing %d products: %s", len(rows_to_process),
            [r.get("Mfg_Part_Num") for r in rows_to_process])

# ── Run pipeline for each ────────────────────────────────────────────────────
graph = build_graph()
final_states = []
seen_mpns = set()

for row in rows_to_process:
    mpn  = (row.get("Mfg_Part_Num") or "").strip()
    if mpn in seen_mpns:
        logger.warning("Skipping duplicate MPN: %s", mpn)
        continue
    seen_mpns.add(mpn)

    brand = (row.get("Part_Manuf") or row.get("E1_Brand") or "").strip()
    desc  = (row.get("Part_Desc") or "").strip()

    logger.info("=" * 60)
    logger.info("Running pipeline: brand=%s  mpn=%s", brand, mpn)

    initial_state = make_initial_state(
        brand=brand,
        mpn=mpn,
        description=desc,
        job_id=f"regen_{mpn}",
        # ── All input CSV columns ──────────────────────────────────────
        part_number=(row.get("PART_NUMBER") or "").strip(),
        dept=(row.get("Dept") or "").strip(),
        class_=(row.get("Class") or "").strip(),
        fine=(row.get("Fine") or "").strip(),
        sku_my_part_number=(row.get("SKU - MY_PART_NUMBER") or "").strip(),
        input_e1_brand=(row.get("E1_Brand") or "").strip(),
        input_unilog_brand=(row.get("Unilog_Brand") or "").strip(),
        input_dib_brand=(row.get("DIB_Brand") or "").strip(),
        input_part_manuf=(row.get("Part_Manuf") or "").strip(),
        input_part_desc=desc,
    )

    try:
        final_state = graph.invoke(initial_state)
        status = final_state.get("status", "unknown")
        mfr_url = final_state.get("mfr_url") or "(MISSING)"
        logger.info("Done: status=%s  mfr_url=%s", status, mfr_url)
        logger.info("  part_number=%s  dept=%s  class=%s",
                    final_state.get("part_number"),
                    final_state.get("dept"),
                    final_state.get("class_"))
        final_states.append(final_state)
    except Exception as e:
        logger.exception("Pipeline FAILED for %s: %s", mpn, e)

if not final_states:
    logger.error("No products completed — cannot write CSV.")
    sys.exit(1)

# ── Export ────────────────────────────────────────────────────────────────────
csv_str = export_to_unilog_format(final_states)
out_path = Path("Master_Unilog_Output_Final.csv")
out_path.write_text(csv_str, encoding="utf-8")
logger.info(f"Wrote {len(final_states)} rows to {out_path.name}")

# ── Quick sanity check ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("QUICK SANITY CHECK")
print("=" * 60)
rows = list(csv.DictReader(csv_str.splitlines()))
for r in rows:
    mpn_v = r.get("MANUFACTURER_PART_NUMBER") or r.get("Mfg_Part_Num") or "?"
    print(f"\nMPN: {mpn_v}")
    print(f"  MFR URL:       {r.get('MFR URL') or '(BLANK!)'}")
    print(f"  PART_NUMBER:   {r.get('PART_NUMBER') or '(BLANK!)'}")
    print(f"  Dept:          {r.get('Dept') or '(BLANK!)'}")
    print(f"  Class:         {r.get('Class') or '(BLANK!)'}")
    print(f"  BRAND_NAME:    {r.get('BRAND_NAME') or '(BLANK!)'}")
    print(f"  Attr Label 1:  {r.get('ATTRIBUTE_LABEL 1') or '(BLANK!)'}")
    print(f"  Attr Val 1:    {r.get('ATTRIBUTE_VALUE 1') or '(BLANK!)'}")
    print(f"  Product Image: {r.get('Product Image') or '(BLANK!)'}")
    print(f"  Actual Image:  {r.get('Actual Image (Yes/No)') or '(BLANK!)'}")
    print(f"  Warranty:      {r.get('Warranty') or '(BLANK!)'}")
print("\nDone.")
