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

from schema import SourceType, Citation, FieldValue

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


def validate(extracted_fields: dict, chunks: list[dict]) -> tuple[dict[str, FieldValue], float, list[str]]:
    """
    Takes extracted fields and chunks, returns (specifications, overall_confidence, flagged_fields).
    """
    specs = {}
    flagged = []

    for fname, ext in extracted_fields.items():
        val = ext.value
        if val is None:
            continue

        stype = ext.source_type
        base = 0.5
        method = "extracted"
        cause = "Extracted successfully."
        
        # 1. Base confidence by source_type
        if stype in ("webpage_text", "pdf_text"):
            base = 0.9
            cause = "Directly read from document text."
        elif stype == "pdf_table":
            base = 0.8
            cause = f"Read from a table structure ({ext.table_location})."
        elif stype == "pdf_chart":
            base = 0.65
            cause = f"Visually read from a chart/diagram ({ext.chart_description}), which is inherently less precise."
        elif stype == "inferred":
            base = 0.5
            method = "inferred"
            cause = "AI Domain Knowledge fallback (no direct source found in retrieved documents)."
        else:
            base = 0.5
            method = "inferred"
            cause = "Source uncertain."

        penalties = 0.0
        
        # 2. Penalty: snippet hallucination
        if stype in ("webpage_text", "pdf_text") and ext.snippet:
            # Find the original chunk
            original_chunk = None
            if ext.doc_id:
                original_chunk = next((c for c in chunks if c.get("doc_id") == ext.doc_id and c.get("page_number") == ext.page_number), None)
            elif ext.url:
                original_chunk = next((c for c in chunks if c.get("url") == ext.url), None)
                
            chunk_text = original_chunk["text"] if original_chunk else ""
            if not _snippet_in_text(ext.snippet, chunk_text):
                penalties += 0.4
                method = "inferred"
                cause = "Snippet claimed but NOT found in source chunk text. Likely hallucination. Please verify."

        # 3. Penalty: Sanity check
        sane, reason = _run_sanity(fname, val)
        if not sane:
            penalties += 0.3
            cause += f" Failed sanity check: {reason}. Please verify."

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
            snippet=ext.snippet,
            table_location=ext.table_location,
            chart_description=ext.chart_description,
            similar_products_used=ext.similar_products_used
        )
        
        specs[fname] = FieldValue(
            value=val,
            confidence=round(conf, 3),
            method=method,
            cause=cause,
            citation=cit
        )
        
    overall = sum(f.confidence for f in specs.values()) / len(specs) if specs else 0.0
    return specs, round(overall, 3), flagged


if __name__ == "__main__":
    print("\n[PASS] validator.py syntax check passed.")
