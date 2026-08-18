"""
pipeline/nodes.py — LangGraph node functions.

KEY CHANGES:
- node_retrieve: propagates mfr_url, ref_urls, all digital asset URLs
- node_interpret: passes subcategory to state for attribute ordering
- node_extract: passes subcategory to extractor for ordered fields
- node_copywrite: cleans manufacturer name from Part_Manuf codes
- node_finalize: promotes all commercial and digital asset fields
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from pipeline.utils import generate_with_retry, parse_json_response
from pipeline.state import PipelineState
from pipeline.interpreter import interpret
from pipeline.retriever import retrieve
from pipeline.extractor import extract
from pipeline.validator import validate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Universal fields every product must try to fill
# ---------------------------------------------------------------------------

_UNIVERSAL_FIELDS = [
    "upc", "ean", "gtin", "country_of_origin", "warranty",
    "list_price", "selling_qty", "selling_uom", "standard_packaging_info",
    "standards_approvals", "prop_65", "with_accessories", "application",
    "includes", "product_name", "trade_name", "alternate_part_number",
    "length", "length_uom", "height", "height_uom",
    "width", "width_uom", "weight", "weight_uom",
    "volume", "volume_uom", "discontinued",
]


# ---------------------------------------------------------------------------
# Manufacturer name cleaner
# ---------------------------------------------------------------------------

def _clean_manufacturer(raw: str) -> str:
    """
    Clean the Part_Manuf field into a proper manufacturer name.
    'Freud Inc (2435)' → 'Freud Inc'
    'Jam Industrial Supply LLC (JAMIN)' → 'Jam Industrial Supply LLC'
    'Appliance Dealers Cooperative (APPDE)' → 'Appliance Dealers Cooperative'
    """
    if not raw:
        return ""
    # Remove trailing (CODE) patterns
    clean = re.sub(r"\s*\([^)]*\)\s*$", "", raw.strip()).strip()
    return clean

def _resolve_true_brand(clean_manuf: str, description: str) -> str:
    """
    Heuristic to find the true brand if Part_Manuf is actually a distributor.
    Rule: if the description mentions a known brand or different company name,
    and Part_Manuf looks like a distributor, use the first word(s) of the desc.
    """
    if not clean_manuf:
        return ""
        
    lower_manuf = clean_manuf.lower()
    distributor_keywords = ["supply", "industrial", "dealer", "distributor", "cooperative", "wholesale"]
    
    is_distributor = any(k in lower_manuf for k in distributor_keywords)
    
    if is_distributor and description:
        # Grab the first 1-2 words of the description as the likely brand
        first_word = description.split()[0] if description else ""
        # Common brands that are single words
        if first_word.isalnum():
            return first_word
            
    return clean_manuf


# ---------------------------------------------------------------------------
# NODE: Interpret
# ---------------------------------------------------------------------------

def node_interpret(state: PipelineState) -> dict:
    logger.info("[Node] Interpret: %s %s", state["brand"], state["mpn"])
    logs = state.get("logs", [])
    
    # ── Identity Chain Step 1 & 2: Clean and resolve true brand ──
    raw_manuf = state.get("input_part_manuf") or state.get("brand") or ""
    clean_manuf = _clean_manufacturer(raw_manuf)
    
    # If the provided brand is unbranded/placeholder, or if we suspect it's a distributor
    current_brand = state["brand"]
    true_brand = current_brand
    
    if current_brand in ("-- Unbranded --", "", "-- No Unilog Brand --") or (
        clean_manuf and current_brand == raw_manuf
    ):
        resolved = _resolve_true_brand(clean_manuf, state.get("description", ""))
        if resolved:
            true_brand = resolved

    logger.info("Resolved brand identity: %s -> %s", current_brand, true_brand)

    try:
        res = interpret(
            true_brand,
            state["mpn"],
            state["description"],
            state.get("provided_schema"),
            state.get("strict_schema", False)
        )
        return {
            "brand": true_brand, # Overwrite state with true brand for downstream nodes
            "manufacturer_name": clean_manuf, # Keep the cleaned original for reference
            "category": res.category,
            "subcategory": res.subcategory,
            "classpath": res.classpath,
            "unspsc": res.unspsc,
            "expected_fields": res.expected_fields,
            "status": "in_progress",
            "logs": logs + [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node": "interpret",
                "message": (
                    f"Resolved Brand: {true_brand} | "
                    f"Classpath: {res.classpath} | "
                    f"UNSPSC: {res.unspsc} | "
                    f"Fields: {len(res.expected_fields)}"
                )
            }]
        }
    except Exception as e:
        return {
            "status": "failed", "error": str(e),
            "logs": logs + [{"timestamp": datetime.now(timezone.utc).isoformat(), "node": "interpret", "message": f"Error: {e}"}]
        }


# ---------------------------------------------------------------------------
# NODE: Retrieve
# ---------------------------------------------------------------------------

def node_retrieve(state: PipelineState) -> dict:
    logger.info("[Node] Retrieve: %s %s", state["brand"], state["mpn"])
    logs = state.get("logs", [])
    try:
        result = retrieve(
            state["brand"], state["mpn"], state["description"], state["category"]
        )
        chunks = result["chunks"]
        mfr_url = result.get("mfr_url")
        ref_urls = result.get("ref_urls", [])

        # Build source_urls for backward compat: mfr_url first, then ref_urls
        source_urls = []
        if mfr_url:
            source_urls.append(mfr_url)
        for u in ref_urls:
            if u not in source_urls:
                source_urls.append(u)

        return {
            "raw_documents": chunks,
            "mfr_url": mfr_url,
            "ref_urls": ref_urls,
            "source_urls": source_urls,
            "product_image_url": result.get("product_image_url"),
            "alternate_image_urls": result.get("alternate_image_urls", []),
            "spec_sheet_url": result.get("spec_sheet_url"),
            "sds_url": result.get("sds_url"),
            "manual_url": result.get("manual_url"),
            "installation_url": result.get("installation_url"),
            "warranty_url": result.get("warranty_url"),
            "catalog_url": result.get("catalog_url"),
            "energy_guide_url": result.get("energy_guide_url"),
            "logs": logs + [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node": "retrieve",
                "message": (
                    f"Chunks: {len(chunks)} | "
                    f"MFR URL: {mfr_url or 'not found'} | "
                    f"Ref URLs: {len(ref_urls)} | "
                    f"Image: {bool(result.get('product_image_url'))} | "
                    f"Spec Sheet: {bool(result.get('spec_sheet_url'))} | "
                    f"SDS: {bool(result.get('sds_url'))} | "
                    f"Manual: {bool(result.get('manual_url'))}"
                )
            }]
        }
    except Exception as e:
        return {
            "status": "failed", "error": str(e),
            "logs": logs + [{"timestamp": datetime.now(timezone.utc).isoformat(), "node": "retrieve", "message": f"Error: {e}"}]
        }


# ---------------------------------------------------------------------------
# NODE: Extract
# ---------------------------------------------------------------------------

def node_extract(state: PipelineState) -> dict:
    # Always add universal fields on top of category-specific fields
    expected = list(state.get("expected_fields", []))
    for uf in _UNIVERSAL_FIELDS:
        if uf not in expected:
            expected.append(uf)

    logger.info("[Node] Extract: %d fields (%d category + universal)",
                len(expected), len(state.get("expected_fields", [])))
    logs = state.get("logs", [])
    try:
        extracted = extract(
            state["brand"],
            state["mpn"],
            state["description"],
            state["category"],
            expected,
            state.get("raw_documents", []),
            subcategory=state.get("subcategory") or "",
        )
        graph_used = any(
            f.source_type == "inferred" for f in extracted.values()
            if hasattr(f, "source_type")
        )
        series_val = extracted.get("series")
        series_found = series_val and series_val.value is not None
        bonus_count = sum(1 for f in extracted.keys() if f not in expected)

        msg = (
            f"Extracted {len(extracted)} fields total "
            f"({bonus_count} bonus) | "
            f"Series: {'✓ ' + str(series_val.value) if series_found else '✗ not found'}"
        )
        if graph_used:
            msg += " | KG inference triggered."

        return {
            "extracted_fields": extracted,
            "logs": logs + [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node": "extract",
                "message": msg
            }]
        }
    except Exception as e:
        return {
            "status": "failed", "error": str(e),
            "logs": logs + [{"timestamp": datetime.now(timezone.utc).isoformat(), "node": "extract", "message": f"Error: {e}"}]
        }


# ---------------------------------------------------------------------------
# NODE: Validate
# ---------------------------------------------------------------------------

def node_validate(state: PipelineState) -> dict:
    logger.info("[Node] Validate")
    logs = state.get("logs", [])
    try:
        specs, overall, flagged = validate(
            state.get("extracted_fields", {}), state.get("raw_documents", [])
        )

        from pipeline.knowledge_graph import ingest_validated_product
        ingest_validated_product(state["brand"], state["mpn"], state["category"], specs)

        provenance = {
            k: {
                "value": v.value,
                "source": v.source_type if hasattr(v, "source_type") else getattr(v, "method", "unknown"),
                "url": getattr(v, "url", None),
                "snippet": getattr(v, "snippet", None)[:100] if getattr(v, "snippet", None) else None,
            }
            for k, v in specs.items() if v.value is not None
        }
        logger.info("[Validate] Provenance: %d fields with sources", len(provenance))

        return {
            "specifications": specs,
            "overall_confidence": overall,
            "flagged_for_review": flagged,
            "logs": logs + [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node": "validate",
                "message": (
                    f"Confidence: {overall*100:.0f}% | "
                    f"Flagged: {len(flagged)} | "
                    f"Provenance: {len(provenance)} fields"
                ),
                "provenance": provenance
            }]
        }
    except Exception as e:
        return {
            "status": "failed", "error": str(e),
            "logs": logs + [{"timestamp": datetime.now(timezone.utc).isoformat(), "node": "validate", "message": f"Error: {e}"}]
        }


# ---------------------------------------------------------------------------
# NODE: Review gate
# ---------------------------------------------------------------------------

def node_review_gate(state: PipelineState) -> dict:
    overall = state.get("overall_confidence", 0.0)
    force = state.get("force_review", False)
    logger.info("[Node] Review Gate (conf=%.2f, force=%s)", overall, force)
    if force or overall < 0.0:
        return {"status": "needs_review"}
    return {}


# ---------------------------------------------------------------------------
# NODE: Copywrite (descriptions + brand normalization)
# ---------------------------------------------------------------------------

def node_copywrite(state: PipelineState) -> dict:
    logger.info("[Node] Copywrite")
    api_key = os.getenv("GROQ_API_KEY", "")
    offline = os.getenv("OFFLINE_DEMO", "false").lower() == "true"
    logs = state.get("logs", [])

    # Use the resolved true brand and cleaned manufacturer from interpret
    clean_brand = state.get("brand", "")
    clean_manuf = state.get("manufacturer_name", "") or _clean_manufacturer(state.get("input_part_manuf") or "")

    specs = state.get("specifications", {})
    all_facts = {k: v.value for k, v in specs.items() if v.value is not None}
    validated_facts = {k: v for k, v in all_facts.items() if specs[k].confidence >= 0.75}

    raw_docs = state.get("raw_documents", [])
    raw_context = "\n\n".join(
        chunk.get("text", "")[:400] for chunk in raw_docs[:3] if chunk.get("text")
    )[:2000]

    # Get series value from specs
    series_val = all_facts.get("series") or ""
    subcategory = state.get("subcategory") or state.get("category") or ""
    unspsc_from_interpret = state.get("unspsc") or ""

    if not api_key or offline:
        return {
            "status": "complete",
            "manufacturer_name": clean_manuf,
            "brand_name": clean_brand,
            "unspsc": unspsc_from_interpret or "00000000",
            "item_features": [],
        }

    prompt = f"""Unilog product content engine. Output JSON only.
