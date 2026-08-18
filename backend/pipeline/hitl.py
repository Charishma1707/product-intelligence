"""
pipeline/hitl.py — Human-in-the-Loop (HITL) review terminal UI.

After the pipeline runs, shows a colored table of ALL extracted fields.
The human can review and override any low-confidence values before
they are written to the CSV and stored in the database.

Color coding (NO icons):
  GREEN  — high confidence (≥ 80%), auto-approved
  YELLOW — low confidence (< 80%), flagged for review
  RED    — field not found at all
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Force UTF-8 stdout for Windows consoles to prevent cp1252 crash on bullet points
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ─────────────────────────────────────────────────────────────
# ANSI color codes
# ─────────────────────────────────────────────────────────────
_R  = "\033[0m"       # reset
_B  = "\033[1m"       # bold
_G  = "\033[32m"      # green  — confirmed high confidence
_Y  = "\033[33m"      # yellow — low confidence, needs review
_RE = "\033[31m"      # red    — not found
_CY = "\033[36m"      # cyan   — header
_GR = "\033[90m"      # gray   — divider / secondary info
_WH = "\033[37m"      # white
_BG_Y = "\033[43m"    # yellow background — for flagged header
_BG_G = "\033[42m"    # green background  — for approved header


def _col_green(text: str) -> str:  return f"{_G}{text}{_R}"
def _col_yellow(text: str) -> str: return f"{_Y}{text}{_R}"
def _col_red(text: str) -> str:    return f"{_RE}{text}{_R}"
def _col_cyan(text: str) -> str:   return f"{_CY}{text}{_R}"
def _col_gray(text: str) -> str:   return f"{_GR}{text}{_R}"
def _bold(text: str) -> str:       return f"{_B}{text}{_R}"


def print_extraction_table(job_id: str, brand: str, mpn: str, specs: dict) -> None:
    """
    Print a beautiful colored table of ALL extracted fields with:
    - Field name
    - Extracted value
    - Confidence percentage
    - Source URL or method
    - Raw snippet

    GREEN  = high confidence (auto-approved)
    YELLOW = low confidence (flagged for review)
    RED    = not found
    """
    print(f"\n{_B}{_CY}{'='*80}{_R}")
    print(f"{_B}{_CY}  EXTRACTION RESULTS  —  {brand} {mpn}{_R}")
    print(f"{_B}{_CY}  Job ID: {_GR}{job_id}{_R}")
    print(f"{_B}{_CY}{'='*80}{_R}")

    # Column widths
    W_FIELD = 28
    W_VALUE = 22
    W_CONF  = 8
    W_SRC   = 18

    header = (
        f"  {_bold('Field'.ljust(W_FIELD))}"
        f"  {_bold('Value'.ljust(W_VALUE))}"
        f"  {_bold('Conf'.ljust(W_CONF))}"
        f"  {_bold('Source')}"
    )
    print(f"\n{header}")
    print(f"  {_GR}{'-'*76}{_R}")

    green_count  = 0
    yellow_count = 0
    red_count    = 0
    flagged_fields: list[tuple] = []

    # Sort: high conf first, then low conf, then missing
    def sort_key(item):
        fname, fv = item
        if isinstance(fv, dict):
            return -(fv.get("confidence", 0) or 0)
        if hasattr(fv, "confidence"):
            return -(fv.confidence or 0)
        return 1

    sorted_specs = sorted(specs.items(), key=sort_key)

    for fname, fv in sorted_specs:
        # Normalize to dict
        if hasattr(fv, "model_dump"):
            fv = fv.model_dump()
        elif not isinstance(fv, dict):
            fv = {}

        val    = fv.get("value")
        conf   = fv.get("confidence") or 0.0
        method = fv.get("method", "unknown")
        cit    = fv.get("citation") or {}
        if isinstance(cit, dict):
            src_url = cit.get("url") or ""
            snippet = cit.get("snippet") or ""
        else:
            src_url = ""
            snippet = ""

        # Format display values
        val_str = str(val)[:45] if val is not None else "[Missing]"
        val_str = val_str.replace("\n", " ").encode("ascii", errors="ignore").decode("ascii")

        field_str = fname[:W_FIELD].ljust(W_FIELD)
        conf_str  = f"{int(conf*100)}%" if val is not None else "   -"
        src_str   = ""
        if method == "inferred":
            src_str = "AI inferred"
        elif src_url:
            # Show just the domain
            try:
                from urllib.parse import urlparse
                src_str = urlparse(src_url).netloc[:W_SRC] or src_url[:W_SRC]
            except Exception:
                src_str = src_url[:W_SRC]
        else:
            src_str = method[:W_SRC]

        if val is None:
            # RED — not found
            line = (
                f"  {_col_red(field_str)}"
                f"  {_col_gray(val_str.ljust(W_VALUE))}"
                f"  {_col_gray(conf_str.ljust(W_CONF))}"
                f"  {_col_gray(src_str)}"
            )
            red_count += 1
        elif conf >= 0.80:
            # GREEN — high confidence
            line = (
                f"  {_col_green(field_str)}"
                f"  {val_str.ljust(W_VALUE)}"
                f"  {_col_green(conf_str.ljust(W_CONF))}"
                f"  {_col_gray(src_str)}"
            )
            green_count += 1
        else:
            # YELLOW — low confidence, needs review
            line = (
                f"  {_col_yellow(field_str)}"
                f"  {_col_yellow(val_str.ljust(W_VALUE))}"
                f"  {_col_yellow(conf_str.ljust(W_CONF))}"
                f"  {_col_gray(src_str)}"
            )
            yellow_count += 1
            flagged_fields.append((fname, val, conf, snippet, src_url))

        print(line)

        # Print snippet on next line if available
        if snippet and val is not None:
            snippet_clean = snippet.replace("\n", " ")
            if len(snippet_clean) > 75:
                snippet_clean = snippet_clean[:72] + "..."
            snippet_safe = snippet_clean.encode("ascii", errors="ignore").decode("ascii")
            print(f"  {_col_gray('    Evidence: ' + repr(snippet_safe))}")

    print(f"\n  {_GR}{'-'*76}{_R}")
    print(f"\n  {_B}Summary:{_R}  "
          f"{_col_green(f'{green_count} confirmed')}   "
          f"{_col_yellow(f'{yellow_count} flagged')}   "
          f"{_col_red(f'{red_count} not found')}")

    return flagged_fields


def run_hitl_review(job_id: str, brand: str, mpn: str, specs: dict) -> dict:
    """
    Interactive HITL terminal review.
    
    Shows all flagged (yellow) fields and asks the human to:
      - Press ENTER to accept the AI value
      - Type a new value to override it
      - Type 'skip' to exclude this field from the output

    Returns a dict of overrides: {field_name: new_value or None}
    """
    flagged_fields = print_extraction_table(job_id, brand, mpn, specs)

    if not flagged_fields:
        print(f"\n  {_col_green('All fields have high confidence. No review needed.')}\n")
        return {}

    print(f"\n{_B}{_BG_Y}  HUMAN REVIEW REQUIRED  {_R}")
    print(f"  {_col_yellow(str(len(flagged_fields)))} fields have low confidence and need your review.")
    _hint = 'Press ENTER to accept, type a value to override, or type "skip" to exclude.'
    print(f"  {_col_gray(_hint)}\n")

    overrides: dict[str, Any] = {}

    for fname, current_val, conf, snippet, src_url in flagged_fields:
        print(f"  {_col_yellow(_bold(fname))}  {_col_gray(f'[confidence: {conf*100:.0f}%]')}")
        if snippet:
            snip_preview = snippet[:100]
            print(f"  {_col_gray('  Evidence: ' + repr(snip_preview))}")
        if src_url:
            print(f"  {_col_gray(f'  Source:   {src_url}')}")

        prompt_str = f"  Current value: {_col_yellow(str(current_val))}  > "
        try:
            user_input = input(prompt_str).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {_col_gray('Review cancelled — using AI values.')}")
            break

        if user_input == "":
            # Accept AI value
            overrides[fname] = current_val
            print(f"  {_col_green('Accepted.')}\n")
        elif user_input.lower() == "skip":
            # Exclude field
            overrides[fname] = None
            print(f"  {_col_red('Excluded from output.')}\n")
        else:
            overrides[fname] = user_input
            print(f"  {_col_green(f'Overridden to: {user_input}')}\n")

    return overrides


def apply_overrides(specs: dict, overrides: dict) -> dict:
    """
    Apply human overrides to the specs dict.
    - If override value is None → remove the field
    - Otherwise → update the value and set confidence to 1.0 (human-verified)
    """
    for fname, new_val in overrides.items():
        if fname not in specs:
            continue
        fv = specs[fname]
        if hasattr(fv, "model_dump"):
            fv = fv.model_dump()

        if new_val is None:
            del specs[fname]
        else:
            if isinstance(specs[fname], dict):
                specs[fname]["value"] = new_val
                specs[fname]["confidence"] = 1.0
                specs[fname]["method"] = "human_verified"
            else:
                specs[fname].value = new_val
                if hasattr(specs[fname], "confidence"):
                    specs[fname].confidence = 1.0
                if hasattr(specs[fname], "method"):
                    specs[fname].method = "human_verified"
    return specs


def save_hitl_result(job_id: str, specs: dict, overrides: dict, output_dir: Path) -> Path:
    """
    Save the HITL review result as a JSON file in the outputs directory.
    Format is human-readable and includes all provenance.
    """
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / f"hitl_{job_id}.json"

    result = {
        "job_id": job_id,
        "hitl_overrides": overrides,
        "fields": {}
    }
    for fname, fv in specs.items():
        if hasattr(fv, "model_dump"):
            fv = fv.model_dump()
        result["fields"][fname] = fv

    with open(out_file, "w") as f:
        json.dump(result, f, indent=2, default=str)

    return out_file
