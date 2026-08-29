"""
pipeline/evaluator.py — AI Evaluation Engine (LLM-as-Judge).

Evaluates a completed product enrichment record across 5 dimensions:
  1. Completeness     — % of category-expected fields filled
  2. Citation Quality — fraction of fields with valid source citation/snippet
  3. Hallucination Risk — LLM assesses plausibility of extracted values
  4. Consistency      — cross-field logical consistency (dimensions, UOM pairs, etc.)
  5. Description Quality — readability, length and informativeness of generated descriptions

Returns an EvaluationReport dict that can be served via the /evaluate/{job_id} endpoint.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from typing import Any

from pipeline.utils import generate_with_retry, parse_json_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_completeness(state: dict) -> dict:
    """Score how many expected fields are filled."""
    expected = state.get("expected_fields") or []
    specs = state.get("specifications") or state.get("extracted_fields") or {}

    # Always check these universal fields too
    universal = [
        "description", "short_desc", "long_desc", "invoice_desc",
        "manufacturer_name", "brand", "category",
        "country_of_origin", "warranty", "unspsc",
    ]
    all_expected = list(dict.fromkeys(expected + universal))

    filled = 0
    missing = []
    for field in all_expected:
        # Check specs dict first
        fv = specs.get(field)
        val = None
        if fv is not None:
            if isinstance(fv, dict):
                val = fv.get("value")
            elif hasattr(fv, "value"):
                val = fv.value
            else:
                val = fv
        # Fall back to top-level state keys
        if val is None:
            val = state.get(field)

        if val is not None and str(val).strip() not in ("", "None", "null"):
            filled += 1
        else:
            missing.append(field)

    total = len(all_expected)
    score = round(filled / total, 3) if total > 0 else 0.0
    return {
        "score": score,
        "filled": filled,
        "total": total,
        "missing_fields": missing[:10],  # top 10 missing
        "reasoning": f"{filled}/{total} expected fields are populated ({score*100:.0f}%).",
    }


def _score_citation_quality(state: dict) -> dict:
    """Score fraction of specs that have a source URL or snippet."""
    specs = state.get("specifications") or state.get("extracted_fields") or {}
    if not specs:
        return {"score": 0.0, "reasoning": "No specifications found.", "cited": 0, "total": 0}

    cited = 0
    uncited = []
    for fname, fv in specs.items():
        if isinstance(fv, dict):
            has_url = bool(fv.get("url") or fv.get("source_url"))
            has_snip = bool(fv.get("snippet") or fv.get("source_snippet"))
            if has_url or has_snip:
                cited += 1
            else:
                uncited.append(fname)
        elif hasattr(fv, "url") or hasattr(fv, "snippet"):
            has_url = bool(getattr(fv, "url", None) or getattr(fv, "source_url", None))
            has_snip = bool(getattr(fv, "snippet", None) or getattr(fv, "source_snippet", None))
            if has_url or has_snip:
                cited += 1
            else:
                uncited.append(fname)

    total = len(specs)
    score = round(cited / total, 3) if total > 0 else 0.0
    return {
        "score": score,
        "cited": cited,
        "total": total,
        "uncited_fields": uncited[:10],
        "reasoning": f"{cited}/{total} specification fields have source citations ({score*100:.0f}%).",
    }


def _score_consistency(state: dict) -> dict:
    """
    Rule-based cross-field consistency checks:
    - Dimension UOM pairs (length/length_uom, weight/weight_uom, etc.)
    - Price sanity (list_price should be a number)
    - Country of origin should be a real country name
    - UNSPSC should be 8 digits
    """
    issues = []
    score = 1.0

    def _get(field):
        specs = state.get("specifications") or {}
        fv = specs.get(field)
        if fv is not None:
            if isinstance(fv, dict):
                return fv.get("value")
            if hasattr(fv, "value"):
                return fv.value
        return state.get(field)

    # Check dimension UOM pairs
    dim_pairs = [
        ("length", "length_uom"),
        ("width", "width_uom"),
        ("height", "height_uom"),
        ("weight", "weight_uom"),
        ("volume", "volume_uom"),
    ]
    for val_field, uom_field in dim_pairs:
        val = _get(val_field)
        uom = _get(uom_field)
        if val and not uom:
            issues.append(f"'{val_field}' has a value ('{val}') but '{uom_field}' is missing.")
            score -= 0.05

    # UNSPSC format
    unspsc = _get("unspsc")
    if unspsc:
        clean = str(unspsc).replace("-", "").replace(".", "").strip()
        if not clean.isdigit() or len(clean) != 8:
            issues.append(f"UNSPSC '{unspsc}' is not a valid 8-digit code.")
            score -= 0.05

    # List price sanity
    list_price = _get("list_price")
    if list_price:
        import re
        num_match = re.search(r"[\d.]+", str(list_price))
        if num_match:
            try:
                p = float(num_match.group())
                if p <= 0 or p > 1_000_000:
                    issues.append(f"List price '{list_price}' seems implausible.")
                    score -= 0.05
            except ValueError:
                pass

    score = max(0.0, round(score, 3))
    if not issues:
        reasoning = "All cross-field consistency checks passed."
    else:
        reasoning = f"{len(issues)} consistency issue(s) found: " + "; ".join(issues[:3])

    return {
        "score": score,
        "issues": issues,
        "reasoning": reasoning,
    }


def _score_description_quality(state: dict) -> dict:
    """Score the quality of generated descriptions (length, completeness, brand mention)."""
    brand = state.get("brand", "")
    mpn = state.get("mpn", "")
    category = state.get("category", "")

    descs = {
        "short_desc": state.get("short_desc") or "",
        "long_desc": state.get("long_desc") or "",
        "invoice_desc": state.get("invoice_desc") or "",
        "marketing_description": state.get("marketing_description") or "",
    }

    scores = []
    feedback = []

    for name, text in descs.items():
        if not text:
            feedback.append(f"'{name}' is empty.")
            scores.append(0.0)
            continue
        word_count = len(text.split())
        has_brand = brand.lower() in text.lower() if brand else True
        has_mpn = mpn.lower() in text.lower() if mpn else True
        has_category = category.lower() in text.lower() if category else True

        field_score = 0.5
        if word_count >= 5:
            field_score += 0.15
        if word_count >= 15:
            field_score += 0.15
        if has_brand:
            field_score += 0.1
        if has_category or has_mpn:
            field_score += 0.1

        if word_count < 3:
            feedback.append(f"'{name}' is too short ({word_count} words).")
        scores.append(min(1.0, field_score))

    # Item features bonus
    features = state.get("item_features") or []
    if len(features) >= 3:
        scores.append(0.9)
    elif features:
        scores.append(0.6)
    else:
        scores.append(0.2)
        feedback.append("No item features generated.")

    score = round(sum(scores) / len(scores), 3) if scores else 0.0
    reasoning = f"Average description quality: {score*100:.0f}%."
    if feedback:
        reasoning += " Issues: " + "; ".join(feedback[:3])

    return {
        "score": score,
        "feedback": feedback,
        "reasoning": reasoning,
    }


def _score_hallucination_risk_llm(state: dict) -> dict:
    """
    Use the LLM to assess hallucination risk by checking if extracted
    values are plausible for the product category and brand.
    Returns a score between 0 (high hallucination risk) and 1 (low risk).
    """
    brand = state.get("brand", "")
    mpn = state.get("mpn", "")
    category = state.get("category", "Unknown")
    description = state.get("description", "")

    specs = state.get("specifications") or state.get("extracted_fields") or {}
    # Sample up to 15 fields for the LLM to evaluate
    sample_fields = {}
    for fname, fv in list(specs.items())[:15]:
        if isinstance(fv, dict):
            val = fv.get("value")
        elif hasattr(fv, "value"):
            val = fv.value
        else:
            val = fv
        if val is not None and str(val).strip() not in ("", "None", "null"):
            sample_fields[fname] = str(val)[:120]

    if not sample_fields:
        return {
            "score": 0.5,
            "risk_level": "unknown",
            "flagged_fields": [],
            "reasoning": "No specification fields available to evaluate.",
        }

    prompt = (
        f"You are a product data quality auditor. Evaluate whether the extracted specification values "
        f"are PLAUSIBLE for this product. Flag any values that look hallucinated, wrong, or physically impossible.\n\n"
        f"Product: {brand} {mpn}\n"
        f"Category: {category}\n"
        f"Description: {description or 'N/A'}\n\n"
        f"Extracted fields:\n"
        + "\n".join(f"  {k}: {v}" for k, v in sample_fields.items())
        + "\n\nRespond with a JSON object:\n"
        '{"hallucination_score": <float 0.0-1.0, where 1.0 = clearly hallucinated, 0.0 = all plausible>,'
        ' "flagged_fields": [{"field": "...", "value": "...", "reason": "..."}],'
        ' "reasoning": "..."}'
    )

    try:
        raw = generate_with_retry(
            messages=[
                {"role": "system", "content": "You output only valid JSON. No markdown."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = parse_json_response(raw)
        h_score = float(data.get("hallucination_score", 0.3))
        flagged = data.get("flagged_fields", [])
        reasoning = data.get("reasoning", "")
        # Convert hallucination_score (0=good, 1=bad) → quality score (0=bad, 1=good)
        quality_score = round(1.0 - h_score, 3)
        risk_level = "low" if h_score < 0.2 else ("medium" if h_score < 0.5 else "high")
        return {
            "score": quality_score,
            "risk_level": risk_level,
            "flagged_fields": flagged[:5],
            "reasoning": reasoning,
        }
    except Exception as e:
        logger.warning("[Evaluator] Hallucination LLM call failed: %s", e)
        return {
            "score": 0.5,
            "risk_level": "unknown",
            "flagged_fields": [],
            "reasoning": f"LLM evaluation unavailable: {e}",
        }


# ---------------------------------------------------------------------------
# Grade mapping
# ---------------------------------------------------------------------------

def _compute_grade(overall_score: float) -> str:
    if overall_score >= 0.90:
        return "A"
    elif overall_score >= 0.80:
        return "B"
    elif overall_score >= 0.70:
        return "C"
    elif overall_score >= 0.55:
        return "D"
    else:
        return "F"


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------

def evaluate_product(state: dict) -> dict:
    """
    Run a full AI evaluation on a completed product enrichment state.

    Returns an EvaluationReport dict with per-dimension scores, an overall
    score, a letter grade, and actionable recommendations.
    """
    brand = state.get("brand", "")
    mpn = state.get("mpn", "")
    logger.info("[Evaluator] Running evaluation for %s %s", brand, mpn)

    # Run all dimensions
    completeness = _score_completeness(state)
    citation = _score_citation_quality(state)
    consistency = _score_consistency(state)
    desc_quality = _score_description_quality(state)
    hallucination = _score_hallucination_risk_llm(state)

    # Weighted overall score
    # Weights: completeness 30%, citation 20%, hallucination 25%, consistency 15%, desc 10%
    weights = {
        "completeness": 0.30,
        "citation_quality": 0.20,
        "hallucination_risk": 0.25,
        "consistency": 0.15,
        "description_quality": 0.10,
    }
    scores = {
        "completeness": completeness["score"],
        "citation_quality": citation["score"],
        "hallucination_risk": hallucination["score"],
        "consistency": consistency["score"],
        "description_quality": desc_quality["score"],
    }
    overall = round(sum(weights[k] * v for k, v in scores.items()), 3)
    grade = _compute_grade(overall)

    # Generate recommendations
    recommendations = []
    if completeness["score"] < 0.7:
        missing = completeness.get("missing_fields", [])
        if missing:
            recommendations.append(f"Fill missing fields: {', '.join(missing[:5])}.")
    if citation["score"] < 0.6:
        recommendations.append("Add source citations/snippets for specification values.")
    if hallucination["risk_level"] in ("medium", "high"):
        flagged = hallucination.get("flagged_fields", [])
        if flagged:
            fields_str = ", ".join(f["field"] for f in flagged[:3])
            recommendations.append(f"Review potentially hallucinated fields: {fields_str}.")
    if consistency["issues"]:
        recommendations.append(f"Fix consistency issues: {consistency['issues'][0]}")
    if desc_quality["score"] < 0.6:
        recommendations.append("Improve description quality — ensure brand, category, and key specs are mentioned.")

    report = {
        "job_id": state.get("job_id", ""),
        "brand": brand,
        "mpn": mpn,
        "category": state.get("category", ""),
        "overall_score": overall,
        "grade": grade,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dimensions": {
            "completeness": completeness,
            "citation_quality": citation,
            "hallucination_risk": hallucination,
            "consistency": consistency,
            "description_quality": desc_quality,
        },
        "weights": weights,
        "recommendations": recommendations,
    }
    logger.info("[Evaluator] Done — grade=%s, overall=%.3f", grade, overall)
    return report
