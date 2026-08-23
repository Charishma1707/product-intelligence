"""
validator.py — Stage 4 of the pipeline.

Responsibilities:
  - Validate extracted fields and assign source-type-aware confidence.
  - Apply penalties for hallucinations (snippet not in chunk) and sanity check failures.
  - Generate a plain-English `cause` for the confidence score.
  - Return final FieldValue objects in a ProductRecord-compatible dict.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

from schema import SourceType, Citation, FieldValue, FieldStatus

logger = logging.getLogger(__name__)

# Sanity rules: field_name → (min_value, max_value, expected_unit_hint)
FIELD_SANITY: dict[str, tuple] = {
    "rated_current_a":       (0.1,   1600,  "A"),
    "coil_voltage":          (5,     1000,  "V"),
    "rated_voltage_v":       (5,     1500,  "V"),
    "power_rating_kw":       (0.001, 1000,  "kW"),
    "bore_diameter_mm":      (0.5,   2000,  "mm"),
    "outer_diameter_mm":     (1,     3000,  "mm"),
    "width_mm":              (0.5,   1000,  "mm"),
    "weight_kg":             (0.001, 5000,  "kg"),
    "limiting_speed_rpm":    (1,     1_000_000, "rpm"),
    "dynamic_load_rating_kn":(0.01,  10_000, "kN"),
    "sensing_distance_mm":   (0.1,   10_000, "mm"),
}


_BOOLEAN_FIELDS = {"prop_65", "discontinued", "actual_image", "with_accessories"}
_GARBAGE_STRINGS = {"yes", "no", "true", "false", "null", "none", "n/a", "unknown", "display only", "-- unbranded --", "-- no unilog brand --", "-- no dib brand --"}


def _is_invalid_garbage(fname: str, value: str) -> tuple[bool, str]:
    s = str(value).strip().lower()
    if not s:
        return True, "Empty value."
    if fname.lower() not in _BOOLEAN_FIELDS and s in _GARBAGE_STRINGS:
        return True, f"Placeholder value '{value}' is invalid for '{fname.replace('_', ' ').title()}'."
    return False, ""


def _extract_first_number(s) -> float | None:
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    m = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(s))
    return float(m.group()) if m else None


def _snippet_in_text(snippet: str, text: str) -> bool:
    if not snippet or not text: return False
    snippet_clean = snippet.strip().lower()
    text_clean = text.lower()
    if snippet_clean in text_clean: return True
    slen = len(snippet_clean)
    if slen < 10: return False
    step = max(1, slen // 3)
    for start in range(0, max(1, len(text_clean) - slen + 1), step):
        window = text_clean[start : start + slen + 40]
        if SequenceMatcher(None, snippet_clean, window).ratio() > 0.65:
            return True
    return False


def _run_sanity(fname: str, value) -> tuple[bool, str]:
    if fname not in FIELD_SANITY: return True, ""
    min_v, max_v, hint = FIELD_SANITY[fname]
    num = _extract_first_number(value)
    if num is None: return True, ""
    if num < min_v: return False, f"Value {num} is below min {min_v} {hint}"
    if num > max_v: return False, f"Value {num} exceeds max {max_v} {hint}"
    return True, ""


# Common raw materials that should never be classified purely as a 'color'
_RAW_MATERIALS = {
    "copper", "brass", "bronze", "stainless steel", "carbon steel", "cast iron",
    "aluminum", "titanium", "pvc", "polyethylene", "polypropylene", "ptfe", "teflon",
    "rubber", "silicone", "neoprene", "ceramic", "porcelain", "zinc", "nickel"
}


def _check_semantic_mismatch_rules(fname: str, value: str) -> tuple[bool, str]:
    """
    Deterministic rule-based checks for common cross-field category confusions.
    E.g. Assigning raw material to color, or amps to voltage rating.
    """
    s = str(value).strip().lower()
    fn = fname.lower()

    # 1. Material mistakenly placed in Color field
    if fn in ("color", "finish_color", "housing_color") and s in _RAW_MATERIALS:
        return False, f"Semantic Mismatch: '{value}' is a raw construction Material, not an applied finish Color."

    # 2. Amperage units placed in Voltage Rating
    if "voltage" in fn and any(u in s for u in [" a", " amp", " amps", " amperes", " ma"]) and " v" not in s and "volt" not in s:
        return False, f"Semantic Mismatch: Amperage/Current unit found in Voltage field '{value}'."

    # 3. Voltage units placed in Amperage Rating
    if "amperage" in fn and any(u in s for u in [" v", " volt", " volts", " kv"]) and " a" not in s and "amp" not in s:
        return False, f"Semantic Mismatch: Voltage unit found in Amperage field '{value}'."

    # 4. Dimension units placed in Weight field
    if "weight" in fn and any(u in s for u in [" in", " inch", " mm", " cm", " ft", " meter"]) and not any(w in s for w in [" lb", " kg", " oz", " gram"]):
        return False, f"Semantic Mismatch: Length/Dimension unit found in Weight field '{value}'."

    return True, ""


def _llm_check_attribute_plausibility(category: str, description: str, attributes: dict[str, Any]) -> dict[str, str]:
    """
    LLM semantic auditor: Evaluates whether extracted attributes are physically and
    categorically plausible for the given product.
    Returns: dict mapping field_name -> issue explanation string (if implausible).
    """
    if not attributes:
        return {}

    try:
        from pipeline.utils import generate_with_retry, parse_json_response

        # Prepare summary of fields to audit
        sample_attrs = {k: v for k, v in attributes.items() if v is not None}
        if not sample_attrs:
            return {}

        prompt = (
            "You are an industrial catalog data quality auditor.\n"
            "Evaluate if the following extracted attribute values are semantically and physically plausible for this product.\n"
            f"Product Category: {category}\n"
            f"Product Description: {description}\n"
            f"Extracted Attributes: {sample_attrs}\n\n"
            "Look specifically for:\n"
            "1. Field confusions (e.g. Raw Material like 'Copper' placed in 'Color', '15A' placed in 'Voltage').\n"
            "2. Physically impossible or nonsensical attributes for this product type.\n\n"
            "Return a JSON object with this format:\n"
            "{\n"
            "  \"issues\": {\n"
            "    \"field_name\": \"Brief 1-sentence reason why this value is semantically implausible\"\n"
            "  }\n"
            "}\n"
            "If all attributes are plausible and properly categorized, return {\"issues\": {}}."
        )

        resp = generate_with_retry(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        parsed = parse_json_response(resp)
        return parsed.get("issues", {})
    except Exception as e:
        logger.warning("[Validator] LLM semantic plausibility check failed: %s", e)
        return {}


def validate(
    extracted_fields: dict,
    chunks: list[dict],
    category: str = "",
    description: str = "",
) -> tuple[dict[str, FieldValue], float, list[str]]:
    """
    Takes extracted fields and chunks, applies sanity + anti-hallucination + semantic compatibility checks,
    and returns (specifications, overall_confidence, flagged_fields).
    """
    specs = {}
    flagged = []
    # Run LLM plausibility audit on non-empty extracted attributes
    raw_attr_dict = {fname: getattr(ext, "value", None) for fname, ext in extracted_fields.items() if getattr(ext, "value", None) is not None}
    llm_issues = _llm_check_attribute_plausibility(category, description, raw_attr_dict) if raw_attr_dict else {}

    for fname, ext in extracted_fields.items():
        val = ext.value
        if val is None:
            # Document missing / null attributes with clear explanation
            specs[fname] = FieldValue(
                value=None,
                confidence=0.0,
                status=FieldStatus.MISSING,
                extraction_method="missing",
                source=Citation(evidence="Not found in retrieved documentation or input description; not applicable or product-specific data unavailable.")
            )
            continue

        # Check for placeholder/garbage values (e.g. 'yes' for material or voltage)
        is_garbage, garbage_msg = _is_invalid_garbage(fname, str(val))

        stype = ext.source_type
        base = 0.5
        method = "extracted"
        cause = "Extracted successfully."
        
        if is_garbage:
            base = 0.20
            cause = f"Flagged: {garbage_msg}"
            flagged.append(fname)
        else:
            # 1. Base confidence by source_type & source tier
            source_tier = getattr(ext, "source_tier", 3)
            mpn_verified = getattr(ext, "mpn_verified", False)
            
            if stype == "mfr_webpage":
                if mpn_verified or source_tier == 1:
                    base = 0.98
                    cause = "Directly verified on manufacturer's official exact-MPN product page."
                else:
                    base = 0.90
                    cause = "Extracted from manufacturer's domain (general product line/catalog)."
            elif stype == "series_knowledge":
                base = 0.92
                cause = "Inherited from verified series-level knowledge repository."
            elif stype in ("description", "input_description") or ext.url == "Input Description":
                base = 0.95
                method = "extracted_description"
                cause = "Directly extracted from user input product description."
            elif stype in ("webpage_text", "pdf_text"):
                if mpn_verified or source_tier in (1, 3):
                    base = 0.88
                    cause = "Directly verified from technical documentation with exact MPN match."
                else:
                    base = 0.78
                    cause = "Read from general technical documentation (MPN not explicitly confirmed on page)."
            elif stype == "pdf_table":
                base = 0.85 if mpn_verified else 0.75
                cause = f"Extracted from specification table ({ext.table_location or 'PDF table'})."
            elif stype == "pdf_chart":
                base = 0.65
                cause = f"Visually interpreted from chart/diagram ({ext.chart_description or 'PDF chart'}), inherently less precise."
            elif stype == "inferred":
                base = 0.50
                method = "inferred"
                cause = "AI Domain Knowledge inference (no direct evidence found in retrieved documents)."
            else:
                base = 0.50
                method = "inferred"
                cause = "Source provenance unconfirmed."

        penalties = 0.0
        
        # 2. Penalty: Variant-specific attribute from unverified MPN document
        from pipeline.extractor import is_variant_specific
        if is_variant_specific(fname) and stype not in ("inferred", "series_knowledge") and not mpn_verified:
            penalties += 0.20
            cause += " Warning: Document lacked explicit exact MPN confirmation for this variant-specific attribute."

        # 3. Penalty: snippet hallucination
        if stype in ("webpage_text", "pdf_text", "mfr_webpage") and ext.snippet:
            # Find the original chunk
            original_chunk = None
            if ext.doc_id:
                original_chunk = next((c for c in chunks if c.get("doc_id") == ext.doc_id and c.get("page_number") == ext.page_number), None)
            elif ext.url:
                original_chunk = next((c for c in chunks if c.get("url") == ext.url), None)
                
            chunk_text = original_chunk["text"] if original_chunk else ""
            if not chunk_text and description:
                chunk_text = description
            if not _snippet_in_text(ext.snippet, chunk_text):
                penalties += 0.40
                method = "inferred"
                cause = "Snippet claimed but NOT found in source chunk text. Likely hallucination. Please verify."

        # 4. Penalty: Sanity check (physical unit bounds)
        sane, reason = _run_sanity(fname, val)
        if not sane:
            penalties += 0.30
            cause += f" Failed sanity check: {reason}. Please verify."

        # 5. Penalty: Deterministic Semantic Mismatch Check (e.g. Copper in Color)
        sem_sane, sem_msg = _check_semantic_mismatch_rules(fname, str(val))
        if not sem_sane:
            penalties += 0.35
            cause += f" {sem_msg}"
            if fname not in flagged:
                flagged.append(fname)

        # 6. Penalty: LLM Semantic Plausibility & Field Compatibility Check
        if fname in llm_issues:
            penalties += 0.30
            cause += f" Plausibility Alert: {llm_issues[fname]}"
            if fname not in flagged:
                flagged.append(fname)

        # Calculate final confidence
        conf = max(0.0, min(1.0, base - penalties))
        
        if method == "inferred":
            conf = min(conf, 0.6) # cap inferred at 0.6
            
        if conf < 0.75:
            flagged.append(fname)
            
        # Build Citation
        try:
            source_type_enum = SourceType(stype)
        except ValueError:
            source_type_enum = SourceType.INFERRED
            
        cit = Citation(
            source_type=source_type_enum,
            url=ext.url,
            doc_id=ext.doc_id,
            doc_name=ext.doc_name,
            page_number=ext.page_number,
            evidence=ext.snippet or cause,
            table_location=ext.table_location,
            chart_description=ext.chart_description,
            similar_products_used=ext.similar_products_used
        )
        
        specs[fname] = FieldValue(
            value=val,
            confidence=round(conf, 3),
            extraction_method=method,
            status=FieldStatus.VERIFIED if conf >= 0.85 else (FieldStatus.INFERRED if method == "inferred" else FieldStatus.NEEDS_REVIEW),
            source=cit
        )
        
    overall = sum(f.confidence for f in specs.values()) / len(specs) if specs else 0.0
    return specs, round(overall, 3), flagged


if __name__ == "__main__":
    print("\n[PASS] validator.py syntax check passed.")
