"""
pipeline/desc_abbr_dict.py — Regex-based abbreviation expansion dictionary.

Built from systematic analysis of real Part_Desc values in:
    Unihack_ Sample Dataset - Input.csv

Pattern format (DESC_ABBR_MAP):
  key   = regex pattern string (used with re.search, re.IGNORECASE)
  value = dict:
    field          — target spec field name (snake_case)
    value          — canonical value; use {1}, {2} for capture groups
    abbr_label     — human-readable abbreviation label for UI display
    uom_field      — (optional) companion UOM field name
    uom_value      — (optional) companion UOM canonical value

Usage:
    from pipeline.desc_abbr_dict import DESC_ABBR_MAP, load_db_abbreviations, BRAND_SHORTCODES
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Primary abbreviation → field mapping
# ---------------------------------------------------------------------------

DESC_ABBR_MAP: dict[str, dict] = {

    # ── COLOR / FINISH ──────────────────────────────────────────────────────
    r"\b(?:WH|Wht)\b":          {"field": "color",    "value": "White",              "abbr_label": "Wh"},
    r"\bWhite\b":               {"field": "color",    "value": "White",              "abbr_label": "White"},
    r"\b(?:BK|Blk)\b":         {"field": "color",    "value": "Black",              "abbr_label": "Bk"},
    r"\bBlack\b":               {"field": "color",    "value": "Black",              "abbr_label": "Black"},
    r"\bDG\b":                  {"field": "color",    "value": "Dark Gray",          "abbr_label": "DG"},
    r"\bLA\b":                  {"field": "color",    "value": "Light Almond",       "abbr_label": "LA"},

    # Materials
    r"\b(?:SS|SST|S/S)\b":     {"field": "material", "value": "Stainless Steel",    "abbr_label": "SS"},
    r"\bBSS\b":                 {"field": "material", "value": "Black Stainless Steel","abbr_label": "BSS"},
    r"\b(?:BRS|BRASS)\b":      {"field": "material", "value": "Brass",              "abbr_label": "BRS"},
    r"\b(?:GI|GALV|Galv)\b":   {"field": "material", "value": "Galvanized Iron",    "abbr_label": "GI"},
    r"\bAlum\b|\bAluminum\b":  {"field": "material", "value": "Aluminum",           "abbr_label": "Alum"},
    r"\bPVC\b":                 {"field": "material", "value": "PVC",                "abbr_label": "PVC"},

    # Finish & Color with MPN suffix support
    r"(?<=\d)NI\b|\bNI\b|\bNickel\b":      {"field": "finish",   "value": "Nickel",             "abbr_label": "NI"},
    r"(?<=\d)BN\b|\bBN\b":                  {"field": "finish",   "value": "Brushed Nickel",     "abbr_label": "BN"},
    r"(?<=\d)CH\b|\b(?:CH|Chr)\b|\bChrome\b": {"field": "finish", "value": "Chrome",            "abbr_label": "CH"},
    r"(?<=\d)CPZ\b|\bCPZ\b":                {"field": "finish",   "value": "Champagne Bronze",   "abbr_label": "CPZ"},
    r"(?<=\d)DBZ\b|\b(?:DBZ|DBrz)\b":      {"field": "finish",   "value": "Dark Bronze",        "abbr_label": "DBZ"},
    r"(?<=\d)BK\b|\b(?:BK|Blk)\b":         {"field": "color",    "value": "Black",              "abbr_label": "Bk"},
    r"(?<=\d)WH\b|\b(?:WH|Wht)\b":         {"field": "color",    "value": "White",              "abbr_label": "Wh"},
    r"\bBlack\b":                           {"field": "color",    "value": "Black",              "abbr_label": "Black"},
    r"\bWhite\b":                           {"field": "color",    "value": "White",              "abbr_label": "White"},
    r"\bAVI\b":                             {"field": "finish",   "value": "Anvil Iron",         "abbr_label": "AVI"},
    r"\bCLR\b|\bClr\b":                    {"field": "lens_type","value": "Clear",              "abbr_label": "CLR"},

    # ── POWER / FUEL TYPE ───────────────────────────────────────────────────
    r"\b(?:Elect|Elec)\b|\bElectric\b": {"field": "fuel_type", "value": "Electric", "abbr_label": "Elect"},
    r"\bGas\b|\bNG\b":          {"field": "fuel_type","value": "Gas",               "abbr_label": "Gas"},

    # ── ELECTRICAL SPECS ────────────────────────────────────────────────────
    r"(\d+)\s*V\b":             {"field": "voltage",  "value": "{1}",               "abbr_label": "{1}V",
                                 "uom_field": "voltage_uom", "uom_value": "V"},
    r"(\d+(?:\.\d+)?)\s*W\b":  {"field": "wattage",  "value": "{1}",               "abbr_label": "{1}W",
                                 "uom_field": "wattage_uom", "uom_value": "W"},
    r"(\d+(?:\.\d+)?)\s*(?:A|Amps?)\b": {"field": "amperage","value": "{1}",        "abbr_label": "{1}A",
                                 "uom_field": "amperage_uom","uom_value": "A"},
    r"(\d+)\s*Hz\b":            {"field": "frequency","value": "{1}",               "abbr_label": "{1}Hz",
                                 "uom_field": "freq_uom",    "uom_value": "Hz"},
    r"\b1PH\b|\bSingle\s*Phase\b": {"field": "phase","value": "1",                  "abbr_label": "1PH"},
    r"\b3PH\b|\bThree\s*Phase\b":  {"field": "phase","value": "3",                  "abbr_label": "3PH"},
    r"(\d+)\s*AH\b":            {"field": "battery_capacity","value": "{1}",         "abbr_label": "{1}AH",
                                 "uom_field": "battery_capacity_uom", "uom_value": "AH"},

    # ── LIGHT COLOR TEMPERATURE (27K, 30K, 40K, 45K, 50K, CCT, 5CCT) ───────
    r"\b27[Kk]\b":              {"field": "color_temperature","value": "2700",       "abbr_label": "27K",
                                 "uom_field": "color_temp_uom","uom_value": "K"},
    r"\b30[Kk]\b":              {"field": "color_temperature","value": "3000",       "abbr_label": "30K",
                                 "uom_field": "color_temp_uom","uom_value": "K"},
    r"\b40[Kk]\b":              {"field": "color_temperature","value": "4000",       "abbr_label": "40K",
                                 "uom_field": "color_temp_uom","uom_value": "K"},
    r"\b45[Kk]\b":              {"field": "color_temperature","value": "4500",       "abbr_label": "45K",
                                 "uom_field": "color_temp_uom","uom_value": "K"},
    r"\b50[Kk]\b":              {"field": "color_temperature","value": "5000",       "abbr_label": "50K",
                                 "uom_field": "color_temp_uom","uom_value": "K"},
    r"\b20[Kk]\b":              {"field": "color_temperature","value": "2000",       "abbr_label": "20K",
                                 "uom_field": "color_temp_uom","uom_value": "K"},
    r"\b21[Kk]\b":              {"field": "color_temperature","value": "2100",       "abbr_label": "21K",
                                 "uom_field": "color_temp_uom","uom_value": "K"},
    r"\b(?:5CCT|Multi\s*CCT|CCT)\b": {"field": "color_temperature","value": "Tunable CCT", "abbr_label": "CCT"},

    # ── LIGHT TECHNOLOGY (Led, Incan, Flor, Halogen, Sodium) ────────────────
    r"\b(?:Led|LED)\b":         {"field": "light_technology","value": "LED",         "abbr_label": "LED"},
    r"\b(?:Incan|Incandescent)\b": {"field": "light_technology","value": "Incandescent","abbr_label": "Incan"},
    r"\b(?:Flor|Fluorescent)\b":   {"field": "light_technology","value": "Fluorescent","abbr_label": "Flor"},
    r"\bHalogen\b":             {"field": "light_technology","value": "Halogen",      "abbr_label": "Halogen"},
    r"\bSodium\b":              {"field": "light_technology","value": "High Pressure Sodium","abbr_label": "Sodium"},

    # ── ABRASIVE GRIT (P80, P120, P150, P180, P220, P320, 220 Grit) ─────────
    r"\bP(\d{2,3})\b":          {"field": "grit",     "value": "{1}",               "abbr_label": "P{1}"},
    r"(\d{2,3})\s*Grit\b":      {"field": "grit",     "value": "{1}",               "abbr_label": "{1} Grit"},

    # ── DIMENSIONS / SIZES ───────────────────────────────────────────────────
    r"(\d+(?:[/-]\d+)?)[\"']\b|\b(\d+(?:\.\d+)?)\s*in\b":
                                {"field": "size",     "value": "{1}",               "abbr_label": "{1}\"",
                                 "uom_field": "size_uom","uom_value": "in"},

    # ── QUANTITY / PACK SIZES (50 Disc/Box, 6pc, 10pc, 2pk, 3pk, 4pk) ───────
    r"(\d+)\s*(?:pc|Pcs?)\b":   {"field": "selling_qty","value": "{1}",             "abbr_label": "{1}pc",
                                 "uom_field": "selling_uom","uom_value": "EA"},
    r"(\d+)\s*(?:Pack?|pk)\b":  {"field": "selling_qty","value": "{1}",             "abbr_label": "{1}pk",
                                 "uom_field": "selling_uom","uom_value": "PK"},
    r"(\d+)\s*(?:Disc|Discs?)/(?:Box|Bx)\b":
                                {"field": "selling_qty","value": "{1}",             "abbr_label": "{1} Disc/Box",
                                 "uom_field": "selling_uom","uom_value": "BX"},

    # ── MOUNT / INSTALL TYPE ─────────────────────────────────────────────────
    r"\bWall\s*(?:Lt|Light|Sconce)\b": {"field": "mount_type","value": "Wall Mount","abbr_label": "Wall Lt"},
    r"\bCeil(?:ing)?\s*(?:Lt|Light)?\b":{"field": "mount_type","value": "Ceiling Mount","abbr_label": "Ceiling Lt"},
    r"\bPendant\b":             {"field": "mount_type","value": "Pendant",           "abbr_label": "Pendant"},
    r"\bChandelier\b":          {"field": "mount_type","value": "Chandelier",        "abbr_label": "Chandelier"},
    r"\bHighbay\b|\bHigh\s*Bay\b": {"field": "mount_type","value": "High Bay",      "abbr_label": "Highbay"},
    r"\bDownlight\b|\bDown\s*Lt\b": {"field": "mount_type","value": "Downlight",    "abbr_label": "Downlight"},

    # ── DECK / LUMBER EDGE ───────────────────────────────────────────────────
    r"\b(?:Sq\s*Edge|Sq\s*Edg)\b": {"field": "edge_type","value": "Square Edge",   "abbr_label": "Sq Edge"},
    r"\b(?:Grooved|Groov)\b":   {"field": "edge_type","value": "Grooved",           "abbr_label": "Grooved"},
    r"\b(?:Hor|Horiz|Horizontal)\b": {"field": "orientation","value": "Horizontal", "abbr_label": "Hor"},
    r"\b(?:Str|Stair)\b":       {"field": "application","value": "Stair",           "abbr_label": "Str"},

    # ── CONNECTION / FASTENING ───────────────────────────────────────────────
    r"\b(?:NPT|FNPT)\b":        {"field": "connection_type","value": "NPT Thread",  "abbr_label": "NPT"},
    r"\bDKO\b":                 {"field": "arbor_type","value": "Diamond Knockout",  "abbr_label": "DKO"},
    r"\b(?:T&G|T\+G|TnG)\b":   {"field": "profile",  "value": "Tongue and Groove",  "abbr_label": "T&G"},

    # ── INSULATION R-VALUE ───────────────────────────────────────────────────
    r"\bR-?(\d+(?:\.\d+)?)\b":  {"field": "r_value",  "value": "R-{1}",             "abbr_label": "R{1}"},

    # ── WINDOW / DOOR ────────────────────────────────────────────────────────
    r"\bLowE\b|\bLow-E\b":      {"field": "glass_type","value": "Low-E Glass",       "abbr_label": "LowE"},
    r"\b(?:Arg|Argon)\b":       {"field": "gas_fill",  "value": "Argon",             "abbr_label": "Arg"},
    r"\b(?:Fxd|Fixed)\b":       {"field": "operable",  "value": "Fixed",             "abbr_label": "Fxd"},
    r"\bSkylt\b|\bSkylight\b":  {"field": "product_type","value": "Skylight",         "abbr_label": "Skylt"},
    r"\b(?:Bsmt|Basement)\b":   {"field": "application","value": "Basement",          "abbr_label": "Bsmt"},

    # ── ADA / COMPLIANCE ─────────────────────────────────────────────────────
    r"\bADA\b":                 {"field": "ada_compliant","value": "Yes",             "abbr_label": "ADA"},

    # ── PRODUCT TYPE SHORTHANDS ──────────────────────────────────────────────
    r"\bSdg\b|\bSiding\b":      {"field": "product_type","value": "Siding",           "abbr_label": "Sdg"},
    r"\bSoff\b|\bSoffit\b":     {"field": "product_type","value": "Soffit",           "abbr_label": "Soff"},
    r"\bDr\b|\bDoor\b":         {"field": "product_type","value": "Door",             "abbr_label": "Dr"},
    r"\bPwr\b|\bPower\b":       {"field": "product_type","value": "Power Supply",     "abbr_label": "Pwr"},
    r"\bLt\b|\bLight\b":        {"field": "product_type","value": "Light",            "abbr_label": "Lt"},
    r"\bBdl\b|\bBundle\b":      {"field": "package_type","value": "Bundle",           "abbr_label": "Bdl"},

    # ── BRAND SHORTCODES (for brand resolution) ──────────────────────────────
    r"\bSQ\b(?!\s*(?:Edge|Edg|ft|in|m))":
                                {"field": "brand",    "value": "Speed Queen",         "abbr_label": "SQ"},
    r"\bMilw\b":                {"field": "brand",    "value": "Milwaukee",           "abbr_label": "Milw"},
    r"\bGE\b|\bG\.E\.\b":      {"field": "brand",    "value": "General Electric",    "abbr_label": "GE"},
    r"\bLG\b":                  {"field": "brand",    "value": "LG Electronics",      "abbr_label": "LG"},
}


# ---------------------------------------------------------------------------
# Brand shortcode resolution (separate from field inference)
# ---------------------------------------------------------------------------

BRAND_SHORTCODES: dict[str, str] = {
    "SQ":    "Speed Queen",
    "Milw":  "Milwaukee",
    "GE":    "General Electric",
    "LG":    "LG Electronics",
    "3M":    "3M Company",
    "LP":    "LP Building Solutions",
    "OC":    "Owens Corning",
}


# ---------------------------------------------------------------------------
# Runtime loader: merges static dict with DB-learned abbreviations
# ---------------------------------------------------------------------------

def load_db_abbreviations() -> dict[str, dict]:
    """
    Load human-approved abbreviations from the desc_abbreviations DB table
    and convert them into regex-compatible entries to merge with DESC_ABBR_MAP.
    Returns an empty dict if DB is unavailable.
    """
    try:
        from pipeline.knowledge_store import get_desc_abbreviations
        db_abbrs = get_desc_abbreviations()
        extra: dict[str, dict] = {}
        for abbr, info in db_abbrs.items():
            # Build a word-boundary regex from the abbreviation
            import re
            safe = re.escape(abbr)
            pattern = rf"\b{safe}\b"
            extra[pattern] = {
                "field":       info.get("field_name", "material"),
                "value":       info["canonical_value"],
                "abbr_label":  abbr,
            }
        return extra
    except Exception as e:
        logger.debug("Could not load DB abbreviations: %s", e)
        return {}
