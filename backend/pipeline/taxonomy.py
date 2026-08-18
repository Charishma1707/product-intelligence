"""
pipeline/taxonomy.py — Canonical taxonomy lookups for the Unilog enrichment pipeline.

Provides:
  - E-commerce domain blocklist (URLs from these must never appear as Ref URLs)
  - Approved industrial distributor domains (valid Ref URL sources)
  - Manufacturer domain guesser (used to identify the MFR URL)
  - UNSPSC + Unilog classpath mapping by leaf category
  - Category → ordered attribute list mapping (Series ALWAYS first)
  - Fuzzy category-to-classpath resolver

All data seeded from the Expected Output sample and Solution Guide.
"""

from __future__ import annotations

import re
from difflib import get_close_matches
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# E-COMMERCE BLOCKLIST — URLs from these domains must NEVER appear as Ref URLs
# ---------------------------------------------------------------------------

ECOMMERCE_BLOCKLIST: frozenset[str] = frozenset({
    "amazon.com", "amazon.ca", "amazon.co.uk", "amazon.de", "amazon.fr",
    "amazon.co.jp", "amazon.in", "amazon.com.au", "amazon.com.mx",
    "ebay.com", "ebay.ca", "ebay.co.uk", "ebay.com.au",
    "walmart.com", "walmart.ca",
    "homedepot.com", "lowes.com",
    "target.com", "bestbuy.com", "costco.com",
    "wayfair.com", "overstock.com", "chewy.com",
    "etsy.com", "aliexpress.com", "alibaba.com", "made-in-china.com",
    "shopify.com", "bigcommerce.com",
    "sears.com", "kmart.com", "staples.com", "officedepot.com",
    "rakuten.com", "newegg.com", "bhphotovideo.com",
    # Aggregator / price comparison — not primary sources
    "pricegrabber.com", "shopping.google.com", "pricespy.com",
    "nextag.com", "shopzilla.com",
})

# ---------------------------------------------------------------------------
# APPROVED DISTRIBUTOR DOMAINS — valid Ref URL sources (B2B industrial only)
# ---------------------------------------------------------------------------

APPROVED_DISTRIBUTOR_DOMAINS: frozenset[str] = frozenset({
    "grainger.com", "zoro.com", "mcmaster.com", "mscdirect.com",
    "fastenal.com", "motion.com", "globalindustrial.com",
    "hdsupply.com", "supplyhouse.com", "platt.com", "rexel.com",
    "digikey.com", "mouser.com", "arrow.com", "avnet.com", "newark.com",
    "automationdirect.com", "galco.com", "alliantsystems.com",
    "hagemeyer.com", "wesco.com", "anixter.com",
    "3m.com",  # 3M is both manufacturer and distributor
})


def is_ecommerce(url: str) -> bool:
    """Return True if the URL belongs to a blocked e-commerce domain."""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        for blocked in ECOMMERCE_BLOCKLIST:
            if host == blocked or host.endswith("." + blocked):
                return True
    except Exception:
        pass
    return False


def is_approved_distributor(url: str) -> bool:
    """Return True if the URL is from an approved B2B distributor domain."""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        for dist in APPROVED_DISTRIBUTOR_DOMAINS:
            if host == dist or host.endswith("." + dist):
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# MANUFACTURER DOMAIN GUESSER
# Tries to guess the manufacturer's own website domain from brand name.
# Used to score Pass 1 search results as "manufacturer URL" candidates.
# ---------------------------------------------------------------------------

