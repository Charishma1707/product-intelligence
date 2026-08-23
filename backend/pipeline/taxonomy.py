"""
pipeline/taxonomy.py — Canonical lookup functions.

Features:
  - E-commerce domain blocklist (URLs from these must never appear as Ref URLs)
  - Approved industrial distributor domains
  - Manufacturer domain guesser (backed by knowledge_store cache and LLM Oracle)
  - Variant-specific field detection
"""

from __future__ import annotations

import re
import logging
from urllib.parse import urlparse
from pipeline.knowledge_store import get_brand_domain, save_brand_domain
from pipeline.utils import generate_with_retry

logger = logging.getLogger(__name__)

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
    "pricegrabber.com", "shopping.google.com", "pricespy.com",
    "nextag.com", "shopzilla.com",
})

APPROVED_DISTRIBUTOR_DOMAINS: frozenset[str] = frozenset({
    "grainger.com", "zoro.com", "mcmaster.com", "mscdirect.com",
    "fastenal.com", "motion.com", "globalindustrial.com",
    "hdsupply.com", "supplyhouse.com", "platt.com", "rexel.com",
    "digikey.com", "mouser.com", "arrow.com", "avnet.com", "newark.com",
    "automationdirect.com", "galco.com", "alliantsystems.com",
    "hagemeyer.com", "wesco.com", "anixter.com",
    "3m.com",
})

def is_ecommerce(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        for blocked in ECOMMERCE_BLOCKLIST:
            if host == blocked or host.endswith("." + blocked):
                return True
    except Exception:
        pass
    return False

def is_approved_distributor(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        for dist in APPROVED_DISTRIBUTOR_DOMAINS:
            if host == dist or host.endswith("." + dist):
                return True
    except Exception:
        pass
    return False

def guess_mfr_domain(brand: str) -> str | None:
    """Return the manufacturer's likely domain from brand string using cache or LLM."""
    clean_brand = re.sub(r"\b(inc|llc|ltd|corp|co|gmbh|ag|sa|nv|bv|plc)\.?\s*$", "", brand.lower()).strip()
    
    # 1. Check Cache
    domain = get_brand_domain(clean_brand)
    if domain:
        logger.debug("[Taxonomy] Domain Cache Hit: %s -> %s", clean_brand, domain)
        return domain
        
    # 2. Ask LLM
    try:
        prompt = (
            f"What is the official primary website domain for the manufacturer '{brand}'? "
            "Reply with JUST the domain name (e.g. 'frigidaire.com' or '3m.com'). No other text."
        )
        messages = [{"role": "user", "content": prompt}]
        response = generate_with_retry(messages=messages, temperature=0.1).strip().lower()
        
        # Clean response
        if "http" in response:
            response = urlparse(response).netloc
        response = response.lstrip("www.").strip()
        
        # Validate it looks like a domain
        if "." in response and len(response) > 3 and " " not in response:
            logger.info("[Taxonomy] LLM resolved brand '%s' -> '%s'", brand, response)
            save_brand_domain(clean_brand, response)
            return response
    except Exception as e:
        logger.warning("[Taxonomy] Failed to guess domain for '%s': %s", brand, e)
        
    return None

def is_manufacturer_domain(url: str, brand: str) -> bool:
    domain = guess_mfr_domain(brand)
    if not domain:
        return not is_ecommerce(url) and not is_approved_distributor(url)
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return host == domain or host.endswith("." + domain)
    except Exception:
        return False

VARIANT_SPECIFIC_FIELDS: frozenset[str] = frozenset({
    "mpn", "model", "alternate_part_number",
    "size", "length", "width", "height", "depth", "depth_with_door_open",
    "disc_diameter", "blade_diameter", "bore_diameter", "outer_diameter",
    "thread_size", "pipe_size",
    "voltage_rating", "amperage_rating", "current_rating", "rated_current",
    "coil_voltage", "wattage", "power_rating",
    "capacity", "flow_rate", "max_speed", "spin_speed", "lumen_output",
    "sensing_distance",
    "grit", "quantity_per_pack", "thickness",
    "weight", "volume",
    "list_price", "upc", "ean", "gtin",
    "sound_level",
    "minimum_height", "maximum_height",
})

def get_variant_specific_fields() -> frozenset[str]:
    return VARIANT_SPECIFIC_FIELDS

def is_series_shared(field_name: str) -> bool:
    return field_name.lower().replace(" ", "_") not in VARIANT_SPECIFIC_FIELDS
