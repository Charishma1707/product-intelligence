"""
benchmark.py — Field-level accuracy benchmark against Unilog ground truth.

Usage:
    .venv\\Scripts\\python benchmark.py [--n 5] [--offline]

Reads:
  - Input:  ../Unihack_ Sample Dataset - Input.csv
  - Truth:  ../Unihack_ Expected Output - Delivery Format.csv

For each sampled product, runs the full pipeline and compares
the output to the known-good ground truth row, field by field.

Prints a beautiful color-coded accuracy report and saves:
  - benchmark_results.csv    (per-field results for every product)
  - benchmark_summary.json   (overall accuracy metrics)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

# ── Setup ──
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("pipeline").setLevel(logging.INFO)

# ── ANSI colors (ASCII-safe) ──
_R  = "\033[0m"
_B  = "\033[1m"
_G  = "\033[32m"
_Y  = "\033[33m"
_RE = "\033[31m"
_CY = "\033[36m"
_GR = "\033[90m"
_BL = "\033[34m"

def ok(s):   print(f"  {_G}{s}{_R}")
def warn(s): print(f"  {_Y}{s}{_R}")
def err(s):  print(f"  {_RE}{s}{_R}")
def info(s): print(f"  {_GR}{s}{_R}")
def hdr(s):  print(f"\n{_B}{_BL}{'='*64}{_R}\n{_B}{_BL}  {s}{_R}\n{_B}{_BL}{'='*64}{_R}")
def kv(k,v): print(f"  {_CY}{k:<32}{_R}{v}")

# ── Root-level file paths ──
ROOT = Path(__file__).parent.parent
INPUT_CSV  = ROOT / "Unihack_ Sample Dataset - Input.csv"
TRUTH_CSV  = ROOT / "Unihack_ Expected Output - Delivery Format.csv"

# ── Fields we benchmark (these have ground truth in the expected output) ──
CORE_FIELDS = [
    "Classpath",
    "MANUFACTURER_NAME",
    "BRAND_NAME",
    "MOBILE_DESC",
    "INVOICE_DESC",
    "SHORT_DESC",
    "LONG_DESC1",
]

ATTR_SLOTS = 20  # how many attribute slots to check

# ── Scoring helpers ──

def _norm(s: str) -> str:
    """Normalize for fuzzy comparison."""
    return " ".join(str(s).lower().split()).strip()


def _exact(pred: str, truth: str) -> float:
    """1.0 if identical after normalization, else 0."""
    return 1.0 if _norm(pred) == _norm(truth) else 0.0


def _fuzzy(pred: str, truth: str) -> float:
    """SequenceMatcher similarity ratio (0-1)."""
    if not pred or not truth:
        return 0.0
    return SequenceMatcher(None, _norm(pred), _norm(truth)).ratio()


def _classpath_score(pred: str, truth: str) -> float:
    """
    Partial credit for classpath:
    - Every correctly named level = 1/total_levels
    - Case-insensitive, ignores whitespace
    """
    if not pred or not truth:
        return 0.0
    pred_parts  = [p.strip().lower() for p in pred.split(">")]
    truth_parts = [p.strip().lower() for p in truth.split(">")]
    if not truth_parts:
        return 0.0
    correct = sum(1 for p, t in zip(pred_parts, truth_parts) if p == t)
    return correct / len(truth_parts)


def _attribute_jaccard(pred_attrs: dict, truth_attrs: dict) -> float:
    """
    Jaccard-like score for attribute coverage:
    |pred_labels ∩ truth_labels| / |pred_labels ∪ truth_labels|
    """
    pred_set  = set(_norm(k) for k in pred_attrs if k)
    truth_set = set(_norm(k) for k in truth_attrs if k)
    if not truth_set:
        return 1.0 if not pred_set else 0.5
    intersection = len(pred_set & truth_set)
    union = len(pred_set | truth_set)
    return intersection / union if union > 0 else 0.0


def _extract_truth_attrs(row: dict) -> dict:
    """Pull attribute label→value pairs from a ground truth CSV row."""
    attrs = {}
    for i in range(1, ATTR_SLOTS + 1):
        label = row.get(f"ATTRIBUTE_LABEL {i}", "").strip()
        value = row.get(f"ATTRIBUTE_VALUE {i}", "").strip()
        if label:
            attrs[label] = value
    return attrs


def _extract_pred_attrs(specs: dict) -> dict:
    """Extract attribute label→value pairs from pipeline output specs dict."""
    attrs = {}
    for fname, fv in specs.items():
        if hasattr(fv, "model_dump"):
            fv = fv.model_dump()
        val = fv.get("value") if isinstance(fv, dict) else getattr(fv, "value", None)
        if val is not None:
            attrs[fname] = str(val)
    return attrs


# ── Load ground truth ──

def load_truth() -> dict[str, dict]:
    """Returns {Mfg_Part_Num -> row_dict} for all truth rows."""
    if not TRUTH_CSV.exists():
        print(f"{_RE}ERROR: Truth CSV not found: {TRUTH_CSV}{_R}")
        sys.exit(1)
    index = {}
    with open(TRUTH_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            mpn = row.get("Mfg_Part_Num", "").strip()
            if mpn:
                index[mpn] = row
    return index


def load_input(n: int, seed_offset: int = 0) -> list[dict]:
    """
    Return up to n products from input CSV that also exist in truth CSV.
    Picks products that have SOME ground truth values (not all empty).
    """
    truth = load_truth()
    candidates = []
    with open(INPUT_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            mpn = row.get("Mfg_Part_Num", "").strip()
            if not mpn or mpn not in truth:
                continue
            truth_row = truth[mpn]
            # Must have at least Classpath and one description field
            if not truth_row.get("Classpath") or not truth_row.get("SHORT_DESC"):
                continue
            candidates.append(row)

    # Sample evenly across the list for variety
    if len(candidates) <= n:
        return candidates
    step = len(candidates) // n
    return [candidates[(i * step + seed_offset) % len(candidates)] for i in range(n)]


# ── Run single product through pipeline ──

def run_pipeline(brand: str, mpn: str, description: str, offline: bool) -> dict:
    """Run one product through the pipeline. Returns the final state dict."""
    if offline:
        os.environ["OFFLINE_DEMO"] = "true"

    from pipeline.graph import build_graph, make_initial_state
    from pipeline.job_store import init_db

    init_db()
    graph = build_graph()
    job_id = f"bench-{mpn.lower()[:20]}-{int(time.time())}"
    state  = make_initial_state(brand=brand, mpn=mpn, description=description, job_id=job_id)

    try:
        final = graph.invoke(state)
        return final
    except Exception as e:
        logging.error("Pipeline failed for %s %s: %s", brand, mpn, e)
        return {"status": "failed", "specifications": {}, "job_id": job_id}


# ── Score one product ──

def score_product(final: dict, truth_row: dict) -> dict:
    """
    Compare pipeline output to ground truth.
    Returns per-field scores dict.
    """
    scores = {}

    # 1. Classpath
    pred_classpath  = final.get("classpath") or final.get("category") or ""
    truth_classpath = truth_row.get("Classpath", "")
    scores["classpath"] = {
        "pred":  pred_classpath,
        "truth": truth_classpath,
        "score": _classpath_score(pred_classpath, truth_classpath),
        "method": "partial_path",
    }

    # 2. MANUFACTURER_NAME
    specs = final.get("specifications", {})
    pred_mfr = ""
    for k in ("MANUFACTURER_NAME", "manufacturer_name", "Manufacturer"):
        fv = specs.get(k)
        if fv:
            pred_mfr = str(fv.get("value") if isinstance(fv, dict) else getattr(fv, "value", "")) or ""
            break
    scores["manufacturer_name"] = {
        "pred":  pred_mfr,
        "truth": truth_row.get("MANUFACTURER_NAME", ""),
        "score": _fuzzy(pred_mfr, truth_row.get("MANUFACTURER_NAME", "")),
        "method": "fuzzy",
    }

    # 3. BRAND_NAME
    pred_brand = final.get("brand") or ""
    scores["brand_name"] = {
        "pred":  pred_brand,
        "truth": truth_row.get("BRAND_NAME", ""),
        "score": _fuzzy(pred_brand, truth_row.get("BRAND_NAME", "")),
        "method": "fuzzy",
    }

    # 4. Text content fields (fuzzy match)
    text_field_map = {
        "mobile_desc":  ("mobile_desc",   "MOBILE_DESC"),
        "invoice_desc": ("invoice_desc",  "INVOICE_DESC"),
        "short_desc":   ("short_desc",    "SHORT_DESC"),
        "long_desc":    ("long_desc",     "LONG_DESC1"),
    }
    for key, (state_field, truth_field) in text_field_map.items():
        pred_val  = final.get(state_field) or ""
        truth_val = truth_row.get(truth_field, "")
        scores[key] = {
            "pred":  pred_val[:120] if pred_val else "",
            "truth": truth_val[:120] if truth_val else "",
            "score": _fuzzy(pred_val, truth_val),
            "method": "fuzzy",
        }

    # 5. Attribute coverage (Jaccard)
    pred_attrs  = _extract_pred_attrs(specs)
    truth_attrs = _extract_truth_attrs(truth_row)
    attr_score  = _attribute_jaccard(pred_attrs, truth_attrs)
    scores["attribute_coverage"] = {
        "pred":  f"{len(pred_attrs)} attrs",
        "truth": f"{len(truth_attrs)} attrs",
        "score": attr_score,
        "method": "jaccard",
        "pred_attrs":  list(pred_attrs.keys())[:10],
        "truth_attrs": list(truth_attrs.keys())[:10],
    }

    # 6. Field fill rate (what % of expected fields have any value)
    expected_fields = final.get("expected_fields", [])
    if expected_fields:
        filled = sum(
            1 for f in expected_fields
            if specs.get(f) and (
                specs[f].get("value") if isinstance(specs[f], dict)
                else getattr(specs[f], "value", None)
            ) is not None
        )
        scores["field_fill_rate"] = {
            "pred":  f"{filled}/{len(expected_fields)}",
            "truth": "all fields",
            "score": filled / len(expected_fields) if expected_fields else 0.0,
            "method": "fill_rate",
        }

    # 7. Spec sheet found
    scores["spec_sheet_found"] = {
        "pred":  "yes" if final.get("spec_sheet_url") else "no",
        "truth": "yes" if truth_row.get("Specification Sheet") else "unknown",
        "score": 1.0 if final.get("spec_sheet_url") else 0.0,
        "method": "binary",
    }

    # 8. UNSPSC code
    pred_unspsc = ""
    for k in ("UNSPSC", "unspsc"):
        fv = specs.get(k)
        if fv:
            pred_unspsc = str(fv.get("value") if isinstance(fv, dict) else getattr(fv, "value", "")) or ""
            break
    scores["unspsc"] = {
        "pred":  pred_unspsc,
        "truth": truth_row.get("UNSPSC", ""),
        "score": _exact(pred_unspsc, truth_row.get("UNSPSC", "")) if truth_row.get("UNSPSC") else None,
        "method": "exact",
    }

    return scores


# ── Pretty print results for one product ──

def print_product_result(mpn: str, brand: str, scores: dict, overall: float):
    print(f"\n  {_B}{mpn}{_R}  {_GR}({brand}){_R}")
    print(f"  {_GR}{'-'*60}{_R}")

    for field, result in scores.items():
        score = result.get("score")
        if score is None:
            color, bar = _GR, "N/A "
        elif score >= 0.85:
            color, bar = _G,  f"{score*100:5.1f}%"
        elif score >= 0.50:
            color, bar = _Y,  f"{score*100:5.1f}%"
        else:
            color, bar = _RE, f"{score*100:5.1f}%"

        pred_disp  = str(result.get("pred",  ""))[:45] or "(empty)"
        truth_disp = str(result.get("truth", ""))[:45] or "(empty)"
        print(f"  {color}{field:<22}{_R} {color}{bar}{_R}  pred: {_GR}{pred_disp}{_R}")
        print(f"  {'':22}       truth: {_GR}{truth_disp}{_R}")

    print(f"\n  {_B}Overall: {_G if overall >= 0.7 else _Y if overall >= 0.4 else _RE}{overall*100:.1f}%{_R}")


# ── Main benchmark loop ──

def run_benchmark(n: int = 5, offline: bool = False):
    hdr(f"UNILOG ACCURACY BENCHMARK  (n={n})")

    truth_index = load_truth()
    products    = load_input(n)

    if not products:
        err("No products found that exist in both input and ground truth CSV.")
        sys.exit(1)

    ok(f"Loaded {len(products)} products for benchmarking")
    ok(f"Ground truth index: {len(truth_index)} products")
    info(f"Mode: {'OFFLINE (local docs only)' if offline else 'ONLINE (web + PDF)'}")

    all_scores: list[dict] = []
    field_totals: dict[str, list[float]] = {}

    for i, inp_row in enumerate(products, 1):
        mpn   = inp_row.get("Mfg_Part_Num", "").strip()
        desc  = inp_row.get("Part_Desc", "").strip()
        manuf = inp_row.get("Part_Manuf", "").strip()

        # Extract brand from Part_Manuf string e.g. "Freud Inc (2435)"
        brand = manuf.split("(")[0].strip() if "(" in manuf else manuf

        truth_row = truth_index.get(mpn, {})

        print(f"\n{_B}{_CY}[{i}/{len(products)}] Running pipeline for {mpn}{_R}")
        info(f"  Brand: {brand}")
        info(f"  Desc:  {desc[:80]}")

        t0    = time.time()
        final = run_pipeline(brand, mpn, desc, offline)
        elapsed = time.time() - t0

        status = final.get("status", "unknown")
        color  = _G if status == "complete" else _Y if status == "needs_review" else _RE
        info(f"  Status: {color}{status}{_R}  ({elapsed:.1f}s)")

        scores = score_product(final, truth_row)

        # Compute overall score for this product
        valid_scores = [r["score"] for r in scores.values() if r.get("score") is not None]
        overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

        print_product_result(mpn, brand, scores, overall)

        for field, result in scores.items():
            if result.get("score") is not None:
                field_totals.setdefault(field, []).append(result["score"])

        all_scores.append({
            "mpn":     mpn,
            "brand":   brand,
            "status":  status,
            "elapsed": round(elapsed, 1),
            "overall": round(overall, 4),
            **{f"score_{k}": round(v["score"], 4) if v.get("score") is not None else None
               for k, v in scores.items()},
        })

    # ── Summary ──
    hdr("BENCHMARK SUMMARY")

    total_overall = sum(r["overall"] for r in all_scores) / len(all_scores) if all_scores else 0

    print(f"\n  {_B}Field-level accuracy:{_R}")
    for field, vals in sorted(field_totals.items()):
        avg = sum(vals) / len(vals)
        color = _G if avg >= 0.75 else _Y if avg >= 0.40 else _RE
        bar_len = int(avg * 30)
        bar = "#" * bar_len + "-" * (30 - bar_len)
        print(f"  {field:<24} {color}[{bar}] {avg*100:.1f}%{_R}")

    print(f"\n  {_B}Overall pipeline accuracy: "
          f"{_G if total_overall >= 0.7 else _Y if total_overall >= 0.4 else _RE}"
          f"{total_overall*100:.1f}%{_R}")

    success = sum(1 for r in all_scores if r["status"] in ("complete", "needs_review"))
    print(f"  {_B}Products completed:{_R} {_G}{success}{_R}/{len(all_scores)}")
    avg_time = sum(r["elapsed"] for r in all_scores) / len(all_scores)
    print(f"  {_B}Avg processing time:{_R} {avg_time:.1f}s per product\n")

    # ── Save results ──
    out_csv  = Path("benchmark_results.csv")
    out_json = Path("benchmark_summary.json")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        if all_scores:
            writer = csv.DictWriter(f, fieldnames=all_scores[0].keys())
            writer.writeheader()
            writer.writerows(all_scores)
    ok(f"Detailed results saved: {out_csv}")

    summary = {
        "run_at":           datetime.now().isoformat(),
        "n_products":       len(all_scores),
        "overall_accuracy": round(total_overall, 4),
        "completed":        success,
        "field_accuracy":   {k: round(sum(v)/len(v), 4) for k, v in field_totals.items()},
        "avg_time_seconds": round(avg_time, 1),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    ok(f"Summary saved: {out_json}")

    print()
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark pipeline accuracy against Unilog ground truth")
    parser.add_argument("--n",       type=int, default=5,     help="Number of products to test (default: 5)")
    parser.add_argument("--offline", action="store_true",      help="Use local reference docs only (no web/API)")
    args = parser.parse_args()

    run_benchmark(n=args.n, offline=args.offline)