# Known exact mappings (brand name lower → domain)
_MFR_DOMAIN_MAP: dict[str, str] = {
    "3m": "3m.com",
    "freud": "freudtools.com",
    "diablo": "diablotools.com",
    "mirka": "mirka.com",
    "norton": "nortonabrasives.com",
    "dewalt": "dewalt.com",
    "bosch": "boschtools.com",
    "makita": "makita.com",
    "milwaukee": "milwaukeetool.com",
    "ridgid": "ridgid.com",
    "festool": "festool.com",
    "metabo": "metabo.com",
    "hilti": "hilti.com",
    "stanley": "stanleytools.com",
    "craftsman": "craftsman.com",
    "black & decker": "blackanddecker.com",
    "black+decker": "blackanddecker.com",
    "siemens": "siemens.com",
    "abb": "abb.com",
    "schneider electric": "se.com",
    "eaton": "eaton.com",
    "omron": "ia.omron.com",
    "skf": "skf.com",
    "fag": "schaeffler.com",
    "nsk": "nskamericas.com",
    "timken": "timken.com",
    "frigidaire": "frigidaire.com",
    "whirlpool": "whirlpool.com",
    "ge appliances": "geappliances.com",
    "lg": "lg.com",
    "samsung": "samsung.com",
    "moen": "moen.com",
    "delta": "deltafaucet.com",
    "kohler": "kohler.com",
    "american standard": "americanstandardus.com",
    "grohe": "grohe.com",
    "pfister": "pfisterfaucets.com",
    "rheem": "rheem.com",
    "honeywell": "honeywell.com",
    "leviton": "leviton.com",
    "hubbell": "hubbell.com",
    "legrand": "legrand.us",
    "panduit": "panduit.com",
    "phoenix contact": "phoenixcontact.com",
    "wago": "wago.com",
    "emerson": "emerson.com",
    "parker": "parker.com",
    "swagelok": "swagelok.com",
    "watts": "watts.com",
    "pentair": "pentair.com",
    "grundfos": "grundfos.com",
    "xylem": "xylem.com",
    "goulds": "gouldswater.com",
    "graco": "graco.com",
    "nordson": "nordson.com",
    "weiler": "weilerabrasives.com",
    "pferd": "pferd.com",
    "walter": "walter.com",
    "victor": "victorequipment.com",
    "lincoln electric": "lincolnelectric.com",
    "esab": "esab.com",
    "miller": "millerwelds.com",
    "fluke": "fluke.com",
    "klein tools": "kleintools.com",
    "channellock": "channellock.com",
    "irwin": "irwin.com",
    "knipex": "knipex.com",
    "wera": "wera.de",
    "weidmuller": "weidmuller.com",
    "fibre-metal": "fibremetal.com",
    "msa": "msasafety.com",
    "3m personal safety": "3m.com",
    "honeywell safety": "honeywellsafety.com",
    "ansell": "ansell.com",
    "pip": "pipglobal.com",
    "north": "honeywellsafety.com",
    "uvex": "uvex.com",
    "moldex": "moldex.com",
}


def guess_mfr_domain(brand: str) -> str | None:
    """Return the manufacturer's likely domain from brand string, or None."""
    key = brand.lower().strip()
    # Direct lookup
    if key in _MFR_DOMAIN_MAP:
        return _MFR_DOMAIN_MAP[key]
    # Strip common suffixes: "Inc", "LLC", "Ltd", "Corp", "(1234)"
    clean = re.sub(r"\s*\(.*?\)\s*", "", key)
    clean = re.sub(r"\b(inc|llc|ltd|corp|co|gmbh|ag|sa|nv|bv|plc)\.?\s*$", "", clean).strip()
    if clean in _MFR_DOMAIN_MAP:
        return _MFR_DOMAIN_MAP[clean]
    # Fuzzy match
    matches = get_close_matches(clean, list(_MFR_DOMAIN_MAP.keys()), n=1, cutoff=0.75)
    if matches:
        return _MFR_DOMAIN_MAP[matches[0]]
    return None


def is_manufacturer_domain(url: str, brand: str) -> bool:
    """Return True if the URL looks like it's from the manufacturer's own domain."""
    domain = guess_mfr_domain(brand)
    if not domain:
        # Heuristic: not a known distributor and not e-commerce → probably manufacturer
        return not is_ecommerce(url) and not is_approved_distributor(url)
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return host == domain or host.endswith("." + domain)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# UNILOG TAXONOMY — Classpath + UNSPSC
# Seeded from Expected Output sample and solution guide
# ---------------------------------------------------------------------------

