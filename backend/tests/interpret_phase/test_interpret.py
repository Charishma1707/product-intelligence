import csv
import json
import os
import sys
from pathlib import Path

# Add backend dir to path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BACKEND_DIR))

from pipeline.nodes import node_identity, node_taxonomy
from pipeline.graph import make_initial_state
from pipeline.knowledge_store import init_db
import time

def test_interpret():
    # Initialize DB before running
    init_db()
    
    sample_file = BACKEND_DIR / "sample_data" / "sample_products.csv"
    output_dir = BACKEND_DIR / "tests" / "interpret_phase"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    with open(sample_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if count >= 10:
                break
                
            brand = row.get("brand") or ""
            mpn = row.get("mpn") or ""
            description = row.get("description") or ""
            
            # Setup initial state
            state = make_initial_state(
                brand=brand,
                mpn=mpn,
                description=description,
            )
            
            print(f"--- Processing {count+1}: {brand} {mpn} ---")
            
            # 1. Identity
            id_result = node_identity(state)
            state.update(id_result)
            
            # 2. Taxonomy
            tax_result = node_taxonomy(state)
            state.update(tax_result)
            
            # Sleep to avoid LLM rate limit
            time.sleep(2)
            
            out_data = {
                "input": {
                    "brand": brand,
                    "mpn": mpn,
                    "description": description,
                    "raw_row": row
                },
                "output": {
                    "resolved_brand": state.get("brand"),
                    "manufacturer_name": state.get("manufacturer_name"),
                    "category": state.get("category"),
                    "subcategory": state.get("subcategory"),
                    "classpath": state.get("classpath"),
                    "unspsc": state.get("unspsc"),
                    "expected_fields": state.get("expected_fields"),
                    "taxonomy_confidence": state.get("taxonomy_confidence"),
                    "status": state.get("status"),
                }
            }
            results.append(out_data)
            count += 1
            
    out_file = output_dir / "interpret_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSaved {len(results)} results to {out_file}")
    
if __name__ == "__main__":
    test_interpret()
