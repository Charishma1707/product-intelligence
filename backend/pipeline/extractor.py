"""
pipeline/extractor.py — Stage 3: Batched LLM Extraction.

KEY CHANGES:
1. Dedicated SERIES extraction pass first (most important attribute).
2. Category-attribute-aware extraction using the ordered field list.
3. Full digital asset and part number capture.
4. All extraction from manufacturer sources first, then supplemented.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from pydantic import BaseModel, Field

from pipeline.utils import generate_with_retry, parse_json_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attribute Classification: Series-Shared vs Variant-Specific
# ---------------------------------------------------------------------------

VARIANT_SPECIFIC_FIELDS = {
    "grit", "diameter", "disc_size", "inner_diameter", "outer_diameter", 
    "width", "length", "height", "depth", "weight", "volume", 
    "cable_length", "sensing_distance", "bore_diameter",
    "coil_voltage", "rated_current", "rated_voltage", "power_rating", 
    "operating_voltage", "switching_frequency", "breaking_capacity",
    "quantity", "selling_qty", "selling_uom", "list_price", 
    "upc", "ean", "gtin", "part_number", "mpn", "alternate_part_number", 
    "model", "sku", "sku_my_part_number"
}

SERIES_SHARED_FIELDS = {
    "series", "trade_name", "backing_material", "backing_type", 
    "abrasive_technology", "abrasive_material", "grain_type", 
    "housing_material", "material", "enclosure_type", "ip_rating", 
    "shielded_unshielded", "mounting_type", "connection_type", 
    "housing_shape", "contact_configuration", "operating_temperature_range", 
    "operating_temperature", "certifications", "standards_approvals", 
    "prop_65", "warranty", "country_of_origin", "utilization_category", 
    "sensor_type", "output_type", "type_of_bearing", "type_of_lubrication"
}

def is_variant_specific(field_name: str) -> bool:
    """Return True if an attribute is variant-specific and must NOT be blindly inherited from series."""
    f = field_name.lower().strip()
    if f in VARIANT_SPECIFIC_FIELDS:
        return True
    if any(k in f for k in ("diameter", "width", "length", "height", "voltage", "current", "grit", "size", "rpm", "kn", "qty", "price")):
        return True
    return False

def is_series_shared(field_name: str) -> bool:
    """Return True if an attribute is shared across all products in the same series."""
    f = field_name.lower().strip()
    if f in SERIES_SHARED_FIELDS:
        return True
    if any(k in f for k in ("material", "rating", "approval", "temp", "type", "warranty", "origin", "enclosure", "backing", "technology")):
        return True
    return not is_variant_specific(field_name)


# ---------------------------------------------------------------------------
# ChromaDB attribute-specific RAG helper
# ---------------------------------------------------------------------------

def _query_chroma_for_attribute(product_id: str, field_name: str, top_k: int = 2, require_mpn_verified: bool = False) -> list[dict]:
    """
    Query ChromaDB semantically for chunks most relevant to a specific field.
    Returns top_k chunks as dicts with 'text', 'url', 'source_type', 'is_mfr_domain', 'mpn_verified'.
    """
    try:
        from pipeline.retriever import _collection
        if not _collection:
            return []
        query_text = f"What is the {field_name.replace('_', ' ')} specification?"
        
        # If variant specific, filter or prioritize mpn_verified chunks
        where_filter = {"product_id": product_id}
        if require_mpn_verified:
            where_filter["mpn_verified"] = True
            
        try:
            results = _collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where_filter,
            )
        except Exception:
            # Fallback without mpn_verified filter if empty
            results = _collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where={"product_id": product_id},
            )
            
        chunks = []
        if results and results.get("ids") and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                doc = results["documents"][0][i] if results["documents"] else ""
                chunks.append({
                    "text": doc,
                    "url": meta.get("url", ""),
                    "source_type": meta.get("source_type", "webpage_text"),
                    "is_mfr_domain": meta.get("is_mfr_domain", False),
                    "mpn_verified": meta.get("mpn_verified", False),
                    "source_tier": meta.get("source_tier", 3),
                })
        return chunks
    except Exception as e:
        logger.debug("[RAG] Chroma query failed for '%s': %s", field_name, e)
        return []


def _extract_field_with_rag(
    brand: str, mpn: str, description: str, category: str,
    field_name: str, product_id: str, fallback_chunks: list[dict]
) -> dict | None:
    """
    Extract a single field using attribute-specific RAG.
    1. Query Chroma for top-2 most relevant chunks for this field.
    2. Fall back to first 2 fallback_chunks if Chroma returns nothing.
    3. Run a tiny, focused LLM prompt (fits in Groq 8k context).
    Returns {"value": ..., "snippet": ..., "url": ..., "source": "mfr"|"ref"|"inferred"}.
    """
    is_variant = is_variant_specific(field_name)
    
    # Get attribute-relevant chunks (require mpn_verified for variant fields if possible)
    rag_chunks = _query_chroma_for_attribute(product_id, field_name, top_k=2, require_mpn_verified=is_variant)
    if not rag_chunks:
        # Sort fallback chunks by tier and MPN verification
        sorted_fb = sorted(
            fallback_chunks,
            key=lambda c: (
                0 if (c.get("is_mfr_domain") and c.get("mpn_verified")) else
                1 if c.get("is_mfr_domain") else
                2 if c.get("mpn_verified") else 3
            )
        )
        rag_chunks = sorted_fb[:2]

    if not rag_chunks:
        return None

    # Build a tiny focused context
    context_parts = []
    for i, c in enumerate(rag_chunks):
        text = (c.get("text") or "")[:1500]
        url = c.get("url", "")
        mfr = "★MFR" if c.get("is_mfr_domain") else ""
        ver = "✓MPN-VERIFIED" if c.get("mpn_verified") else ""
        context_parts.append(f"[SOURCE {i+1} {mfr} {ver} {url}]\n{text}")
    context = "\n\n---\n\n".join(context_parts)

    readable = field_name.replace("_", " ").title()
    constraint_note = (
        f"IMPORTANT: '{readable}' is a VARIANT-SPECIFIC attribute. It MUST apply directly to MPN '{mpn}'. "
        f"Do not confuse with sibling products or other size variants."
        if is_variant else
        f"NOTE: '{readable}' is a SERIES-LEVEL attribute. It can apply to the product line/series if mentioned."
    )

    prompt = f"""Product: {brand} {mpn}