# (leaf_category_key, classpath, unspsc_8digit)
_TAXONOMY: list[tuple[str, str, str]] = [
    # Abrasives
    ("sanding belt",          "Hand Tools > Abrasives > Sanding Belts",               "23152000"),
    ("sanding disc",          "Hand Tools > Abrasives > Sanding Discs",               "23152000"),
    ("abrasive disc",         "Hand Tools > Abrasives > Abrasive Discs",              "23152000"),
    ("cut-off disc",          "Hand Tools > Abrasives > Cut-Off Discs",               "23152000"),
    ("cut off disc",          "Hand Tools > Abrasives > Cut-Off Discs",               "23152000"),
    ("cutting wheel",         "Hand Tools > Abrasives > Cut-Off Discs",               "23152000"),
    ("grinding disc",         "Hand Tools > Abrasives > Grinding Wheels",             "23152000"),
    ("grinding wheel",        "Hand Tools > Abrasives > Grinding Wheels",             "23152000"),
    ("flap disc",             "Hand Tools > Abrasives > Flap Discs",                  "23152000"),
    ("abrasive sheet",        "Hand Tools > Abrasives > Abrasive Sheets",             "23152000"),
    ("sandpaper",             "Hand Tools > Abrasives > Abrasive Sheets",             "23152000"),
    ("abrasive roll",         "Hand Tools > Abrasives > Abrasive Rolls",              "23152000"),
    ("wire brush",            "Hand Tools > Abrasives > Wire Brushes",                "23152000"),
    ("abrasive pad",          "Hand Tools > Abrasives > Abrasive Pads",               "23152000"),
    ("polishing disc",        "Hand Tools > Abrasives > Polishing Discs",             "23152000"),
    # Appliances
    ("built-in dishwasher",   "Appliances & Consumer Electronics > Kitchen Appliances > Built-In Dishwashers", "52141500"),
    ("dishwasher",            "Appliances & Consumer Electronics > Kitchen Appliances > Built-In Dishwashers", "52141500"),
    ("refrigerator",          "Appliances & Consumer Electronics > Kitchen Appliances > Refrigerators",        "52141600"),
    ("washing machine",       "Appliances & Consumer Electronics > Laundry Appliances > Washing Machines",    "52161500"),
    ("washer",                "Appliances & Consumer Electronics > Laundry Appliances > Washing Machines",    "52161500"),
    ("dryer",                 "Appliances & Consumer Electronics > Laundry Appliances > Dryers",              "52161500"),
    ("range",                 "Appliances & Consumer Electronics > Kitchen Appliances > Ranges",               "52141700"),
    ("oven",                  "Appliances & Consumer Electronics > Kitchen Appliances > Ovens",                "52141700"),
    ("microwave",             "Appliances & Consumer Electronics > Kitchen Appliances > Microwave Ovens",      "52141900"),
    # Plumbing / Faucets
    ("kitchen faucet",        "Plumbing > Faucets & Fixtures > Kitchen Faucets",      "30181500"),
    ("bathroom faucet",       "Plumbing > Faucets & Fixtures > Bathroom Faucets",     "30181500"),
    ("sink faucet",           "Plumbing > Faucets & Fixtures > Sink Faucets",         "30181500"),
    ("faucet",                "Plumbing > Faucets & Fixtures > Faucets",              "30181500"),
    ("pipe fitting",          "Plumbing > Pipe Fittings > Pipe Fittings",             "40141600"),
    ("brass fitting",         "Plumbing > Pipe Fittings > Brass Pipe Fittings",       "40141600"),
    ("valve",                 "Plumbing > Valves > Valves",                           "40141700"),
    ("ball valve",            "Plumbing > Valves > Ball Valves",                      "40141700"),
    ("gate valve",            "Plumbing > Valves > Gate Valves",                      "40141700"),
    # Electrical
    ("contactor",             "Electrical > Motor Controls > Contactors",             "39121400"),
    ("circuit breaker",       "Electrical > Electrical Distribution > Circuit Breakers", "39121200"),
    ("relay",                 "Electrical > Controls > Relays",                       "39121600"),
    ("disconnect switch",     "Electrical > Electrical Distribution > Disconnect Switches", "39121200"),
    ("wire connector",        "Electrical > Wiring Devices > Wire Connectors",        "39121100"),
    ("conduit fitting",       "Electrical > Conduit & Fittings > Conduit Fittings",   "39131600"),
    ("light fixture",         "Electrical > Lighting > Light Fixtures",               "39111600"),
    ("led fixture",           "Electrical > Lighting > LED Fixtures",                 "39111600"),
    ("outlet",                "Electrical > Wiring Devices > Outlets",                "39121100"),
    ("switch",                "Electrical > Wiring Devices > Switches",               "39121100"),
    # Safety / PPE
    ("safety glasses",        "Safety > Eye & Face Protection > Safety Glasses",      "46182000"),
    ("hard hat",              "Safety > Head Protection > Hard Hats",                 "46181500"),
    ("gloves",                "Safety > Hand Protection > Gloves",                    "46182300"),
    ("respirator",            "Safety > Respiratory Protection > Respirators",        "46182100"),
    ("hearing protection",    "Safety > Hearing Protection > Earplugs & Earmuffs",   "46182200"),
    # Hand Tools
    ("hammer",                "Hand Tools > Striking Tools > Hammers",                "27111500"),
    ("wrench",                "Hand Tools > Wrenches > Wrenches",                     "27111700"),
    ("screwdriver",           "Hand Tools > Screwdrivers > Screwdrivers",             "27111900"),
    ("drill bit",             "Hand Tools > Drilling & Boring > Drill Bits",          "27111600"),
    ("saw blade",             "Hand Tools > Cutting Tools > Saw Blades",              "27112200"),
    ("measuring tape",        "Hand Tools > Measuring Tools > Measuring Tapes",       "41111600"),
    # Material Handling
    ("hand truck",            "Material Handling > Carts & Dollies > Hand Trucks",    "24101601"),
    ("pallet jack",           "Material Handling > Carts & Dollies > Pallet Jacks",   "24101603"),
    ("storage cabinet",       "Material Handling > Storage > Storage Cabinets",       "56101700"),
    # Fasteners
    ("bolt",                  "Fasteners > Bolts > Bolts",                            "31161500"),
    ("nut",                   "Fasteners > Nuts > Nuts",                              "31161600"),
    ("screw",                 "Fasteners > Screws > Screws",                          "31161700"),
    ("washer",                "Fasteners > Washers > Washers",                        "31161800"),
    # Bearings
    ("ball bearing",          "Mechanical Components > Bearings > Ball Bearings",     "31171500"),
    ("bearing",               "Mechanical Components > Bearings > Bearings",          "31171500"),
    # Sensors
    ("proximity sensor",      "Electrical > Sensors > Proximity Sensors",             "32101500"),
    ("sensor",                "Electrical > Sensors > Sensors",                       "32101500"),
    ("limit switch",          "Electrical > Sensors > Limit Switches",                "32101800"),
    # Pneumatics / Hydraulics
    ("air compressor",        "Pneumatics > Air Compressors > Air Compressors",       "40161500"),
    ("pneumatic cylinder",    "Pneumatics > Cylinders > Pneumatic Cylinders",         "40141100"),
    ("hydraulic fitting",     "Hydraulics > Hydraulic Fittings > Hydraulic Fittings", "40141600"),
    # Cleaning / Janitorial
    ("cleaning supplies",     "Cleaning & Maintenance > Cleaning Supplies > Cleaning Supplies", "47131600"),
    ("mop",                   "Cleaning & Maintenance > Cleaning Supplies > Mops",   "47131600"),
    # Lubricants
    ("lubricant",             "Maintenance > Lubricants & Oils > Lubricants",         "15121900"),
    ("grease",                "Maintenance > Lubricants & Oils > Greases",            "15121900"),
]


