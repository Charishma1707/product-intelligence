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
from pipeline.taxonomy import get_category_attributes

logger = logging.getLogger(__name__)

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
        # ── Pass 1: Single batched LLM call for all category fields ──────────
        prompt = _build_batched_prompt(
            brand, mpn, description, category, subcategory, expected_fields, chunks
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        logger.info("[Extractor] Sending batched extraction for %d fields across %d chunks",
                    len(expected_fields), len(chunks))

        task_type = "pdf" if _detect_source_type(chunks).startswith("pdf") else "normal"
        try:
            raw = generate_with_retry(messages=messages, response_format={"type": "json_object"}, temperature=0.1, task_type=task_type)
            data = parse_json_response(raw)

            for fname in expected_fields:
                # Skip series if already set from Pass 0
                if fname == "series" and results.get("series") and results["series"].value:
                    continue

                # Try both snake_case and label versions
                fdata = data.get(fname) or data.get(fname.replace("_", " ").title())
                if not fdata:
                    # Also try lowercase title
                    fdata = data.get(fname.replace("_", " ").lower())

                if isinstance(fdata, dict):
                    val = fdata.get("value")
                    if val is not None and str(val).strip() not in ("", "null", "None", "N/A"):
                        results[fname].value = val
                        results[fname].source_type = _detect_source_type(chunks)
                        results[fname].url = fdata.get("url") or first_url
                        results[fname].snippet = fdata.get("snippet")
                        # Assign doc metadata
                        url = fdata.get("url") or first_url
                        matching = next(
                            (c for c in chunks if c.get("url") == url),
                            first_mfr_chunk or (chunks[0] if chunks else None)
                        )
                        if matching:
                            results[fname].doc_id = matching.get("doc_id")
                            results[fname].doc_name = matching.get("doc_name")
                elif fdata is not None:
                    # Scalar value
                    val = str(fdata).strip()
                    if val and val not in ("null", "None", "N/A"):
                        results[fname].value = val
                        results[fname].source_type = _detect_source_type(chunks)
                        results[fname].url = first_url

        except Exception as e:
            logger.error("[Extractor] Batched extraction failed: %s", e)

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