Brand: {clean_brand} | Manufacturer: {clean_manuf} | MPN: {state['mpn']}
Classpath: {state.get('classpath')} | Subcategory: {subcategory}
Series: {series_val}
Input Desc: {state.get('description', '')}
Specs: {json.dumps(validated_facts)[:1500]}
Context: {raw_context[:1000]}

UNILOG CONTENT RULES:
1. invoice_desc: ≤40 chars, ALL CAPS. Item type FIRST (not brand).
   Abbreviations: SST=Stainless Steel, V=Volts, A=Amps, IN=Inches, EA=Each, BX=Box.
   BLTLN=Built-in, FRSTND=Freestanding, CNTR=Counter.
   Fractions: 50.25in→50-1/4IN. Example: "DISHWASHER LEG 5 SST 120V 15A 50-1/4IN"
   Use voltage + amperage if known. Use dominant material (SST, WHT, BLK).
2. mobile_desc: 60-80 chars. Format: "Brand ProductType, Series, MPN, MountType"
3. short_desc: "Brand® Series MPN ItemType With KeyFeature, MountType, Size, Material"
   ALWAYS use ® and ™ symbols where they apply to brands.
4. long_desc: 80-150 word paragraph. All specs, fraction inches (50-1/4 in), full sentences.
5. retail_desc: 1-2 consumer-friendly sentences focusing on benefits.
6. marketing_description: 2-3 marketing sentences emphasizing value propositions.
   Use the OFFICIAL marketing copy from the raw context if available.