def lookup_taxonomy(category_hint: str) -> tuple[str, str]:
    """
    Given a free-text category/description hint, return (classpath, unspsc).
    Uses simple keyword matching then falls back to fuzzy match.
    Returns generic fallback if nothing matches.
    """
    hint_lower = category_hint.lower()

    # 1. Direct keyword scan (longest match wins)
    best_key = ""
    best_classpath = ""
    best_unspsc = ""
    for key, classpath, unspsc in _TAXONOMY:
        if key in hint_lower and len(key) > len(best_key):
            best_key = key
            best_classpath = classpath
            best_unspsc = unspsc
    if best_classpath:
        return best_classpath, best_unspsc

    # 2. Fuzzy match against keys
    keys = [t[0] for t in _TAXONOMY]
    matches = get_close_matches(hint_lower, keys, n=1, cutoff=0.55)
    if matches:
        for key, classpath, unspsc in _TAXONOMY:
            if key == matches[0]:
                return classpath, unspsc

    return "Industrial Products > General > Miscellaneous", "00000000"


# ---------------------------------------------------------------------------
# CATEGORY → ORDERED ATTRIBUTE LIST
# Series is ALWAYS index 0 (ATTRIBUTE_LABEL 1).
# These are the exact attribute names that Unilog expects for each leaf category.
# Seeded from Expected Output sample + solution guide field definitions.
# ---------------------------------------------------------------------------

