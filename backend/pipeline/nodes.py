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
from pipeline.knowledge_store import get_canonical_brand, save_brand_alias

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
    """
    if not raw:
        return ""
    # Regex removed as per user request to not strip ()
    return raw.strip()


# ---------------------------------------------------------------------------
# NODE: Identity
# ---------------------------------------------------------------------------

def node_identity(state: PipelineState) -> dict:
    logger.info("[Node] Identity: %s %s", state.get("brand"), state.get("mpn"))
    logs = state.get("logs", [])
    
    raw_manuf = state.get("input_part_manuf") or state.get("brand") or ""
    clean_manuf = _clean_manufacturer(raw_manuf)
    
    return {
        "manufacturer_name": clean_manuf, 
        "status": "in_progress",
        "logs": logs + [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "identity",
            "message": f"Cleaned input manufacturer: {clean_manuf}"
        }]
    }

# ---------------------------------------------------------------------------
# NODE: Taxonomy
# ---------------------------------------------------------------------------

def node_taxonomy(state: PipelineState) -> dict:
    logger.info("[Node] Taxonomy: %s %s", state["brand"], state["mpn"])
    logs = state.get("logs", [])
    try:
        res = interpret(
            state["brand"],
            state["mpn"],
            state["description"],
            state.get("provided_schema"),
            state.get("strict_schema", False)
        )
        return {
            "brand": res.true_brand,
            "manufacturer_name": res.true_manufacturer,
            "category": res.category,
            "subcategory": res.subcategory,
            "classpath": res.classpath,
            "unspsc": res.unspsc,
            "expected_fields": res.expected_fields,
            "taxonomy_leaf": res.subcategory,
            "taxonomy_confidence": 0.9 if not res.used_fallback else 0.4,
            "status": "in_progress",
            "logs": logs + [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node": "taxonomy",
                "message": (
                    f"Resolved Brand: {res.true_brand} | "
                    f"Classpath: {res.classpath} | "
                    f"UNSPSC: {res.unspsc} | "
                    f"Fields: {len(res.expected_fields)}"
                )
            }]
        }
    except Exception as e:
        return {
            "status": "failed", "error": str(e),
            "logs": logs + [{"timestamp": datetime.now(timezone.utc).isoformat(), "node": "taxonomy", "message": f"Error: {e}"}]
        }

# ---------------------------------------------------------------------------
# NODE: Series
# ---------------------------------------------------------------------------

def node_series(state: PipelineState) -> dict:
    logger.info("[Node] Series: %s %s", state["brand"], state["mpn"])
    logs = state.get("logs", [])
    
    from pipeline.extractor import _extract_series
    
    series_val = _extract_series(
        state["brand"],
        state["mpn"],
        state["description"],
        state["category"],
        state.get("raw_documents", [])
    )
    
    return {
        "series": series_val,
        "logs": logs + [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "series",
            "message": f"Found series: {series_val}" if series_val else "No series found."
        }]
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

        mpn_verified = result.get("mpn_verified", False)
        return {
            "raw_documents": chunks,
            "mfr_url": mfr_url,
            "ref_urls": ref_urls,
            "source_urls": source_urls,
            "mpn_verified": mpn_verified,
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
                    f"MPN Verified: {'✓ Yes' if mpn_verified else '✗ No'} | "
                    f"Ref URLs: {len(ref_urls)} | "
                    f"Image: {bool(result.get('product_image_url'))} | "
                    f"Spec Sheet: {bool(result.get('spec_sheet_url'))}"
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
            state.get("extracted_fields", {}),
            state.get("raw_documents", []),
            category=state.get("category", ""),
            description=state.get("description", ""),
        )

        from pipeline.knowledge_graph import ingest_validated_product
        ingest_validated_product(state["brand"], state["mpn"], state["category"], specs)

        provenance = {}
        for k, v in specs.items():
            val = v.get("value") if isinstance(v, dict) else getattr(v, "value", None)
            if val is not None:
                stype = v.get("source_type", v.get("method", "unknown")) if isinstance(v, dict) else (getattr(v, "source_type", None) or getattr(v, "method", "unknown"))
                u = v.get("url") if isinstance(v, dict) else getattr(v, "url", None)
                snip = v.get("snippet") if isinstance(v, dict) else getattr(v, "snippet", None)
                provenance[k] = {
                    "value": val,
                    "source": stype,
                    "url": u,
                    "snippet": snip[:100] if snip else None,
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
    tax_conf = state.get("taxonomy_confidence", 1.0)
    force = state.get("force_review", False)
    flagged = state.get("flagged_for_review", [])
    
    logger.info("[Node] Review Gate (overall=%.2f, tax=%.2f, flagged=%d, force=%s)", 
                overall, tax_conf, len(flagged), force)
    
    needs_review = force or overall < 0.8 or tax_conf < 0.8 or len(flagged) > 0
    
    if needs_review:
        review_items = []
        specs = state.get("specifications", {})
        
        for fname in flagged:
            val = specs.get(fname)
            if val:
                v_val = val.get("value") if isinstance(val, dict) else getattr(val, "value", None)
                v_conf = val.get("confidence", 0.0) if isinstance(val, dict) else getattr(val, "confidence", 0.0)
                v_cause = val.get("cause", "") if isinstance(val, dict) else getattr(val, "cause", "")
                review_items.append({
                    "type": "field",
                    "field": fname,
                    "value": v_val,
                    "confidence": v_conf,
                    "cause": v_cause,
                })
        
        # Add taxonomy review if needed
        if tax_conf < 0.8:
            review_items.append({
                "type": "taxonomy",
                "category": state.get("category"),
                "subcategory": state.get("subcategory"),
                "confidence": tax_conf,
                "cause": "Taxonomy classification was low confidence (fallback used)."
            })
            
        return {
            "status": "needs_review",
            "human_review_items": review_items,
            "logs": state.get("logs", []) + [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node": "review_gate",
                "message": f"Paused for human review. {len(review_items)} items flagged."
            }]
        }
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
    all_facts = {}
    validated_facts = {}
    for k, v in specs.items():
        val = v.get("value") if isinstance(v, dict) else getattr(v, "value", None)
        conf = v.get("confidence", 0.0) if isinstance(v, dict) else getattr(v, "confidence", 0.0)
        if val is not None:
            all_facts[k] = val
            if conf >= 0.75:
                validated_facts[k] = val

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


# ---------------------------------------------------------------------------
# NODE: HITL Supervisor Routing Agent
# ---------------------------------------------------------------------------

def node_hitl_supervisor(state: PipelineState, corrections: dict, reviewer: str = "human") -> dict:
    """
    Intelligent LangGraph Supervisor Node for Human-in-the-Loop.
    Inspects human feedback and decides which node to route to next:
    - If Brand or MPN changed -> Routes to 'node_retrieve' to rediscover official manufacturer documentation.
    - If Sourcing URLs changed -> Routes to 'node_retrieve' to ingest documents into ChromaDB, then 'node_extract'.
    - If Taxonomy / Category changed -> Routes to 'node_taxonomy' to recalculate UNSPSC and category schema.
    - If Attributes / Specifications changed -> Routes to 'node_validate', persists series knowledge, then 'node_copywrite'.
    - If Descriptions changed -> Routes to 'node_finalize'.
    """
    logs = state.get("logs", [])
    current_status = state.get("status", "needs_review")

    has_identity = any(k in corrections for k in ("brand", "mpn", "manufacturer_name"))
    has_urls = any(k in corrections for k in ("mfr_url", "spec_sheet_url", "manual_url", "installation_url", "sds_url", "product_image_url"))
    has_copywriting = any(k in corrections for k in ("invoice_desc", "short_desc", "long_desc", "marketing_description"))

    # 1. Identity change -> Route to Node 2 (retrieve)
    if current_status == "needs_review_identity" or has_identity:
        for k in ("brand", "mpn", "manufacturer_name"):
            if k in corrections:
                state[k] = corrections[k]

        logger.info("[Supervisor Agent] Identity confirmed/modified. Routing LangGraph -> 'node_retrieve'.")
        logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "hitl_supervisor",
            "message": "Supervisor Agent routed to 'node_retrieve' for document sourcing."
        })
        state["logs"] = logs
        retrieved = node_retrieve(state)
        state.update(retrieved)
        state["status"] = "needs_review_retrieval"
        return state

    # 2. Sourcing URLs change -> Route to Node 3 (taxonomy + series + extract)
    if current_status == "needs_review_retrieval" or has_urls:
        for f in ("mfr_url", "spec_sheet_url", "manual_url", "installation_url", "warranty_url", "catalog_url", "energy_guide_url", "sds_url", "product_image_url"):
            if f in corrections:
                state[f] = corrections[f]

        logger.info("[Supervisor Agent] Sourcing URLs verified. Routing LangGraph -> 'node_taxonomy' -> 'node_series' -> 'node_extract'.")
        logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "hitl_supervisor",
            "message": "Supervisor Agent routed to 'node_taxonomy' and 'node_extract' for attribute extraction."
        })
        state["logs"] = logs
        state.update(node_taxonomy(state))
        state.update(node_series(state))
        state.update(node_extract(state))
        state["status"] = "needs_review_extraction"
        return state

    # 3. Extraction / Attribute verification -> Route to Node 4 (validate + copywrite + finalize)
    if current_status in ("needs_review_extraction", "needs_review") or not has_copywriting:
        specs = state.get("specifications", {})
        brand = state.get("brand", "")
        series = state.get("series") or (specs.get("series", {}).get("value") if isinstance(specs.get("series"), dict) else getattr(specs.get("series"), "value", None))
        pid = state.get("product_id") or state.get("job_id")

        from pipeline.knowledge_store import save_human_review, save_series_knowledge, increment_metric, save_attribute_alias
        from pipeline.extractor import is_series_shared

        for fname, cval in corrections.items():
            if fname in specs:
                old_val = specs[fname].get("value") if isinstance(specs[fname], dict) else getattr(specs[fname], "value", None)
                if isinstance(specs[fname], dict):
                    specs[fname]["value"] = cval
                    specs[fname]["confidence"] = 1.0
                    specs[fname]["method"] = "human_verified"
                    specs[fname]["cause"] = f"Verified and corrected by reviewer ({reviewer})."
                else:
                    specs[fname].value = cval
                    specs[fname].confidence = 1.0
                    specs[fname].method = "human_verified"
                    specs[fname].cause = f"Verified and corrected by reviewer ({reviewer})."

                save_human_review(pid, fname, str(old_val), str(cval), f"approved_by_{reviewer}")

                if old_val and cval and str(old_val).strip().lower() != str(cval).strip().lower():
                    save_attribute_alias(str(old_val), str(cval))

                if series and is_series_shared(fname):
                    save_series_knowledge(
                        manufacturer=brand,
                        series=str(series),
                        attribute=fname,
                        value=str(cval),
                        scope="series",
                        confidence=1.0,
                        source="human_verified"
                    )
                    increment_metric("series_hits", 1)
            elif fname in ("category", "subcategory", "unspsc"):
                state[fname] = cval

        state["specifications"] = specs

        logger.info("[Supervisor Agent] Attributes verified. Routing LangGraph -> 'node_validate' -> 'node_copywrite' -> 'node_finalize'.")
        logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "hitl_supervisor",
            "message": "Supervisor Agent routed to 'node_validate' and 'node_copywrite'."
        })
        state["logs"] = logs
        state.update(node_validate(state))
        state.update(node_copywrite(state))
        state.update(node_finalize(state))
        state["status"] = "needs_review_final"
        return state

    # 4. Final Copywriting approved -> Route to Stage 5 (needs_review_delivery)
    if current_status == "needs_review_final":
        for k, v in corrections.items():
            state[k] = v
        state["status"] = "needs_review_delivery"
        logger.info("[Supervisor Agent] Copywriting approved. Routing LangGraph -> 'needs_review_delivery' (Stage 5: Final Delivery Fields).")
        logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "hitl_supervisor",
            "message": "Supervisor Agent routed to Stage 5: Final Delivery Fields Table."
        })
        state["logs"] = logs
        return state

    # 5. Stage 5 Delivery Fields approved -> Post-approval persistence & Complete
    for k, v in corrections.items():
        state[k] = v
    persist_res = node_post_approval_persist(state, reviewer)
    state.update(persist_res)
    state["status"] = "complete"
    logger.info("[Supervisor Agent] Final delivery fields approved. Post-approval learning complete. Workflow COMPLETE.")
    logs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "hitl_supervisor",
        "message": "Supervisor Agent finalized enrichment and persisted all knowledge to DB & Knowledge Graph."
    })
    state["logs"] = logs
    return state


# ---------------------------------------------------------------------------
# NODE: Description Inference (Regex + LLM abbreviation expansion)
# ---------------------------------------------------------------------------

# Stage-to-field mapping for implicit confidence boost
_STAGE_FIELD_SCOPE: dict[int, list] = {
    1: ["brand", "mpn", "manufacturer_name"],
    2: ["mfr_url", "spec_sheet_url", "manual_url", "installation_url", "sds_url",
        "product_image_url", "warranty_url", "catalog_url", "energy_guide_url"],
    3: [],   # Populated dynamically from specs keys
    4: ["invoice_desc", "short_desc", "long_desc", "mobile_desc", "retail_desc",
        "marketing_description", "item_features", "trade_name", "product_name",
        "standards_approvals"],
    5: ["upc", "ean", "gtin", "unspsc", "warranty", "list_price", "selling_qty",
        "selling_uom", "standard_packaging_info", "length", "length_uom",
        "height", "height_uom", "width", "width_uom", "weight", "weight_uom",
        "volume", "volume_uom", "product_image_url", "spec_sheet_url", "sds_url",
        "manual_url", "installation_url", "warranty_url", "catalog_url",
        "energy_guide_url", "country_of_origin", "discontinued"],
}


def apply_implicit_confidence_boost(
    state: PipelineState, stage_num: int, corrections: dict, reviewer: str
) -> tuple[dict, list]:
    """
    When a human advances a stage without editing any values, boost confidence
    for all fields in that stage's scope by +0.15 (capped at 1.0).
    Records each boost in human_reviews with decision='implicit_accept_stage_N'.
    Returns (updated_state, list_of_boosted_field_names).
    """
    from pipeline.knowledge_store import save_human_review
    specs = state.get("specifications", {})
    scope = _STAGE_FIELD_SCOPE.get(stage_num, [])

    # For stage 3, scope is all spec fields
    if stage_num == 3:
        scope = list(specs.keys())

    changed_keys = set(corrections.keys())
    boosted = []

    for fname in scope:
        if fname in changed_keys:
            continue  # Human explicitly changed this — skip
        if fname not in specs:
            continue

        spec = specs[fname]
        current_conf = (spec.get("confidence", 0.0) if isinstance(spec, dict)
                        else getattr(spec, "confidence", 0.0))
        new_conf = min(1.0, current_conf + 0.15)

        boost_note = (f" | Implicitly accepted by human at Stage {stage_num} "
                      f"review without modification (confidence +0.15).")
        if isinstance(spec, dict):
            specs[fname]["confidence"] = new_conf
            specs[fname]["cause"] = (spec.get("cause", "") or "") + boost_note
        else:
            specs[fname].confidence = new_conf

        pid = state.get("product_id") or state.get("job_id", "")
        save_human_review(
            pid, fname,
            str(current_conf), str(new_conf),
            f"implicit_accept_stage_{stage_num}_{reviewer}"
        )
        boosted.append(fname)

    state["specifications"] = specs
    return state, boosted


def node_desc_infer(state: PipelineState) -> dict:
    """
    Scan the input description for shorthand abbreviations using:
      Phase 1 — Static + DB-learned regex dictionary (desc_abbr_dict.py)
      Phase 2 — LLM fallback for unknown UPPERCASE tokens

    Merges inferred values into extracted_fields only where confidence < 0.8.
    Stores desc_inferred_aliases {abbr → canonical} in state for later DB save.
    """
    from pipeline.desc_abbr_dict import DESC_ABBR_MAP, load_db_abbreviations

    description = state.get("description", "")
    extracted = dict(state.get("extracted_fields", {}))
    logs = state.get("logs", [])

    if not description:
        return {"extracted_fields": extracted, "desc_inferred_aliases": {}, "logs": logs}

    # Merge static + DB-learned patterns
    merged_map = {**DESC_ABBR_MAP, **load_db_abbreviations()}

    inferred: dict[str, dict] = {}
    desc_inferred_aliases: dict[str, str] = {}

    # ── Phase 1: Regex scan ─────────────────────────────────────────────────
    for pattern, meta in merged_map.items():
        try:
            m = re.search(pattern, description, re.IGNORECASE)
        except re.error:
            continue
        if not m:
            continue

        # Resolve capture group placeholders in value template
        canonical_val = meta["value"]
        for i, grp in enumerate(m.groups(), 1):
            if grp:
                canonical_val = canonical_val.replace(f"{{{i}}}", grp)

        fname = meta["field"]
        abbr_label = meta.get("abbr_label", m.group(0))
        # Resolve placeholder in abbr_label too
        for i, grp in enumerate(m.groups(), 1):
            if grp:
                abbr_label = abbr_label.replace(f"{{{i}}}", grp)

        # Only infer if field not already confidently extracted
        existing = extracted.get(fname)
        existing_conf = 0.0
        if existing is not None:
            existing_conf = (existing.get("confidence", 0.0) if isinstance(existing, dict)
                             else getattr(existing, "confidence", 0.0))

        if existing_conf < 0.8:
            inferred[fname] = {
                "value": canonical_val,
                "confidence": 0.65,
                "method": "llm_inferred_from_description",
                "cause": (f"Inferred from abbreviation '{abbr_label}' in product "
                          f"description ({abbr_label} = {canonical_val})"),
                "abbr_source": abbr_label,
                "source_type": "desc_inferred",
            }
            desc_inferred_aliases[abbr_label] = canonical_val

        # Handle companion UOM field
        if "uom_field" in meta and "uom_value" in meta:
            uom_fname = meta["uom_field"]
            uom_existing = extracted.get(uom_fname)
            uom_conf = 0.0
            if uom_existing:
                uom_conf = (uom_existing.get("confidence", 0.0) if isinstance(uom_existing, dict)
                            else getattr(uom_existing, "confidence", 0.0))
            if uom_conf < 0.8:
                inferred[uom_fname] = {
                    "value": meta["uom_value"],
                    "confidence": 0.65,
                    "method": "llm_inferred_from_description",
                    "cause": (f"UOM inferred from '{abbr_label}' abbreviation in description"),
                    "abbr_source": abbr_label,
                    "source_type": "desc_inferred",
                }

    # ── Phase 2: LLM fallback for unknown UPPERCASE tokens ──────────────────
    offline = os.getenv("OFFLINE_DEMO", "false").lower() == "true"
    if not offline:
        # Find unexplained uppercase 2-5 letter tokens
        all_upper = set(re.findall(r'\b[A-Z]{2,5}\b', description))
        known = set(desc_inferred_aliases.keys()) | {
            "MPN", "LED", "USA", "ADA", "GE", "LG", "3M", "LP", "OC",
            "PVC", "NPT", "DKO", "AVI", "NI", "BN", "CH", "SS", "BK", "WH",
        }
        unknown_tokens = [t for t in all_upper if t not in known]

        if unknown_tokens:
            prompt = (
                f'Product description: "{description}"\n'
                f"Unknown shorthand codes found: {unknown_tokens}\n"
                "For each code that represents a product attribute (material, color, size, "
                "voltage, finish, etc.), return JSON:\n"
                '{"results": [{"abbreviation": "XX", "field_name": "field", '
                '"canonical_value": "value", "reason": "..."}]}\n'
                "Return empty results array if none apply. "
                "Only return real industrial/product attributes."
            )
            try:
                resp = generate_with_retry(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                parsed = parse_json_response(resp)
                for item in parsed.get("results", []):
                    fname = item.get("field_name", "")
                    abbr = item.get("abbreviation", "")
                    cval = item.get("canonical_value", "")
                    if fname and abbr and cval:
                        existing_conf = 0.0
                        ex = extracted.get(fname)
                        if ex:
                            existing_conf = (ex.get("confidence", 0.0) if isinstance(ex, dict)
                                            else getattr(ex, "confidence", 0.0))
                        if existing_conf < 0.8:
                            inferred[fname] = {
                                "value": cval,
                                "confidence": 0.55,
                                "method": "llm_inferred_from_description",
                                "cause": (f"LLM inferred: '{abbr}' in description → {cval}. "
                                          f"{item.get('reason', '')}"),
                                "abbr_source": abbr,
                                "source_type": "desc_inferred",
                            }
                            desc_inferred_aliases[abbr] = cval
            except Exception as e:
                logger.warning("[DescInfer] LLM fallback failed: %s", e)

    # Merge inferred into extracted_fields (only where conf < 0.8)
    for fname, fdata in inferred.items():
        existing = extracted.get(fname)
        existing_conf = 0.0
        if existing:
            existing_conf = (existing.get("confidence", 0.0) if isinstance(existing, dict)
                            else getattr(existing, "confidence", 0.0))
        if existing_conf < 0.8:
            extracted[fname] = fdata

    inferred_count = len([f for f in inferred if f in extracted])
    logger.info("[DescInfer] %d fields inferred from %d abbreviations",
                inferred_count, len(desc_inferred_aliases))

    return {
        "extracted_fields": extracted,
        "desc_inferred_aliases": desc_inferred_aliases,
        "logs": logs + [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "desc_infer",
            "message": (
                f"Description inference: {inferred_count} fields inferred from "
                f"{len(desc_inferred_aliases)} abbreviations "
                f"({', '.join(list(desc_inferred_aliases.keys())[:5])}{'...' if len(desc_inferred_aliases) > 5 else ''})"
            )
        }]
    }


# ---------------------------------------------------------------------------
# NODE: Post-Approval Persistence Agent
# ---------------------------------------------------------------------------

def node_post_approval_persist(state: PipelineState, reviewer: str = "human") -> dict:
    """
    Runs automatically after Stage 5 human accepts the final product.
    Persists all learning artifacts:
      1. Abbreviation aliases → attribute_aliases + desc_abbreviations tables
      2. Series-shared attrs  → series_knowledge (confidence = 1.0)
      3. Unique product attrs → product_attributes table + knowledge graph
      4. Increment metrics
    Returns post_approval_summary dict for the Final Product Response view.
    """
    from pipeline.knowledge_store import (
        save_attribute_alias, save_desc_abbreviation,
        save_product_attribute, boost_series_attribute_confidence,
        save_series_knowledge, increment_metric
    )
    from pipeline.extractor import is_series_shared
    from pipeline.knowledge_graph import ingest_validated_product

    brand = state.get("brand", "")
    mpn = state.get("mpn", "")
    category = state.get("category", "")
    specs = state.get("specifications", {})
    desc_aliases = state.get("desc_inferred_aliases", {})

    # Resolve series
    series = state.get("series") or None
    series_spec = specs.get("series")
    if not series and series_spec:
        series = (series_spec.get("value") if isinstance(series_spec, dict)
                  else getattr(series_spec, "value", None))

    aliases_saved = 0
    series_boosted = 0
    unique_saved = 0

    # ── Step 1: Abbreviation aliases ────────────────────────────────────────
    for abbr, canonical in desc_aliases.items():
        try:
            save_attribute_alias(abbr, canonical)
            save_desc_abbreviation(abbr, canonical, "")
            aliases_saved += 1
        except Exception as e:
            logger.warning("[PostApproval] Failed to save alias %s→%s: %s", abbr, canonical, e)

    # ── Step 2 + 3: Series boost & unique attribute storage ─────────────────
    for fname, fval_obj in specs.items():
        val = (fval_obj.get("value") if isinstance(fval_obj, dict)
               else getattr(fval_obj, "value", None))
        conf = (fval_obj.get("confidence", 0.0) if isinstance(fval_obj, dict)
                else getattr(fval_obj, "confidence", 0.0))
        if val is None:
            continue

        try:
            if series and is_series_shared(fname):
                boost_series_attribute_confidence(brand, series, fname, str(val))
                series_boosted += 1
            else:
                save_product_attribute(brand, mpn, fname, str(val), conf,
                                       "human_verified", reviewer)
                unique_saved += 1
        except Exception as e:
            logger.warning("[PostApproval] Failed to persist %s: %s", fname, e)

    # Ingest full validated product into knowledge graph
    try:
        ingest_validated_product(brand, mpn, category, specs)
    except Exception as e:
        logger.warning("[PostApproval] KG ingest failed: %s", e)

    # ── Step 4: Metrics ──────────────────────────────────────────────────────
    try:
        increment_metric("human_approvals", 1)
        if aliases_saved:
            increment_metric("aliases_learned", aliases_saved)
    except Exception as e:
        logger.warning("[PostApproval] Metrics update failed: %s", e)

    summary = {
        "aliases_saved": aliases_saved,
        "series_boosted": series_boosted,
        "unique_attrs_saved": unique_saved,
        "reviewer": reviewer,
    }
    logger.info("[PostApproval] Complete: aliases=%d series=%d unique=%d",
                aliases_saved, series_boosted, unique_saved)

    return {
        "post_approval_summary": summary,
        "status": "complete",
        "logs": state.get("logs", []) + [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "post_approval_persist",
            "message": (
                f"Post-approval learning: {aliases_saved} aliases saved, "
                f"{series_boosted} series attrs boosted, "
                f"{unique_saved} unique attrs stored."
            )
        }]
    }