7. item_features: 10-20 bullet points each ≤80 chars, starting with verbs or key specs.
8. unspsc: 8-digit UNSPSC code. Hint: {unspsc_from_interpret or "use category knowledge"}
9. product_name: short marketing name (3-6 words), e.g. "Dishwasher" or "24-Inch Dishwasher"
10. trade_name: series/line name only (e.g. "Professional Series", "Eco Series")
11. manufacturer_name: full legal company name. If brand is well-known (Frigidaire, Whirlpool)
    use the actual parent OEM legal name (e.g. "Whirlpool Corporation", "Frigidaire" = Electrolux brand).
12. brand_name: ALWAYS include ® or ™ trademark symbol as officially trademarked.
    Examples: "FRIGIDAIRE®", "Whirlpool®", "3M™", "DeWalt®". NEVER omit the symbol.
13. with_accessories: "With X" format listing key included features (e.g. "With CleanBoost™")
14. standards_approvals: pipe-separated certs from context (UL Listed|ENERGY STAR|NSF Certified)
15. application: primary use case (e.g. "Residential Dishwashing")
16. includes: box contents (pipe-separated if multiple items)
17. country_of_origin: country name only
18. warranty: FULL warranty string matching manufacturer spec exactly.
    Example: "1 Year Manufacturer, 1 Year Labor and Parts"