CATEGORY_ATTRIBUTES: dict[str, list[str]] = {
    # ── Abrasives ───────────────────────────────────────────────────────────
    "Sanding Belts": [
        "Series", "Model", "Grit", "Length", "Width",
        "Backing Material", "Abrasive Material", "Abrasive Type", "Bond Type",
        "Max Speed", "Application", "Quantity Per Pack",
        "Color", "Country Of Origin",
    ],
    "Sanding Discs": [
        "Series", "Model", "Grit", "Disc Diameter", "Hole Diameter",
        "Backing Material", "Abrasive Material", "Attachment Type",
        "Max Speed", "Application", "Quantity Per Pack",
    ],
    "Abrasive Discs": [
        "Series", "Model", "Grit", "Disc Diameter", "Hole Diameter",
        "Backing Material", "Abrasive Material", "Attachment Type",
        "Max Speed", "Application", "Quantity Per Pack",
    ],
    "Cut-Off Discs": [
        "Series", "Model", "Disc Diameter", "Thickness", "Arbor Hole Size",
        "Abrasive Material", "Max Speed", "Material Compatibility",
        "Application", "Quantity Per Pack",
    ],
    "Grinding Wheels": [
        "Series", "Model", "Disc Diameter", "Thickness", "Arbor Hole Size",
        "Abrasive Material", "Grain Size", "Hardness Grade",
        "Bond Type", "Max Speed", "Application",
    ],
    "Flap Discs": [
        "Series", "Model", "Grit", "Disc Diameter", "Arbor Hole Size",
        "Abrasive Material", "Flap Material", "Max Speed",
        "Application", "Quantity Per Pack",
    ],
    "Abrasive Sheets": [
        "Series", "Model", "Grit", "Length", "Width",
        "Backing Material", "Abrasive Material", "Attachment Type",
        "Application", "Quantity Per Pack",
    ],
    "Wire Brushes": [
        "Series", "Model", "Wire Material", "Disc Diameter",
        "Wire Gauge", "Max Speed", "Application",
    ],
    # ── Appliances ──────────────────────────────────────────────────────────
    "Built-In Dishwashers": [
        "Series", "Model", "Number of Wash Cycles", "Voltage Rating", "Amperage Rating",
        "Mounting Type", "Plug Type", "Size", "Depth With Door Open",
        "Minimum Height", "Maximum Height", "Sound Level", "Material", "Color",
        "Additional Information",
    ],
    "Refrigerators": [
        "Series", "Model", "Capacity", "Voltage Rating", "Amperage Rating",
        "Configuration", "Door Style", "Ice Maker", "Water Dispenser",
        "Energy Star Certified", "Size", "Color", "Material",
    ],
    "Washing Machines": [
        "Series", "Model", "Capacity", "Voltage Rating", "Amperage Rating",
        "Loading Type", "Spin Speed", "Number of Wash Cycles",
        "Energy Star Certified", "Size", "Color",
    ],
    "Dryers": [
        "Series", "Model", "Capacity", "Voltage Rating", "Amperage Rating",
        "Fuel Type", "Venting Type", "Number of Cycles",
        "Energy Star Certified", "Size", "Color",
    ],
    "Ranges": [
        "Series", "Model", "Fuel Type", "Number of Burners", "Oven Capacity",
        "Voltage Rating", "Amperage Rating", "Size", "Color",
    ],
    "Ovens": [
        "Series", "Model", "Fuel Type", "Oven Capacity", "Convection",
        "Voltage Rating", "Amperage Rating", "Size", "Color",
    ],
    "Microwave Ovens": [
        "Series", "Model", "Capacity", "Wattage", "Mounting Type",
        "Voltage Rating", "Size", "Color",
    ],
    # ── Faucets & Plumbing ───────────────────────────────────────────────────
    "Kitchen Faucets": [
        "Series", "Model", "Number of Holes", "Handle Type", "Mounting Type",
        "Spout Height", "Spout Reach", "Flow Rate", "Finish",
        "Material", "Includes Spray", "Valve Type",
    ],
    "Bathroom Faucets": [
        "Series", "Model", "Number of Holes", "Handle Type", "Mounting Type",
        "Spout Height", "Spout Reach", "Flow Rate", "Finish",
        "Material", "Valve Type",
    ],
    "Sink Faucets": [
        "Series", "Model", "Number of Holes", "Handle Type", "Mounting Type",
        "Spout Height", "Spout Reach", "Flow Rate", "Finish",
        "Material", "Valve Type",
    ],
    "Faucets": [
        "Series", "Model", "Number of Holes", "Handle Type", "Mounting Type",
        "Flow Rate", "Finish", "Material", "Valve Type",
    ],
    "Pipe Fittings": [
        "Series", "Model", "Fitting Type", "Material", "Connection Type",
        "Thread Size", "Pipe Size", "Pressure Rating", "Temperature Rating",
    ],
    "Brass Pipe Fittings": [
        "Series", "Model", "Fitting Type", "Material", "Connection Type",
        "Thread Size", "Pipe Size", "Pressure Rating",
    ],
    "Ball Valves": [
        "Series", "Model", "Material", "Connection Type", "Pipe Size",
        "Pressure Rating", "Temperature Rating", "Actuation Type",
    ],
    "Gate Valves": [
        "Series", "Model", "Material", "Connection Type", "Pipe Size",
        "Pressure Rating", "Temperature Rating",
    ],
    "Valves": [
        "Series", "Model", "Valve Type", "Material", "Connection Type",
        "Pipe Size", "Pressure Rating", "Temperature Rating",
    ],
    # ── Electrical ───────────────────────────────────────────────────────────
    "Contactors": [
        "Series", "Model", "Rated Current", "Coil Voltage", "Pole Count",
        "AC Utilization Category", "Power Rating", "Operating Voltage Range",
        "Contact Type", "Mounting Type", "IP Rating", "Certifications",
    ],
    "Circuit Breakers": [
        "Series", "Model", "Amperage Rating", "Voltage Rating", "Interrupt Rating",
        "Number of Poles", "Mounting Type", "Frame Size", "Trip Type",
        "Certifications",
    ],
    "Relays": [
        "Series", "Model", "Coil Voltage", "Contact Rating", "Contact Configuration",
        "Mounting Type", "IP Rating", "Certifications",
    ],
    "Light Fixtures": [
        "Series", "Model", "Wattage", "Voltage Rating", "Color Temperature",
        "Lumen Output", "Mounting Type", "Fixture Type", "Dimmable",
        "IP Rating", "Material", "Color", "Energy Star Certified",
    ],
    "LED Fixtures": [
        "Series", "Model", "Wattage", "Voltage Rating", "Color Temperature",
        "Lumen Output", "Mounting Type", "Fixture Type", "Dimmable",
        "IP Rating", "Material", "Color", "Energy Star Certified",
    ],
    # ── Safety / PPE ─────────────────────────────────────────────────────────
    "Safety Glasses": [
        "Series", "Model", "Lens Material", "Frame Material", "Lens Color",
        "UV Protection", "ANSI Rating", "Certifications",
    ],
    "Hard Hats": [
        "Series", "Model", "Type", "Class", "Material",
        "Suspension Type", "ANSI Rating", "Color",
    ],
    "Gloves": [
        "Series", "Model", "Material", "Liner Material", "Size",
        "Cut Resistance Level", "Grip Type", "ANSI Rating",
    ],
    # ── Hand Tools ───────────────────────────────────────────────────────────
    "Drill Bits": [
        "Series", "Model", "Bit Diameter", "Bit Length", "Shank Type",
        "Shank Diameter", "Material", "Coating", "Application",
    ],
    "Saw Blades": [
        "Series", "Model", "Blade Diameter", "Tooth Count", "Kerf Width",
        "Arbor Size", "Material", "Application",
    ],
    "Wrenches": [
        "Series", "Model", "Drive Size", "Wrench Type", "Material",
        "Finish", "Length",
    ],
    # ── Bearings ─────────────────────────────────────────────────────────────
    "Ball Bearings": [
        "Series", "Model", "Bore Diameter", "Outer Diameter", "Width",
        "Dynamic Load Rating", "Static Load Rating", "Max Speed",
        "Bearing Type", "Sealing Type", "Material",
    ],
    "Bearings": [
        "Series", "Model", "Bore Diameter", "Outer Diameter", "Width",
        "Dynamic Load Rating", "Static Load Rating", "Max Speed",
        "Bearing Type", "Sealing Type", "Material",
    ],
    # ── Sensors ─────────────────────────────────────────────────────────────
    "Proximity Sensors": [
        "Series", "Model", "Sensing Distance", "Output Type", "Supply Voltage",
        "Output Current", "Switching Frequency", "Connection Type",
        "Housing Material", "IP Rating", "Thread Size", "Certifications",
    ],
    "Sensors": [
        "Series", "Model", "Sensing Distance", "Output Type", "Supply Voltage",
        "IP Rating", "Connection Type", "Certifications",
    ],
    "Limit Switches": [
        "Series", "Model", "Actuator Type", "Contact Configuration",
        "Rated Voltage", "Rated Current", "IP Rating",
        "Housing Material", "Certifications",
    ],
    # ── Default ──────────────────────────────────────────────────────────────
    "Default": [
        "Series", "Model", "Voltage Rating", "Amperage Rating", "Material",
        "Size", "Color", "Finish", "Application",
        "Certifications", "Country Of Origin",
    ],
}

