"""
interpreter.py — Stage 1 of the pipeline.

Responsibilities:
  - Ask the LLM to classify the product into a LEAF-LEVEL Unilog taxonomy classpath AND deduce required attributes.
  - Check the local knowledge_store cache to reuse taxonomy decisions.
  - Guarantee "Series" is always the FIRST attribute in expected_fields.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
from pipeline.utils import generate_with_retry, parse_json_response
from pipeline.knowledge_store import get_category_cache, save_category_cache, get_canonical_brand, save_brand_alias

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

logger = logging.getLogger(__name__)

class InterpretResult(BaseModel):
    true_manufacturer: str
    true_brand: str
    category: str
    subcategory: str | None
    classpath: str | None
    unspsc: str | None
    expected_fields: list[str]
    used_fallback: bool = False

_SYSTEM_PROMPT = (
    "You are a product taxonomy expert for Unilog, a B2B product content platform. "
    "Your job is to classify industrial and consumer products into the Unilog taxonomy, "
    "identify the true OEM manufacturer (in case the input is a distributor), "
    "and identify ALL essential technical attributes required for this category. "
    "Output ONLY valid JSON. Never include markdown fences."
)

_USER_PROMPT_TEMPLATE = """\
Product info:
  Input Manufacturer/Brand String: {brand}
  MPN: {mpn}
  Description: {description}

Your task: 
1. Determine the TRUE OEM manufacturer and brand. The 'Input Manufacturer/Brand String' might actually be a distributor name (like 'Appliance Dealers Cooperative' or 'Fastenal'). Figure out the true OEM brand (e.g., 'Frigidaire', 'DeWalt').
2. Classify this product into the Unilog taxonomy hierarchy at LEAF LEVEL.
3. Determine ALL essential technical attributes (like Voltage, Grit, Diameter, Material, etc.) required to fully enrich this specific leaf category. DO NOT include generic fields like Description, MPN, Brand, or URL. Focus on technical specs.

RULES:
1. classpath must follow EXACTLY: "Top Level > Mid Level > Leaf Node"
2. subcategory = the exact leaf node name (last segment of classpath).
3. unspsc = 8-digit UNSPSC code closest to the product.
4. expected_fields = array of strings representing ALL required attribute labels. "Series" must be the first item.

Return ONLY this JSON:
{{
  "true_manufacturer": "<true OEM manufacturer name>",
  "true_brand": "<true OEM brand name>",
  "category": "<top-level category>",
  "subcategory": "<leaf node name, e.g. Sanding Belts>",
  "classpath": "<Top > Mid > Leaf>",
  "unspsc": "<8-digit code>",
  "expected_fields": ["Series", "Attribute 2", "Attribute 3"]
}}
"""

def _clean_manufacturer_from_partmanuf(part_manuf: str) -> str:
    """Return raw part_manuf without stripping ()"""
    return part_manuf.strip()

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
    1. Try LLM classification first, which will also deduce the required fields.
    2. Cache the result by 'subcategory' so future products of the same type skip the attribute generation.
    3. Override with provided_schema if given.
    """
    clean_manuf = _clean_manufacturer_from_partmanuf(brand)
    cached_brand = get_canonical_brand(clean_manuf)
    
    true_manufacturer = cached_brand or clean_manuf
    true_brand = cached_brand or brand
    subcategory: str | None = None
    classpath: str | None = None
    unspsc: str | None = None
    expected_fields: list[str] = []
    used_fallback = False
    offline = os.getenv("OFFLINE_MODE", "false").lower() == "true"
    if not offline:
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
            
            llm_manufacturer = data.get("true_manufacturer")
            llm_brand = data.get("true_brand")
            
            if llm_manufacturer and not cached_brand:
                true_manufacturer = llm_manufacturer
                if llm_manufacturer.lower() != clean_manuf.lower():
                    logger.info("[Interpreter] LLM resolved brand '%s' -> '%s'", clean_manuf, llm_manufacturer)
                    save_brand_alias(clean_manuf, llm_manufacturer)
            
            if llm_brand and not cached_brand:
                true_brand = llm_brand
            elif cached_brand:
                true_brand = cached_brand
                true_manufacturer = cached_brand
            
            # Check cache if we already know this subcategory's schema
            if subcategory:
                cached = get_category_cache(subcategory)
                if cached:
                    logger.info("[Interpreter] Cache hit for category: %s", subcategory)
                    classpath = cached["classpath"]
                    unspsc = cached["unspsc"]
                    expected_fields = cached["expected_fields"]
                else:
                    logger.info("[Interpreter] Cache miss for category: %s. Using LLM generated schema.", subcategory)
                    classpath = data.get("classpath")
                    unspsc = data.get("unspsc")
                    expected_fields = data.get("expected_fields", [])
                    # Save to cache
                    save_category_cache(subcategory, classpath or "Unknown", unspsc or "00000000", expected_fields)
            else:
                classpath = data.get("classpath")
                unspsc = data.get("unspsc")
                expected_fields = data.get("expected_fields", [])
                
            logger.info("[Interpreter] LLM → true_mfr=%s subcategory=%s classpath=%s unspsc=%s",
                        true_manufacturer, subcategory, classpath, unspsc)
        except Exception as e:
            logger.warning("[Interpreter] LLM classification failed: %s", e)
            used_fallback = True

    if not classpath:
        classpath = "Industrial Products > General > Miscellaneous"
        subcategory = "Miscellaneous"
        unspsc = "00000000"
        expected_fields = ["Series", "Material", "Color", "Size"]
        used_fallback = True

    # Convert to snake_case for internal field names
    fields = [_to_snake(a) for a in expected_fields]

    if strict_schema and provided_schema:
        fields = provided_schema

    if provided_schema and not strict_schema:
        for extra in provided_schema:
            if extra not in fields:
                fields.append(extra)

    # Guarantee "series" is always first
    if "series" not in fields:
        fields = ["series"] + fields
    elif fields[0] != "series":
        fields = ["series"] + [f for f in fields if f != "series"]

    category = classpath.split(">")[0].strip() if classpath else "Industrial Products"

    logger.info(
        "[Interpreter] Done — category=%s subcategory=%s classpath=%s unspsc=%s fields=%d",
        category, subcategory, classpath, unspsc, len(fields)
    )

    return InterpretResult(
        true_manufacturer=true_manufacturer,
        true_brand=true_brand,
        category=category,
        subcategory=subcategory,
        classpath=classpath,
        unspsc=unspsc,
        expected_fields=fields,
        used_fallback=used_fallback,
    )

def _to_snake(label: str) -> str:
    return re.sub(r"[\s\-/]+", "_", label.strip().lower()).strip("_")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from pipeline.knowledge_store import init_db
    init_db()
    result = interpret("Freud", "DCB518ASTS06G", 'Diablo 1/2"x18" - Sanding Belt 6pc')
    print(result.model_dump_json(indent=2))