Category: {category}
Description: {description}

{constraint_note}

Documentation excerpts:
{context}

TASK: Find the '{readable}' for this exact product.
- Return the value ONLY if explicitly stated in the documentation above.
- Include the exact verbatim quote as 'snippet' and the source URL.
- If not found, return null for value.
- Never hallucinate or guess.

Return JSON only: {{"value": "...", "snippet": "...", "url": "..."}}"""

    try:
        raw = generate_with_retry(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.05,
        )
        data = parse_json_response(raw)
        val = data.get("value")
        if val is not None and str(val).strip() not in ("", "null", "None", "N/A"):
            from pipeline.knowledge_store import get_canonical_attribute_value
            canonical = get_canonical_attribute_value(str(val))
            if canonical:
                logger.info("[Extractor] Alias hit for field '%s': '%s' -> '%s'", field_name, val, canonical)
                val = canonical
            return {
                "value": val,
                "snippet": data.get("snippet"),
                "url": data.get("url") or (rag_chunks[0].get("url") if rag_chunks else None),
                "is_mfr": any(c.get("is_mfr_domain") for c in rag_chunks),
                "mpn_verified": any(c.get("mpn_verified") for c in rag_chunks),
                "source_tier": min((c.get("source_tier", 3) for c in rag_chunks), default=3),
            }
    except Exception as e:
        logger.debug("[RAG] Field '%s' extraction failed: %s", field_name, e)
    return None

_SYSTEM_PROMPT = (
    "You are a precise data extraction AI for industrial B2B and consumer products. "
    "Extract structured product specifications from the provided documentation. "
    "Output only valid JSON. Never hallucinate or invent values. "
    "If a value is not found in the documentation, set it to null."
)


class ExtractedField(BaseModel):
    value: str | float | int | bool | None = None
    source_type: str = "none"
    url: str | None = None
    doc_id: str | None = None
    doc_name: str | None = None
    page_number: int | None = None
    snippet: str | None = None
    table_location: str | None = None
    chart_description: str | None = None
    similar_products_used: list[str] | None = None


# ---------------------------------------------------------------------------
# Dedicated SERIES extraction — always runs first
# ---------------------------------------------------------------------------

def _extract_series(
    brand: str, mpn: str, description: str, category: str, chunks: list[dict]
) -> str | None:
    """
    Dedicated first pass to extract the product Series/Line name.
    This populates ATTRIBUTE_LABEL 1 = "Series" / ATTRIBUTE_VALUE 1.

    Examples: "Professional Series", "Eco Series", "Cubitron II",
              "775L", "Steel Demon", "Speed Demon", "Diablo"
    """
    # Try extracting from description first (fast, no API)
    series_from_desc = _guess_series_from_description(brand, mpn, description)
    if series_from_desc:
        logger.info("[Extractor] Series from description: %s", series_from_desc)
        return series_from_desc

    if not chunks:
        return None

    combined_text = _build_context_text(chunks, max_chars=3000)
    if not combined_text.strip():
        return None

    prompt = f"""Product: {brand} {mpn}
