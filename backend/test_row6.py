from pipeline.nodes import node_identity, node_desc_infer, _clean_manufacturer, _resolve_true_brand
from pipeline.graph import make_initial_state
import json

row_mpn = '3MABR-7100075690'
row_desc = '3M 775L Stikit Film P180 - Cubitron II 50 Disc/Box'
row_manuf = 'Jam Industrial Supply LLC (JAMIN)'

clean_manuf = _clean_manufacturer(row_manuf)
true_brand = _resolve_true_brand(clean_manuf, row_desc, mpn=row_mpn)
state = make_initial_state(brand=row_manuf, mpn=row_mpn, description=row_desc, input_part_manuf=row_manuf)
id_res = node_identity(state)
state.update(id_res)
infer_res = node_desc_infer(state)

print("=" * 60)
print("6TH PRODUCT IN CSV — TEST RESULTS")
print("=" * 60)
print("Raw Input MPN          :", row_mpn)
print("Raw Input Part_Desc    :", row_desc)
print("Raw Input Part_Manuf   :", row_manuf)
print("-" * 60)
print("Expected Manufacturer  :", state.get("manufacturer_name"))
print("Expected Brand         :", state.get("brand"))
print("Expected Part Number   :", state.get("mpn"))
print("-" * 60)
print("Description-Inferred Specifications:")
for k, v in infer_res.get("extracted_fields", {}).items():
    val = v.get("value")
    cause = v.get("cause")
    conf = v.get("confidence")
    print(f"  * {k:15}: {val:15} [Conf: {conf}] -> {cause}")
print("=" * 60)
