import csv
import logging
import sys
from pathlib import Path

# Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("trace")

from dotenv import load_dotenv
BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

from pipeline.graph import build_graph, make_initial_state
from exporter import export_to_unilog_format

def trace_product(target_mpn):
    input_csv = BASE.parent / "Unihack_ Sample Dataset - Input.csv"
    expected_csv = BASE.parent / "Unihack_ Expected Output - Delivery Format.csv"
    
    target_row = None
    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("Mfg_Part_Num") or "").strip() == target_mpn:
                target_row = row
                break
                
    if not target_row:
        logger.error(f"Could not find {target_mpn} in input dataset")
        return
        
    expected_row = None
    with open(expected_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("PART_NUMBER") or "").strip() == target_mpn:
                expected_row = row
                break

    brand = (target_row.get("Part_Manuf") or target_row.get("E1_Brand") or "").strip()
    desc = (target_row.get("Part_Desc") or "").strip()
    
    initial_state = make_initial_state(
        brand=brand,
        mpn=target_mpn,
        description=desc,
        job_id=f"trace_{target_mpn}",
        part_number=(target_row.get("PART_NUMBER") or "").strip(),
        dept=(target_row.get("Dept") or "").strip(),
        class_=(target_row.get("Class") or "").strip(),
        fine=(target_row.get("Fine") or "").strip(),
        sku_my_part_number=(target_row.get("SKU - MY_PART_NUMBER") or "").strip(),
        input_e1_brand=(target_row.get("E1_Brand") or "").strip(),
        input_unilog_brand=(target_row.get("Unilog_Brand") or "").strip(),
        input_dib_brand=(target_row.get("DIB_Brand") or "").strip(),
        input_part_manuf=(target_row.get("Part_Manuf") or "").strip(),
        input_part_desc=desc,
    )
    
    logger.info("Starting Pipeline Trace for %s", target_mpn)
    graph = build_graph()
    final_state = graph.invoke(initial_state)
    
    logger.info("Pipeline Finished.")
    logger.info("Exporting to Unilog Format...")
    
    output_rows = export_to_unilog_format([final_state])
    if not output_rows:
        logger.error("No output rows generated!")
        return
        
    actual_row = output_rows[0]
    
    print("\n" + "="*80)
    print(f"TRACE RESULTS FOR {target_mpn}")
    print("="*80)
    
    if not expected_row:
        print("NOTE: No expected row found in Delivery Format to compare against.")
        for k, v in actual_row.items():
            if v:
                print(f"{k}: {v}")
        return

    print(f"{'FIELD':<30} | {'EXPECTED':<40} | {'ACTUAL (OUR PIPELINE)':<40}")
    print("-" * 115)
    
    all_keys = set(expected_row.keys()).union(set(actual_row.keys()))
    
    # Sort keys for readability
    first_keys = ["SKU - MY_PART_NUMBER", "PART_NUMBER", "MANUFACTURER_NAME", "Item_Description", "ITEM_FEATURES"]
    sorted_keys = first_keys + [k for k in sorted(all_keys) if k not in first_keys and not k.startswith("ATTR")]
    attr_keys = sorted([k for k in all_keys if k.startswith("ATTR")])
    sorted_keys.extend(attr_keys)
    
    matches = 0
    mismatches = 0
    misses = 0
    
    for key in sorted_keys:
        if not key: continue
        exp_val = str(expected_row.get(key, "")).strip()
        act_val = str(actual_row.get(key, "")).strip()
        
        # Unilog output contains ATTR_NAME_1, ATTR_VAL_1, ATTR_UOM_1
        # Let's just print the values that are populated in either
        if not exp_val and not act_val:
            continue
            
        status = " "
        if exp_val and act_val:
            if exp_val.lower() == act_val.lower():
                status = "✅"
                matches += 1
            else:
                status = "❌"
                mismatches += 1
        elif exp_val and not act_val:
            status = "⚠️"
            misses += 1
        elif act_val and not exp_val:
            status = "➕"
            
        print(f"{status} {key:<28} | {exp_val[:38]:<40} | {act_val[:38]:<40}")

    print("-" * 115)
    print(f"Matches: {matches} | Mismatches: {mismatches} | Misses: {misses}")
    print("="*80)

if __name__ == "__main__":
    mpn = sys.argv[1] if len(sys.argv) > 1 else "WDTS7024RZ"
    trace_product(mpn)
