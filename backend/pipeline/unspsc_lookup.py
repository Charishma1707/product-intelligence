"""
unspsc_lookup.py — UNSPSC code lookup table and brand normalization.

UNSPSC (United Nations Standard Products and Services Code) is an 8-digit
hierarchical code used in B2B procurement. This module provides:
  1. Category → UNSPSC code mapping for the most common industrial categories.
  2. Brand name normalization (strips distributor codes like "(2435)").
"""

from __future__ import annotations
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UNSPSC lookup: category keywords → 8-digit code
# ---------------------------------------------------------------------------

UNSPSC_MAP: dict[str, str] = {
    # Bearings
    "bearing": "31171500",
    "ball bearing": "31171501",
    "roller bearing": "31171504",
    "thrust bearing": "31171505",

    # Electrical / Switchgear
    "contactor": "39121401",
    "relay": "39121410",
    "circuit breaker": "39121101",
    "fuse": "39121301",
    "switch": "39121200",

    # Motors / Drives
    "motor": "26101500",
    "servo motor": "26101511",
    "stepper motor": "26101512",
    "variable frequency drive": "26111607",
    "vfd": "26111607",
    "inverter": "26111607",

    # Sensors / Instrumentation
    "sensor": "41112200",
    "proximity sensor": "41112218",
    "pressure sensor": "41115500",
    "temperature sensor": "41111700",
    "limit switch": "39121208",
    "encoder": "41115800",

    # Pneumatics / Hydraulics
    "valve": "40141600",
    "pneumatic cylinder": "40142200",
    "hydraulic pump": "40151700",
    "solenoid valve": "40141607",

    # Fasteners / Hardware
    "bolt": "31161501",
    "nut": "31161600",
    "screw": "31161700",
    "washer": "31161800",

    # Abrasives / Tools
    "sanding belt": "27112800",
    "abrasive": "27112800",
    "grinding wheel": "27112801",
    "drill bit": "27111501",

    # Appliances
    "dishwasher": "52141501",
    "washing machine": "52141601",
    "refrigerator": "52141200",
    "air conditioner": "40101700",

    # Cables / Wiring
    "cable": "26121600",
    "wire": "26121500",
    "connector": "39121400",

    # Lighting
    "led": "39111400",
    "lamp": "39111500",
    "bulb": "39111500",

    # Power Supplies / Batteries
    "power supply": "26111601",
    "battery": "26111700",
    "ups": "39121700",

    # Pumps / Compressors
    "pump": "40151500",
    "compressor": "40151900",

    # Safety / PPE
    "helmet": "46181501",
    "glove": "46181504",
    "safety": "46000000",

    # Generic fallback
    "industrial": "31000000",
}


def lookup_unspsc(brand: str, mpn: str, description: str, category: str) -> str | None:
    """
    Look up UNSPSC code by matching category/description keywords.
    Returns 8-digit string code or None if not found.
    """
    combined = (description + " " + category + " " + mpn).lower()
    # Try longest match first
    for keyword in sorted(UNSPSC_MAP.keys(), key=len, reverse=True):
        if keyword in combined:
            code = UNSPSC_MAP[keyword]
            logger.info("[UNSPSC] Matched '%s' → %s", keyword, code)
            return code
    return None


# ---------------------------------------------------------------------------
# Brand normalization
# ---------------------------------------------------------------------------

# Known brand cleanup rules: raw → clean name
BRAND_OVERRIDES: dict[str, str] = {
    "-- unbranded --": "Unbranded",
    "-- no unilog brand --": "Unbranded",
    "-- no dib brand --": "Unbranded",
    "freud inc": "Freud",
    "jam industrial supply llc": "3M",
    "mirka abrasives inc": "Mirka",
    "appliance dealers cooperative": "ADE",
}


def normalize_brand(raw_brand: str, raw_manuf: str = "") -> tuple[str, str]:
    """
    Returns (cleaned_brand_name, cleaned_manufacturer_name).
    Strips distributor codes like '(2435)' or '(JAMIN)' from manufacturer strings.
    """
    def _clean(s: str) -> str:
        # Remove parenthesized codes like "(2435)" or "(APPDE)"
        s = re.sub(r"\s*\([^)]+\)\s*", "", s).strip()
        return s

    brand_lower = raw_brand.strip().lower()
    manuf_lower = raw_manuf.strip().lower()

    # Check overrides for brand
    for k, v in BRAND_OVERRIDES.items():
        if k in brand_lower:
            return v, _clean(raw_manuf) or v

    # Check overrides for manufacturer
    for k, v in BRAND_OVERRIDES.items():
        if k in manuf_lower:
            return _clean(raw_brand) or v, v

    return _clean(raw_brand) or raw_brand, _clean(raw_manuf) or raw_manuf


if __name__ == "__main__":
    print(lookup_unspsc("SKF", "6205-2RS1", "Deep Groove Ball Bearing", "Bearings"))
    print(normalize_brand("-- Unbranded --", "Freud Inc (2435)"))
    print(normalize_brand("3M", "Jam Industrial Supply LLC (JAMIN)"))
