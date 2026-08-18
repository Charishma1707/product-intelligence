"""
interpreter.py — Stage 1 of the pipeline.

Responsibilities:
  - Ask the LLM to classify the product into a LEAF-LEVEL Unilog taxonomy classpath.
  - Look up canonical UNSPSC and attribute list from taxonomy.py.
  - Guarantee "Series" is always the FIRST attribute in expected_fields.
  - Supports OFFLINE_DEMO mode.
  - Falls back to keyword heuristics if LLM fails.

Standalone test:
    cd backend
    python -m pipeline.interpreter
"""

from __future__ import annotations

import json
import logging
import os
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
from pipeline.utils import generate_with_retry, parse_json_response
from pipeline.taxonomy import lookup_taxonomy, get_category_attributes

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic result
# ---------------------------------------------------------------------------

class InterpretResult(BaseModel):
    category: str
    subcategory: str | None
    classpath: str | None
    unspsc: str | None
    expected_fields: list[str]
    used_fallback: bool = False


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a product taxonomy expert for Unilog, a B2B product content platform. "
    "Your job is to classify industrial and consumer products into the Unilog taxonomy "
    "and identify the leaf-level product category. "
    "Output ONLY valid JSON. Never include markdown fences."
)

_USER_PROMPT_TEMPLATE = """\
Product info:
  Brand/Manufacturer: {brand}
  MPN: {mpn}
  Description: {description}

Your task: Classify this product into the Unilog taxonomy hierarchy at LEAF LEVEL.

RULES:
1. classpath must follow EXACTLY: "Top Level > Mid Level > Leaf Node"
   Examples:
     "Hand Tools > Abrasives > Sanding Belts"
     "Hand Tools > Abrasives > Cut-Off Discs"
     "Appliances & Consumer Electronics > Kitchen Appliances > Built-In Dishwashers"
     "Electrical > Motor Controls > Contactors"
     "Plumbing > Faucets & Fixtures > Kitchen Faucets"
   This MUST be a LEAF LEVEL node — as specific as possible.

2. subcategory = the exact leaf node name (last segment of classpath).
   Examples: "Sanding Belts", "Cut-Off Discs", "Built-In Dishwashers"

3. unspsc = 8-digit UNSPSC code closest to the product.
   Abrasives family: 23152000
   Appliances family: 52141500+
   Faucets/Plumbing: 30181500
   Electrical controls: 39121400
   Hand Tools: 27111500

Return ONLY this JSON:
{{
  "category": "<top-level category>",
  "subcategory": "<leaf node name, e.g. Sanding Belts>",
  "classpath": "<Top > Mid > Leaf>",
  "unspsc": "<8-digit code>"
}}
"""


# ---------------------------------------------------------------------------
# Keyword fallback (no LLM needed)
# ---------------------------------------------------------------------------