Category: {category}
Description: {description}

Documentation:
---
{combined_text}
---

TASK: What is the PRODUCT SERIES or PRODUCT LINE NAME for this product?
- The series name identifies a product family/range within the brand.
- Examples: "Professional Series", "Eco Series", "Cubitron II", "Steel Demon",
  "775L", "Speed Demon", "Diablo", "HIOLIT", "Abranet"
- Look for: series name, product line, product family.
- Do NOT use the brand name itself (e.g. not "3M" or "Freud").
- Do NOT use the MPN.
- If you cannot find a series name, return null.

Return JSON only:
{{"series": "<series name or null>"}}"""

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    task_type = "pdf" if _detect_source_type(chunks).startswith("pdf") else "normal"
    try:
        raw = generate_with_retry(messages=messages, response_format={"type": "json_object"}, temperature=0.05, task_type=task_type)
        data = parse_json_response(raw)
        val = data.get("series")
        if val and str(val).strip() not in ("null", "None", "", "N/A"):
            logger.info("[Extractor] Series extracted by LLM: %s", val)
            return str(val).strip()
    except Exception as e:
        logger.warning("[Extractor] Series extraction failed: %s", e)
    return None


def _guess_series_from_description(brand: str, mpn: str, description: str) -> str | None:
    """
    Fast heuristic: extract series name from the description string itself.
    e.g. "DCB518ASTS06G Diablo 1/2\"x18\" - Sanding Belt 6pc" → "Diablo"
    e.g. "3M 775L Stikit Film P150 - Cubitron II 50 Disc/Box" → "Cubitron II"
    e.g. "PDSH4816AF Dishwasher SS - Professional Series" → "Professional Series"
    """
    desc = description.strip()

    # Check for known series keywords in description
    known_series_patterns = [
        # Abrasives
        r"\bCubitron\s+II\b",
        r"\bCubitron\b",
        r"\bStikit\b",
        r"\bHIOLIT\b",
        r"\bAbranet\b",
        r"\bAbraflex\b",
        r"\bNorax\b",
        r"\bGold\s+Film\b",
        r"\bBlue\s+Fire\b",
        r"\bRed\s+Heat\b",
        r"\bRapidfire\b",
        r"\bSpeed\s+Demon\b",
        r"\bSteel\s+Demon\b",
        r"\bDiablo\b",
        r"\bFreeStyle\b",
        # Appliances
        r"\bProfessional\s+Series\b",
        r"\bEco\s+Series\b",
        r"\bGallery\s+Series\b",
        r"\bElite\s+Series\b",
        r"\bClassic\s+Series\b",
        r"\bPlatinum\s+Series\b",
        r"\bDiamond\s+Series\b",
        r"\bSignature\s+Series\b",
        r"\bCommercial\s+Series\b",
        # Faucets
        r"\bBrantford\b",
        r"\bKingsley\b",
        r"\bBanbury\b",
        r"\bAdler\b",
        r"\bArbor\b",
        r"\bAllen\b",
        r"\bGlenshire\b",
        r"\bGranite\b",
        r"\bSpot\s+Resist\b",
    ]

    import re
    for pat in known_series_patterns:
        m = re.search(pat, desc, re.IGNORECASE)
        if m:
            return m.group(0).strip()

    # Pattern: "<MPN> <SeriesName> <ProductType>" — extract second token after MPN
    # e.g. "DCB518ASTS06G Diablo 1/2..."
    mpn_escaped = re.escape(mpn)
    m = re.match(rf"^{mpn_escaped}\s+([A-Za-z][A-Za-z0-9\s\-]+?)\s+[\d\"']", desc)
    if m:
        candidate = m.group(1).strip()
        # Must be 1-3 words, not just filler
        if 1 <= len(candidate.split()) <= 3 and not candidate.lower() in ("the", "a", "an"):
            return candidate

    # Pattern: Model number like "775L" at start of desc after brand
    # e.g. "3M 775L Stikit Film..."
    m = re.match(r"^(?:\S+\s+)?(\d{2,4}[A-Z]{0,3})\s+", desc)
    if m:
        candidate = m.group(1).strip()
        if candidate != mpn and len(candidate) <= 8:
            return candidate

    return None


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context_text(chunks: list[dict], max_chars: int = 6000) -> str:
    """Combine chunk texts into a single context string, prioritizing mfr domain chunks."""
    # Sort: manufacturer domain chunks first
    sorted_chunks = sorted(chunks, key=lambda c: (0 if c.get("is_mfr_domain") else 1))

    seen_urls: set[str] = set()
    sections: list[str] = []
    total_chars = 0

    for i, chunk in enumerate(sorted_chunks):
        text = chunk.get("text", "").strip()
        if not text or total_chars >= max_chars:
            break
        url = chunk.get("url", "")
        stype = chunk.get("source_type", "text")
        mfr_flag = "★MFR" if chunk.get("is_mfr_domain") else ""
        header = f"[SOURCE {i+1}: {stype} {mfr_flag} — {url or 'local'}]"
        section = f"{header}\n{text[:2000]}"
        sections.append(section)
        total_chars += len(section)
        if url and url not in seen_urls:
            seen_urls.add(url)

    return "\n\n---\n\n".join(sections) if sections else ""


# ---------------------------------------------------------------------------
# Main extraction prompt
# ---------------------------------------------------------------------------

def _build_batched_prompt(
    brand: str, mpn: str, description: str, category: str, subcategory: str,
    expected_fields: list[str], chunks: list[dict]
) -> str:
    """
    Build a comprehensive prompt combining ALL document chunks.
    Fields are provided in the correct Unilog order.
    """
    combined_context = _build_context_text(chunks, max_chars=7000)

    # Convert snake_case fields to readable labels for the prompt
    readable_fields = []
    for f in expected_fields:
        label = f.replace("_", " ").title()
        readable_fields.append(label)

    return f"""Product to enrich:
  Brand: {brand}
  MPN: {mpn}
  Description: {description}
  Category: {category}
  Subcategory: {subcategory}

