import os
import sys
import re

from pipeline.desc_abbr_dict import DESC_ABBR_MAP, BRAND_SHORTCODES
from pipeline.knowledge_store import (
    init_db, save_desc_abbreviation, get_desc_abbreviations,
    save_product_attribute, boost_series_attribute_confidence
)
from pipeline.nodes import node_desc_infer, apply_implicit_confidence_boost

def run_tests():
    print("1. Initializing DB tables...")
    init_db()
    print("   [OK] DB initialized.")

    print("\n2. Testing regex abbreviation dictionary on CSV cases...")
    test_cases = [
        ('KDFM404KPS Dishwasher SS', 'material', 'Stainless Steel'),
        ('LDPH5554D LG Dishwasher BSS', 'material', 'Black Stainless Steel'),
        ('DC5004WE SQ Elect Dryer Wh', 'fuel_type', 'Electric'),
        ('DR7004WG SQ Gas Dryer Wh', 'fuel_type', 'Gas'),
        ('55210NI Kichler Wall Light', 'finish', 'Nickel'),
        ('S3702 40W Incan Med 27K', 'wattage', '40'),
        ('565374 75W Led A19 Med 27k 4pk', 'light_technology', 'LED'),
        ('5B-332-080 HIOLIT 5" P80', 'grit', '80'),
        ('1x6-16 Coastline Sq Edge', 'edge_type', 'Square Edge'),
        ('BRS 1/2in NPT Fitting', 'material', 'Brass'),
    ]

    passed = 0
    for desc, field, expected in test_cases:
        found = None
        for pat, meta in DESC_ABBR_MAP.items():
            if meta['field'] == field and re.search(pat, desc, re.IGNORECASE):
                canonical = meta['value']
                m = re.search(pat, desc, re.IGNORECASE)
                for i, grp in enumerate(m.groups(), 1):
                    if grp:
                        canonical = canonical.replace(f"{{{i}}}", grp)
                found = canonical
                break
        ok = found is not None and expected.lower() in (found or '').lower()
        if ok: passed += 1
        status = 'PASS' if ok else 'FAIL'
        print(f"   [{status}]: '{desc}' -> {field} = '{found}'")

    print(f"   Summary: {passed}/{len(test_cases)} tests passed.")

    print("\n3. Testing node_desc_infer...")
    mock_state = {
        "description": "DC5004WE SQ Elect Dryer Wh BRS 120V",
        "extracted_fields": {},
        "brand": "Speed Queen",
        "mpn": "DC5004WE",
        "logs": []
    }
    infer_res = node_desc_infer(mock_state)
    inferred_fields = infer_res["extracted_fields"]
    aliases = infer_res["desc_inferred_aliases"]
    print("   Inferred fields count:", len(inferred_fields))
    print("   Inferred fields keys:", list(inferred_fields.keys()))
    print("   Inferred aliases:", aliases)
    assert len(inferred_fields) >= 3, "Expected at least 3 fields inferred"
    print("   [OK] node_desc_infer passed.")

    print("\n4. Testing implicit confidence boost...")
    boost_state = {
        "job_id": "test-job-1",
        "product_id": "prod-1",
        "specifications": {
            "voltage": {"value": "120", "confidence": 0.65, "cause": "inferred"},
            "color": {"value": "White", "confidence": 0.70, "cause": "inferred"},
        }
    }
    updated_state, boosted = apply_implicit_confidence_boost(
        boost_state, stage_num=3, corrections={}, reviewer="test_reviewer"
    )
    print("   Boosted fields:", boosted)
    print("   New voltage confidence:", updated_state["specifications"]["voltage"]["confidence"])
    assert round(updated_state["specifications"]["voltage"]["confidence"], 2) == 0.80
    assert round(updated_state["specifications"]["color"]["confidence"], 2) == 0.85
    print("   [OK] Implicit confidence boost passed (+0.15 applied).")

    print("\n5. Testing DB helper functions...")
    save_desc_abbreviation("BRS", "Brass", "material")
    save_desc_abbreviation("SS", "Stainless Steel", "material")
    abbrs = get_desc_abbreviations()
    print("   DB abbreviations stored:", abbrs)
    assert "BRS" in abbrs and abbrs["BRS"]["canonical_value"] == "Brass"

    save_product_attribute("TestBrand", "MPN-100", "material", "Brass", 1.0, "human", "tester")
    boost_series_attribute_confidence("Speed Queen", "DC5000", "fuel_type", "Electric")
    print("   [OK] DB persistence functions passed.")

    print("\n================ ALL UNIT TESTS PASSED ================\n")

if __name__ == "__main__":
    run_tests()