_KEYWORD_FALLBACKS: list[tuple[list[str], str, str]] = [
    # keywords → subcategory, classpath
    (["sanding belt", "sanding-belt"],
     "Sanding Belts", "Hand Tools > Abrasives > Sanding Belts"),
    (["sanding disc", "sanding disk", "stikit", "film disc"],
     "Sanding Discs", "Hand Tools > Abrasives > Sanding Discs"),
    (["cut-off", "cut off", "cutting wheel", "cutoff"],
     "Cut-Off Discs", "Hand Tools > Abrasives > Cut-Off Discs"),
    (["grinding wheel", "grinding disc"],
     "Grinding Wheels", "Hand Tools > Abrasives > Grinding Wheels"),
    (["flap disc", "flap disk"],
     "Flap Discs", "Hand Tools > Abrasives > Flap Discs"),
    (["abrasive", "abranet", "cubitron", "grit", "hiolit"],
     "Sanding Discs", "Hand Tools > Abrasives > Sanding Discs"),
    (["dishwasher"],
     "Built-In Dishwashers", "Appliances & Consumer Electronics > Kitchen Appliances > Built-In Dishwashers"),
    (["refrigerator", "fridge"],
     "Refrigerators", "Appliances & Consumer Electronics > Kitchen Appliances > Refrigerators"),
    (["washer", "washing machine"],
     "Washing Machines", "Appliances & Consumer Electronics > Laundry Appliances > Washing Machines"),
    (["dryer"],
     "Dryers", "Appliances & Consumer Electronics > Laundry Appliances > Dryers"),
    (["range", "stove", "cooktop"],
     "Ranges", "Appliances & Consumer Electronics > Kitchen Appliances > Ranges"),
    (["microwave"],
     "Microwave Ovens", "Appliances & Consumer Electronics > Kitchen Appliances > Microwave Ovens"),
    (["kitchen faucet"],
     "Kitchen Faucets", "Plumbing > Faucets & Fixtures > Kitchen Faucets"),
    (["bathroom faucet", "bath faucet", "lavatory faucet"],
     "Bathroom Faucets", "Plumbing > Faucets & Fixtures > Bathroom Faucets"),
    (["faucet"],
     "Faucets", "Plumbing > Faucets & Fixtures > Faucets"),
    (["pipe fitting", "brass fitting", "pipe coupling"],
     "Pipe Fittings", "Plumbing > Pipe Fittings > Pipe Fittings"),
    (["ball valve"],
     "Ball Valves", "Plumbing > Valves > Ball Valves"),
    (["contactor"],
     "Contactors", "Electrical > Motor Controls > Contactors"),
    (["circuit breaker"],
     "Circuit Breakers", "Electrical > Electrical Distribution > Circuit Breakers"),
    (["ball bearing", "deep groove", "bearing"],
     "Ball Bearings", "Mechanical Components > Bearings > Ball Bearings"),
    (["proximity sensor", "inductive sensor"],
     "Proximity Sensors", "Electrical > Sensors > Proximity Sensors"),
    (["limit switch"],
     "Limit Switches", "Electrical > Sensors > Limit Switches"),
    (["drill bit"],
     "Drill Bits", "Hand Tools > Drilling & Boring > Drill Bits"),
    (["saw blade"],
     "Saw Blades", "Hand Tools > Cutting Tools > Saw Blades"),
    (["safety glasses", "safety spectacle"],
     "Safety Glasses", "Safety > Eye & Face Protection > Safety Glasses"),
    (["hard hat", "safety helmet"],
     "Hard Hats", "Safety > Head Protection > Hard Hats"),
]


def _keyword_classify(brand: str, mpn: str, description: str) -> tuple[str, str] | None:
    """
    Match product text against keyword fallback list.
    Returns (subcategory, classpath) or None.
    """
    text = (brand + " " + mpn + " " + description).lower()
    for keywords, subcategory, classpath in _KEYWORD_FALLBACKS:
        for kw in keywords:
            if kw in text:
                return subcategory, classpath
    return None


def _clean_manufacturer_from_partmanuf(part_manuf: str) -> str:
    """Strip distributor codes like '(2435)' from Part_Manuf field."""
    # Remove trailing (CODE) or (ALPHA) patterns
    clean = re.sub(r"\s*\([^)]*\)\s*$", "", part_manuf).strip()
    return clean


import re


# ---------------------------------------------------------------------------
# Main interpret function
# ---------------------------------------------------------------------------

