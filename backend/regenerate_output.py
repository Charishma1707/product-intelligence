"""
regenerate_output.py — Re-runs the hackathon products through the fixed pipeline
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

# ── Group by (Manufacturer, Series) ──────────────────────────────────────────
# NOTE: Series here is a PRE-RESOLUTION GUESS for grouping only.
# The pipeline will resolve the true series. Siblings share docs but not specs.
from pipeline.extractor import _guess_series_from_description
from pipeline.taxonomy import is_series_shared

groups = {}
seen_mpns = set()
for row in rows_to_process:
    mpn = (row.get("Mfg_Part_Num") or "").strip()
    if mpn in seen_mpns:
        continue
    seen_mpns.add(mpn)
    
    brand = (row.get("Part_Manuf") or row.get("E1_Brand") or "").strip()
    desc = (row.get("Part_Desc") or "").strip()
    
    # Try to guess series
    series = _guess_series_from_description(brand, mpn, desc) or mpn[:4]
    
    group_key = (brand, series)
    if group_key not in groups:
        groups[group_key] = []
    groups[group_key].append(row)

# ── Run pipeline for each group ──────────────────────────────────────────────
graph = build_graph()
final_states = []

for group_key, rows in groups.items():
    brand, series = group_key
    logger.info("=" * 60)
    logger.info("Processing Group: Brand=%s, Series=%s (%d items)", brand, series, len(rows))
    
    rep_row = rows[0]
    rep_mpn = (rep_row.get("Mfg_Part_Num") or "").strip()
    rep_desc = (rep_row.get("Part_Desc") or "").strip()
    
    logger.info("  -> Representative Item: %s", rep_mpn)
    
    # Process representative item FULLY
    rep_initial_state = make_initial_state(
        brand=brand,
        mpn=rep_mpn,
        description=rep_desc,
        job_id=f"regen_{rep_mpn}",
        part_number=(rep_row.get("PART_NUMBER") or "").strip(),
        dept=(rep_row.get("Dept") or "").strip(),
        class_=(rep_row.get("Class") or "").strip(),
        fine=(rep_row.get("Fine") or "").strip(),
        sku_my_part_number=(rep_row.get("SKU - MY_PART_NUMBER") or "").strip(),
        input_e1_brand=(rep_row.get("E1_Brand") or "").strip(),
        input_unilog_brand=(rep_row.get("Unilog_Brand") or "").strip(),
        input_dib_brand=(rep_row.get("DIB_Brand") or "").strip(),
        input_part_manuf=(rep_row.get("Part_Manuf") or "").strip(),
        input_part_desc=rep_desc,
    )
    
    try:
        rep_final_state = graph.invoke(rep_initial_state)
        status = rep_final_state.get("status", "unknown")
        mfr_url = rep_final_state.get("mfr_url") or "(MISSING)"
        logger.info("  -> Rep Done: status=%s  mfr_url=%s", status, mfr_url)
        final_states.append(rep_final_state)
    except Exception as e:
        logger.exception("Pipeline FAILED for rep item %s: %s", rep_mpn, e)
        continue

    # Safe sibling propagation — only inherit SERIES_SHARED fields
    for sibling_row in rows[1:]:
        sib_mpn = (sibling_row.get("Mfg_Part_Num") or "").strip()
        sib_desc = (sibling_row.get("Part_Desc") or "").strip()
        logger.info("  -> Processing Sibling: %s", sib_mpn)

        # Clone the representative state
        sib_state = rep_final_state.copy()

        # Update identity fields
        sib_state["mpn"] = sib_mpn
        sib_state["description"] = sib_desc
        sib_state["job_id"] = f"regen_sib_{sib_mpn}"

        # Update passthrough input fields from CSV
        sib_state["part_number"] = (sibling_row.get("PART_NUMBER") or "").strip()
        sib_state["dept"] = (sibling_row.get("Dept") or "").strip()
        sib_state["class_"] = (sibling_row.get("Class") or "").strip()
        sib_state["fine"] = (sibling_row.get("Fine") or "").strip()
        sib_state["sku_my_part_number"] = (sibling_row.get("SKU - MY_PART_NUMBER") or "").strip()
        sib_state["input_part_desc"] = sib_desc

        # ── SAFE PROPAGATION: only keep SERIES_SHARED specs ──────────────────
        # VARIANT_SPECIFIC fields (size, voltage, grit, UPC, weight, etc.)
        # are cleared so they don't get incorrectly inherited by siblings.
        if "specifications" in sib_state and isinstance(sib_state["specifications"], dict):
            safe_specs = {}
            cleared = []
            for field_name, field_val in sib_state["specifications"].items():
                if is_series_shared(field_name):
                    # Mark as propagated (lower confidence)
                    if hasattr(field_val, "method"):
                        field_val = field_val.__class__(
                            value=field_val.value,
                            confidence=min(field_val.confidence, 0.65),
                            method="propagated_from_sibling",
                            cause=f"Propagated from representative sibling {rep_mpn}. Verify for this specific MPN.",
                            citation=getattr(field_val, "citation", None),
                        )
                    safe_specs[field_name] = field_val
                else:
                    cleared.append(field_name)
            sib_state["specifications"] = safe_specs
            if cleared:
                logger.info("  -> Sibling %s: cleared %d variant-specific fields: %s",
                            sib_mpn, len(cleared), cleared[:8])

        final_states.append(sib_state)
        logger.info("  -> Sibling Done: %s", sib_mpn)


if not final_states:
    logger.error("No products completed — cannot write CSV.")
    sys.exit(1)

# ── Export ────────────────────────────────────────────────────────────────────
csv_str = export_to_unilog_format(final_states)
out_path = Path("Master_Unilog_Output_Final_v2.csv")
try:
    out_path.write_text(csv_str, encoding="utf-8")
except PermissionError:
    out_path = Path("Master_Unilog_Output_Final_v3.csv")
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