Return JSON with ALL keys: invoice_desc, mobile_desc, short_desc, long_desc,
retail_desc, marketing_description, item_features (array), unspsc,
product_name, trade_name, manufacturer_name, brand_name, with_accessories,
standards_approvals, application, includes, country_of_origin, warranty."""

    messages = [
        {"role": "system", "content": "You output only valid JSON for product catalog content. Follow Unilog content rules exactly."},
        {"role": "user", "content": prompt}
    ]

    resp_raw = generate_with_retry(
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    data = parse_json_response(resp_raw)

    item_features = data.get("item_features", [])
    if isinstance(item_features, list):
        item_features = [str(f)[:80] for f in item_features[:20]]
    else:
        item_features = []

    unspsc_code = data.get("unspsc") or unspsc_from_interpret or "00000000"
    manufacturer_name = data.get("manufacturer_name") or clean_manuf
    brand_name = data.get("brand_name") or clean_brand

    logger.info(
        "[Copywriter] manufacturer=%s brand=%s features=%d UNSPSC=%s",
        manufacturer_name, brand_name, len(item_features), unspsc_code
    )

    return {
        "invoice_desc": data.get("invoice_desc"),
        "mobile_desc": data.get("mobile_desc"),
        "short_desc": data.get("short_desc"),
        "long_desc": data.get("long_desc"),
        "retail_desc": data.get("retail_desc"),
        "marketing_description": data.get("marketing_description"),
        "item_features": item_features,
        "manufacturer_name": manufacturer_name,
        "brand_name": brand_name,
        "unspsc": unspsc_code,
        "product_name": data.get("product_name"),
        "trade_name": data.get("trade_name") or series_val or None,
        "with_accessories": data.get("with_accessories"),
        "standards_approvals": data.get("standards_approvals"),
        "application_desc": data.get("application"),
        "includes_desc": data.get("includes"),
        "country_of_origin": data.get("country_of_origin"),
        "warranty": data.get("warranty"),
        "status": "complete",
        "logs": logs + [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "copywrite",
            "message": (
                f"Descriptions generated. UNSPSC={unspsc_code}. "
                f"Manufacturer={manufacturer_name}. Brand={brand_name}. "
                f"Features={len(item_features)}."
            )
        }]
    }


# ---------------------------------------------------------------------------
# NODE: Finalize
# ---------------------------------------------------------------------------

def node_finalize(state: PipelineState) -> dict:
    """Promote extracted spec values to top-level state fields."""
    logger.info("[Node] Finalize")
    specs = state.get("specifications", {})

    def _from_specs(field: str) -> str | None:
        if state.get(field):
            return None  # Already set
        fv = specs.get(field)
        if fv is None:
            return None
        val = fv.value if hasattr(fv, "value") else (fv.get("value") if isinstance(fv, dict) else None)
        return str(val) if val is not None else None

    updates: dict = {}
    for field in _UNIVERSAL_FIELDS:
        promoted = _from_specs(field)
        if promoted:
            updates[field] = promoted

    # Promote dimension fields explicitly
    for dim in ["upc", "ean", "gtin", "length", "length_uom", "height", "height_uom",
                "width", "width_uom", "weight", "weight_uom", "volume", "volume_uom"]:
        val = _from_specs(dim)
        if val:
            updates[dim] = val

    if state.get("status") not in ("failed", "needs_review"):
        updates["status"] = "complete"

    return updates