def interpret(
    brand: str,
    mpn: str,
    description: str,
    provided_schema: list[str] | None = None,
    strict_schema: bool = False,
) -> InterpretResult:
    """
    Stage 1: Determine product category, classpath, UNSPSC, and expected spec fields.

    Strategy:
    1. Try keyword-based classification first (fast, zero API cost, reliable)
    2. Fall back to LLM if keyword match fails
    3. Look up canonical attributes from taxonomy.py (always Series first)
    4. Override with provided_schema if given
    """
    offline = os.getenv("OFFLINE_DEMO", "false").lower() == "true"

    subcategory: str | None = None
    classpath: str | None = None
    unspsc: str | None = None
    used_fallback = False

    # ── Step 1: Keyword classification ──────────────────────────────────────
    kw_result = _keyword_classify(brand, mpn, description)
    if kw_result:
        subcategory, classpath = kw_result
        logger.info("[Interpreter] Keyword match → %s / %s", subcategory, classpath)
    elif not offline:
        # ── Step 2: LLM classification ───────────────────────────────────────
        prompt = _USER_PROMPT_TEMPLATE.format(brand=brand, mpn=mpn, description=description)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        try:
            raw = generate_with_retry(
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.05,
            )
            data = parse_json_response(raw)
            subcategory = data.get("subcategory")
            classpath = data.get("classpath")
            unspsc = data.get("unspsc")
            logger.info("[Interpreter] LLM → subcategory=%s classpath=%s unspsc=%s",
                        subcategory, classpath, unspsc)
        except Exception as e:
            logger.warning("[Interpreter] LLM classification failed: %s — using generic fallback", e)
            used_fallback = True

    # ── Step 3: Taxonomy lookup for UNSPSC + canonical classpath ────────────
    if subcategory or classpath:
        hint = f"{subcategory or ''} {classpath or ''} {description}"
        tax_classpath, tax_unspsc = lookup_taxonomy(hint)
        # Only use taxonomy result for UNSPSC if LLM didn't provide one
        if not unspsc or unspsc == "00000000":
            unspsc = tax_unspsc
        # Use taxonomy classpath if LLM didn't provide one
        if not classpath:
            classpath = tax_classpath
    else:
        # Full fallback
        classpath, unspsc = lookup_taxonomy(description)
        subcategory = classpath.split(">")[-1].strip() if classpath else "General"
        used_fallback = True

    # ── Step 4: Build expected fields from canonical attribute list ──────────
    if strict_schema and provided_schema:
        # User override — honour exactly, but guarantee Series first
        fields = provided_schema
        if "series" not in [f.lower() for f in fields]:
            fields = ["series"] + fields
        elif fields[0].lower() != "series":
            fields = ["series"] + [f for f in fields if f.lower() != "series"]
    else:
        # Get canonical attributes for this leaf category
        raw_attrs = get_category_attributes(
            subcategory or "Default",
            description
        )
        # Convert to snake_case for internal field names
        fields = [_to_snake(a) for a in raw_attrs]

        # Merge in provided_schema extras
        if provided_schema:
            for extra in provided_schema:
                if extra not in fields:
                    fields.append(extra)

    # Guarantee "series" is always first
    if "series" not in fields:
        fields = ["series"] + fields
    elif fields[0] != "series":
        fields = ["series"] + [f for f in fields if f != "series"]

    # Derive top-level category from classpath
    category = classpath.split(">")[0].strip() if classpath else "Industrial Products"

    logger.info(
        "[Interpreter] Done — category=%s subcategory=%s classpath=%s unspsc=%s fields=%d",
        category, subcategory, classpath, unspsc, len(fields)
    )

    return InterpretResult(
        category=category,
        subcategory=subcategory,
        classpath=classpath,
        unspsc=unspsc,
        expected_fields=fields,
        used_fallback=used_fallback,
    )


def _to_snake(label: str) -> str:
    """Convert 'Number Of Wash Cycles' → 'number_of_wash_cycles'."""
    return re.sub(r"[\s\-/]+", "_", label.strip().lower()).strip("_")


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pprint
    logging.basicConfig(level=logging.INFO)

    test_products = [
        ("Freud", "DCB518ASTS06G", "Diablo 1/2\"x18\" - Sanding Belt 6pc"),
        ("3M", "7100075678", "3M 775L Stikit Film P150 - Cubitron II 50 Disc/Box"),
        ("Freud", "DBD090094101F", "Diablo 9\" - Metal Cut-Off Disc"),
        ("Appliance Dealers", "PDSH4816AF", "PDSH4816AF Dishwasher SS - Display Only"),
    ]

    for brand, mpn, desc in test_products:
        print(f"\n--- {brand} {mpn} ---")
        result = interpret(brand, mpn, desc)
        print(f"  classpath:    {result.classpath}")
        print(f"  subcategory:  {result.subcategory}")
        print(f"  unspsc:       {result.unspsc}")
        print(f"  fields[0]:    {result.expected_fields[0]}")
        print(f"  all_fields:   {result.expected_fields[:8]}...")

    print("\n[PASS] interpreter.py standalone test complete.")