# Alias map for flexible lookup
_CATEGORY_ALIASES: dict[str, str] = {
    "sanding belt": "Sanding Belts",
    "sanding belts": "Sanding Belts",
    "sanding disc": "Sanding Discs",
    "sanding discs": "Sanding Discs",
    "abrasive disc": "Abrasive Discs",
    "abrasive discs": "Abrasive Discs",
    "cut-off disc": "Cut-Off Discs",
    "cut off disc": "Cut-Off Discs",
    "cut-off discs": "Cut-Off Discs",
    "cutting wheel": "Cut-Off Discs",
    "cutting wheels": "Cut-Off Discs",
    "grinding disc": "Grinding Wheels",
    "grinding wheel": "Grinding Wheels",
    "grinding wheels": "Grinding Wheels",
    "flap disc": "Flap Discs",
    "flap discs": "Flap Discs",
    "abrasive sheet": "Abrasive Sheets",
    "abrasive sheets": "Abrasive Sheets",
    "sandpaper": "Abrasive Sheets",
    "wire brush": "Wire Brushes",
    "wire brushes": "Wire Brushes",
    "abrasive pads": "Abrasive Sheets",
    "dishwasher": "Built-In Dishwashers",
    "built-in dishwasher": "Built-In Dishwashers",
    "built in dishwasher": "Built-In Dishwashers",
    "refrigerator": "Refrigerators",
    "washing machine": "Washing Machines",
    "washer": "Washing Machines",
    "dryer": "Dryers",
    "range": "Ranges",
    "oven": "Ovens",
    "microwave": "Microwave Ovens",
    "kitchen faucet": "Kitchen Faucets",
    "bathroom faucet": "Bathroom Faucets",
    "sink faucet": "Sink Faucets",
    "faucet": "Faucets",
    "pipe fitting": "Pipe Fittings",
    "brass fitting": "Brass Pipe Fittings",
    "brass pipe fitting": "Brass Pipe Fittings",
    "ball valve": "Ball Valves",
    "gate valve": "Gate Valves",
    "valve": "Valves",
    "contactor": "Contactors",
    "circuit breaker": "Circuit Breakers",
    "relay": "Relays",
    "light fixture": "Light Fixtures",
    "led fixture": "LED Fixtures",
    "safety glasses": "Safety Glasses",
    "hard hat": "Hard Hats",
    "gloves": "Gloves",
    "drill bit": "Drill Bits",
    "saw blade": "Saw Blades",
    "wrench": "Wrenches",
    "ball bearing": "Ball Bearings",
    "bearing": "Bearings",
    "proximity sensor": "Proximity Sensors",
    "sensor": "Sensors",
    "limit switch": "Limit Switches",
}