FIELDS TO EXTRACT (in this exact order — this becomes the output attribute order):
{json.dumps(readable_fields, indent=2)}

PRODUCT DOCUMENTATION (★MFR = from manufacturer's own website — prioritize these):
{combined_context if combined_context else "(No documents retrieved — use domain knowledge conservatively)"}

EXTRACTION RULES:
1. For EVERY field, extract the value if found ANYWHERE in documentation.
2. If found: provide value AND exact verbatim quote as "snippet" AND source URL.
3. If NOT found in docs: use domain knowledge ONLY for well-known specs; otherwise null.
4. NEVER hallucinate or invent values.
5. For numeric values, include the unit (e.g. "120 V", "15 A", "47 dBA", "24 in").
6. For "Series": the product line/family name (e.g. "Professional Series", "Cubitron II").
7. For UOM fields: use standard abbreviations (V, A, W, in, mm, kg, lb, dBA).
8. The "Series" field MUST be populated if at all possible — check product name, title, series field.
9. For dimensions: use format "X in W x Y in D" or just the number + unit.

Return a SINGLE JSON object where every key is the snake_case field name:
{{
  "series": {{"value": "...", "snippet": "...", "url": "..."}},
  "model": {{"value": "...", "snippet": "...", "url": "..."}},
  ...all other fields in the same format...
}}"""


# ---------------------------------------------------------------------------
# Targeted document re-search for missing fields
# ---------------------------------------------------------------------------

def _targeted_extraction(
    brand: str, mpn: str, description: str, category: str,
    missing_fields: list[str], chunks: list[dict]
) -> dict[str, dict]:
    """Targeted second pass scanning the documents specifically for still-missing fields."""
    if not missing_fields or not chunks:
        return {}

    combined_context = _build_context_text(chunks, max_chars=7000)
    
    prompt = f"""Product: {brand} {mpn}
Category: {category}
Description: {description}

The following fields were missed in the initial extraction pass. 
Specifically look for these missing attributes in the document:
{json.dumps(missing_fields, indent=2)}

Documentation:
---
{combined_context}
---

TASK: Perform a highly targeted search for ONLY these missing fields.
- If found, provide the value and the exact verbatim snippet.
- If truly not mentioned in the documentation, return null.
- Do NOT guess or invent values here; this is strict document extraction.

Return JSON:
{{
  "field_name": {{"value": "...", "snippet": "..."}}
}}"""

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    task_type = "pdf" if _detect_source_type(chunks).startswith("pdf") else "normal"
    try:
        raw = generate_with_retry(messages=messages, response_format={"type": "json_object"}, temperature=0.1, task_type=task_type)
        return parse_json_response(raw)
    except Exception as e:
        logger.warning("[Extractor] Targeted extraction failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Inference for missing fields
# ---------------------------------------------------------------------------

def _infer_missing_fields(
    brand: str, mpn: str, description: str, category: str,
    missing_fields: list[str]
) -> dict[str, dict]:
    """Single LLM call to infer remaining missing fields using domain knowledge."""
    if not missing_fields:
        return {}

    graph_context = ""
    try:
        from pipeline.knowledge_graph import query_related_specs
        graph_context = query_related_specs(category)
    except Exception:
        pass

    prompt = f"""Product: {brand} {mpn}
Category: {category}
Description: {description}
Fields still missing: {json.dumps(missing_fields)}

Knowledge from similar products:
{graph_context or '(none available)'}

TASK: For each missing field, infer the most likely value based on category knowledge.
- Be conservative: only infer if highly confident.
- Set value to null if truly unknown.
- For "series": extract from MPN patterns or description tokens.

Return JSON:
{{
  "field_name": {{
    "value": "inferred value or null",
    "similar_products_used": ["MPN1"]
  }}
}}"""

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    raw = generate_with_retry(messages=messages, response_format={"type": "json_object"}, temperature=0.3)
    return parse_json_response(raw)


# ---------------------------------------------------------------------------
# Part number & commercial field extraction
# ---------------------------------------------------------------------------

def _extract_commercial_fields(
    brand: str, mpn: str, description: str, chunks: list[dict]
) -> dict[str, dict]:
    """Extract UPC, EAN, GTIN, list price, selling qty, country of origin, etc."""
    combined_text = _build_context_text(chunks, max_chars=4000)
    if not combined_text.strip():
        return {}

    prompt = f"""Product: {brand} {mpn}
Description: {description}

Documentation:
---
{combined_text}
---

TASK: Extract these commercial/compliance fields if present:
- upc: UPC barcode (12 digits)
- ean: EAN barcode (13 digits)
- gtin: GTIN (14 digits)
- list_price: manufacturer suggested retail price
- selling_qty: quantity sold per unit (e.g. "1", "6", "50")
- selling_uom: unit of measure (EA, BX, PK, BG, etc.)
- country_of_origin: country where manufactured
- warranty: full warranty description
- prop_65: "Yes" if California Prop 65 warning applies, else "No" or null
- standards_approvals: pipe-separated list of certifications (UL Listed|ENERGY STAR|etc.)
- alternate_part_number: any alternate or cross-reference part number

Return JSON: {{"field_name": {{"value": "...", "snippet": "..."}}}}
Set value to null for any not found."""

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    task_type = "pdf" if _detect_source_type(chunks).startswith("pdf") else "normal"
    try:
        raw = generate_with_retry(messages=messages, response_format={"type": "json_object"}, temperature=0.05, task_type=task_type)
        return parse_json_response(raw)
    except Exception as e:
        logger.warning("[Extractor] Commercial field extraction failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Bonus attributes pass
# ---------------------------------------------------------------------------

def _extract_bonus_fields(
    brand: str, mpn: str, description: str, category: str,
    already_captured: list[str], chunks: list[dict]
) -> dict[str, dict]:
    """Second-pass scan for additional ecommerce attributes not in the original field list."""
    combined_text = "\n\n".join(
        chunk.get("text", "")[:600] for chunk in chunks[:4] if chunk.get("text")
    )[:3000]

    if not combined_text.strip():
        return {}

    already_str = ", ".join(already_captured[:30])
    prompt = f"""Product: {brand} {mpn} | Category: {category}
Already captured (DO NOT repeat): [{already_str}]

Document text:
---
{combined_text}
---

TASK: Find ANY additional product attributes not already captured useful for an ecommerce catalog.
Look for: certifications, color, finish, material, energy ratings, connectivity, compatibility,
special functions, included accessories, UNSPSC, product weight class, fragile flag.
Only return attributes actually present in the text. Return {{}} if nothing new.

Return JSON: {{"attribute_name": {{"value": "...", "snippet": "..."}}}}"""

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    task_type = "pdf" if _detect_source_type(chunks).startswith("pdf") else "normal"
    try:
        raw = generate_with_retry(messages=messages, response_format={"type": "json_object"}, temperature=0.1, task_type=task_type)
        return parse_json_response(raw)
    except Exception as e:
        logger.warning("[Extractor] Bonus extraction failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Main extract function
# ---------------------------------------------------------------------------

def extract(
    brand: str, mpn: str, description: str, category: str,
    expected_fields: list[str], chunks: list[dict],
    subcategory: str = "",
) -> dict[str, ExtractedField]:
    """
    Stage 3: Extract all spec fields using targeted LLM calls.

    Pass 0: Dedicated Series extraction (description heuristic + LLM)
    Pass 1: Batched extraction of all category fields
    Pass 2: Inference for still-missing fields
    Pass 3: Commercial fields (UPC, EAN, warranty, etc.)
    Pass 4: Bonus attributes discovery
    """
    results: dict[str, ExtractedField] = {f: ExtractedField() for f in expected_fields}

    first_url = chunks[0].get("url") if chunks else None
    first_mfr_chunk = next((c for c in chunks if c.get("is_mfr_domain")), chunks[0] if chunks else None)

    # ── Pass 0: Dedicated Series extraction ─────────────────────────────────
    series_val = _extract_series(brand, mpn, description, category, chunks)
    if series_val:
        ef = ExtractedField()
        ef.value = series_val
        ef.source_type = "webpage_text"
        ef.url = first_mfr_chunk.get("url") if first_mfr_chunk else first_url
        results["series"] = ef
        logger.info("[Extractor] Series locked: %s", series_val)

    if not chunks:
        logger.warning("[Extractor] No chunks available — skipping to inference")
    else:
        # ─────────────────────────────────────────────────────────────────────
        # Pass 1: ATTRIBUTE-SPECIFIC RAG (replaces monolithic batch)
        #
        # For each field, we query ChromaDB for only the 2 most relevant
        # chunks for that specific attribute, then run a tiny focused LLM
        # prompt. This keeps every call well within the 8k context window
        # of Groq's fast tier and avoids the 400/context-overflow errors.
        # ─────────────────────────────────────────────────────────────────────
        product_id = f"{brand.strip().lower()}_{mpn.strip().lower()}"
        fields_to_extract = [f for f in expected_fields if f != "series" or not results.get("series") or results["series"].value is None]

        logger.info("[Extractor] Starting attribute-specific RAG for %d fields", len(fields_to_extract))

        conflict_log: dict[str, list[str]] = {}  # field → list of different values seen

        from pipeline.knowledge_store import get_series_knowledge, save_series_knowledge
        
        series_knowledge = {}
        if results.get("series") and results["series"].value:
            sk_list = get_series_knowledge(brand, str(results["series"].value))
            for sk in sk_list:
                series_knowledge[sk["attribute"]] = sk

        for field_name in fields_to_extract:
            # ── 1. Check Series Knowledge Cache (ONLY for shared attributes) ──
            if field_name in series_knowledge and is_series_shared(field_name):
                sk = series_knowledge[field_name]
                if sk.get("scope", "series") == "series":
                    ef = results.get(field_name, ExtractedField())
                    ef.value = sk["value"]
                    ef.source_type = sk.get("source") or "series_knowledge"
                    results[field_name] = ef
                    logger.info("[Extractor] Shared field '%s' inherited from series knowledge: %s", field_name, sk["value"])
                    continue

            # ── 2. Run Attribute-Specific RAG ──
            extracted = _extract_field_with_rag(
                brand, mpn, description, category,
                field_name, product_id, chunks
            )
            if extracted:
                prev = results.get(field_name)
                new_val = str(extracted["value"]).strip()

                # Conflict detection: if we already have a value from a different source
                if prev and prev.value is not None:
                    old_val = str(prev.value).strip()
                    if old_val.lower() != new_val.lower():
                        # Record conflict
                        conflict_log.setdefault(field_name, [old_val]).append(new_val)
                        logger.warning("[Extractor] CONFLICT on '%s': '%s' vs '%s'",
                                       field_name, old_val, new_val)
                        # Keep the manufacturer-sourced value
                        if extracted.get("is_mfr") and not prev.source_type.startswith("mfr"):
                            pass  # fall through to overwrite with mfr value
                        else:
                            continue  # keep existing value

                ef = results.get(field_name, ExtractedField())
                ef.value = extracted["value"]
                ef.source_type = "mfr_webpage" if extracted.get("is_mfr") else _detect_source_type(chunks)
                ef.url = extracted.get("url")
                ef.snippet = extracted.get("snippet")
                results[field_name] = ef
                
                # Save to series knowledge: only mark scope='series' if it's truly a shared attribute
                if extracted.get("is_mfr") and results.get("series") and results["series"].value:
                    attr_scope = "series" if is_series_shared(field_name) else "variant"
                    save_series_knowledge(
                        brand, str(results["series"].value), field_name, new_val, 
                        scope=attr_scope, confidence=0.9, source="mfr_webpage"
                    )

        if conflict_log:
            logger.info("[Extractor] Conflicts detected in %d fields: %s",
                        len(conflict_log), list(conflict_log.keys()))

    # ── Pass 1.5: Targeted document re-search for still-missing fields ──────
    missing_after_batch = [f for f, r in results.items() if r.value is None]
    if missing_after_batch and chunks:
        logger.info("[Extractor] Running targeted document re-search for %d missing fields", len(missing_after_batch))
        targeted = _targeted_extraction(brand, mpn, description, category, missing_after_batch, chunks)
        for fname in missing_after_batch:
            if fname in targeted:
                fdata = targeted[fname]
                val = fdata.get("value") if isinstance(fdata, dict) else fdata
                if val is not None and str(val).strip() not in ("null", "None", "", "N/A"):
                    results[fname].value = val
                    results[fname].source_type = _detect_source_type(chunks)
                    results[fname].url = first_url
                    if isinstance(fdata, dict):
                        results[fname].snippet = fdata.get("snippet")

    # ── Pass 2: Inference for still-missing fields ───────────────────────────
    still_missing = [f for f, r in results.items() if r.value is None]
    if still_missing:
        logger.info("[Extractor] Inferring %d missing fields", len(still_missing))
        try:
            inferred = _infer_missing_fields(brand, mpn, description, category, still_missing)
            for fname in still_missing:
                if fname in inferred:
                    iv = inferred[fname]
                    val = iv.get("value") if isinstance(iv, dict) else iv
                    if val is not None and str(val).strip() not in ("null", "None", "", "N/A"):
                        results[fname].value = val
                        results[fname].source_type = "inferred"
                        if isinstance(iv, dict):
                            results[fname].similar_products_used = iv.get("similar_products_used", [])
        except Exception as e:
            logger.warning("[Extractor] Inference pass failed: %s", e)

    # ── Pass 3: Commercial fields ─────────────────────────────────────────────
    commercial_fields = [
        "upc", "ean", "gtin", "list_price", "selling_qty", "selling_uom",
        "country_of_origin", "warranty", "prop_65", "standards_approvals",
        "alternate_part_number",
    ]
    missing_commercial = [f for f in commercial_fields if not results.get(f) or results[f].value is None]
    if missing_commercial and chunks:
        try:
            commercial = _extract_commercial_fields(brand, mpn, description, chunks)
            for fname, fdata in commercial.items():
                if fname in results and results[fname].value is not None:
                    continue  # Don't overwrite already-found values
                val = fdata.get("value") if isinstance(fdata, dict) else fdata
                if val and str(val).strip() not in ("null", "None", "", "N/A"):
                    ef = results.get(fname, ExtractedField())
                    ef.value = val
                    ef.source_type = _detect_source_type(chunks)
                    ef.snippet = fdata.get("snippet") if isinstance(fdata, dict) else None
                    ef.url = first_url
                    results[fname] = ef
            logger.info("[Extractor] Commercial pass done")
        except Exception as e:
            logger.warning("[Extractor] Commercial pass failed: %s", e)

    # ── Pass 4: Bonus attributes discovery ───────────────────────────────────
    if chunks:
        already = [f for f, r in results.items() if r.value is not None]
        try:
            bonus = _extract_bonus_fields(brand, mpn, description, category, already + list(results.keys()), chunks)
            added = 0
            for attr_name, attr_data in bonus.items():
                if attr_name in results:
                    continue
                val = attr_data.get("value") if isinstance(attr_data, dict) else attr_data
                if val and str(val).strip() not in ("", "null", "None"):
                    ef = ExtractedField()
                    ef.value = val
                    ef.source_type = _detect_source_type(chunks)
                    ef.snippet = attr_data.get("snippet") if isinstance(attr_data, dict) else None
                    ef.url = first_url
                    if first_mfr_chunk:
                        ef.doc_id = first_mfr_chunk.get("doc_id")
                    results[attr_name] = ef
                    added += 1
            logger.info("[Extractor] Bonus pass discovered %d extra attributes", added)
        except Exception as e:
            logger.warning("[Extractor] Bonus pass failed: %s", e)

    extracted_count = sum(1 for r in results.values() if r.value is not None)
    logger.info("[Extractor] Done: %d/%d fields populated", extracted_count, len(expected_fields))
    return results


def _detect_source_type(chunks: list[dict]) -> str:
    """Detect predominant source type from chunks."""
    for c in chunks:
        st = c.get("source_type", "")
        if st in ("pdf_text", "pdf_table", "pdf_chart"):
            return st
    return "webpage_text"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n[PASS] extractor.py syntax check passed.")