def get_category_attributes(subcategory: str, description: str = "") -> list[str]:
    """
    Return the ordered attribute list for a given subcategory.
    Series is guaranteed to be first. Falls back to Default.
    """
    # Direct lookup by subcategory name
    attrs = CATEGORY_ATTRIBUTES.get(subcategory)
    if attrs:
        return _ensure_series_first(attrs)

    # Alias lookup
    key = subcategory.lower().strip()
    if key in _CATEGORY_ALIASES:
        attrs = CATEGORY_ATTRIBUTES.get(_CATEGORY_ALIASES[key])
        if attrs:
            return _ensure_series_first(attrs)

    # Scan description + subcategory for keyword match
    combined = (subcategory + " " + description).lower()
    for alias, cat_name in _CATEGORY_ALIASES.items():
        if alias in combined:
            attrs = CATEGORY_ATTRIBUTES.get(cat_name)
            if attrs:
                return _ensure_series_first(attrs)

    # Fuzzy match against known category names
    known_cats = list(CATEGORY_ATTRIBUTES.keys())
    matches = get_close_matches(subcategory, known_cats, n=1, cutoff=0.6)
    if matches:
        return _ensure_series_first(CATEGORY_ATTRIBUTES[matches[0]])

    return _ensure_series_first(CATEGORY_ATTRIBUTES["Default"])


def _ensure_series_first(attrs: list[str]) -> list[str]:
    """Guarantee 'Series' is always the first attribute."""
    result = [a for a in attrs if a.lower() != "series"]
    return ["Series"] + result


if __name__ == "__main__":
    # Quick self-test
    cp, us = lookup_taxonomy("sanding belt")
    assert cp == "Hand Tools > Abrasives > Sanding Belts", cp
    assert us == "23152000", us

    cp2, us2 = lookup_taxonomy("built-in dishwasher")
    assert "Dishwasher" in cp2, cp2

    attrs = get_category_attributes("Sanding Belts")
    assert attrs[0] == "Series", attrs

    assert is_ecommerce("https://www.amazon.com/dp/B0001")
    assert not is_ecommerce("https://www.grainger.com/product/123")
    assert is_approved_distributor("https://grainger.com/product/123")

    print("[PASS] taxonomy.py self-test passed.")
