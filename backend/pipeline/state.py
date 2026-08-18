"""
state.py — Defines the LangGraph state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from schema import FieldValue

class PipelineState(TypedDict, total=False):
    # Inputs
    job_id: str
    product_id: str
    brand: str
    mpn: str
    description: str
    provided_schema: list[str] | None
    strict_schema: bool
    force_review: bool
    
    # Node 1: Interpret
    category: str
    subcategory: str | None
    classpath: str | None
    expected_fields: list[str]
    
    # Node 2: Retrieve
    raw_documents: list[dict]  # list of chunks
    source_urls: list[str]     # all non-ecommerce URLs used (legacy compat)
    mfr_url: str | None        # manufacturer's own product page URL
    ref_urls: list[str]        # approved distributor/datasheet ref URLs (non-ecommerce)
    product_image_url: str | None    # product image from manufacturer site
    alternate_image_urls: list[str]  # up to 4 alternate images from manufacturer site
    spec_sheet_url: str | None       # PDF spec sheet from manufacturer
    sds_url: str | None              # Safety Data Sheet URL from manufacturer
    manual_url: str | None           # owner/user manual URL from manufacturer
    installation_url: str | None     # installation guide URL from manufacturer
    warranty_url: str | None         # warranty document URL from manufacturer
    catalog_url: str | None          # catalog URL from manufacturer
    energy_guide_url: str | None     # energy guide URL from manufacturer

    # Node 3: Extract
    extracted_fields: dict[str, Any]  # ExtractedField dicts

    # Node 4: Validate
    specifications: dict[str, FieldValue]
    flagged_for_review: list[str]
    overall_confidence: float

    # Node 5: Copywrite
    invoice_desc: str | None
    mobile_desc: str | None
    short_desc: str | None
    long_desc: str | None
    retail_desc: str | None
    marketing_description: str | None
    item_features: list[str]          # ITEM_FEATURES_1 to ITEM_FEATURES_20
    unspsc: str | None                # 8-digit UNSPSC code
    manufacturer_name: str | None     # Normalized from brand input

    # Unilog Commercial Fields (extracted by extractor, finalized by copywrite)
    upc: str | None
    ean: str | None
    gtin: str | None
    warranty: str | None
    list_price: str | None
    selling_qty: str | None
    selling_uom: str | None
    standard_packaging_info: str | None
    country_of_origin: str | None
    standards_approvals: str | None
    prop_65: str | None
    with_accessories: str | None
    application_desc: str | None
    includes_desc: str | None
    product_name: str | None
    trade_name: str | None
    alternate_part_number: str | None
    discontinued: str | None

    # Dimensions & Weight
    length: str | None
    length_uom: str | None
    height: str | None
    height_uom: str | None
    width: str | None
    width_uom: str | None
    weight: str | None
    weight_uom: str | None
    volume: str | None
    volume_uom: str | None

    # Input CSV Passthrough — raw columns copied verbatim from input CSV
    input_part_desc: str | None
    input_e1_brand: str | None
    input_unilog_brand: str | None
    input_dib_brand: str | None
    input_part_manuf: str | None
    # Unilog taxonomy passthrough from input (PART_NUMBER, Dept, Class, Fine, SKU)
    part_number: str | None
    dept: str | None
    class_: str | None
    fine: str | None
    sku_my_part_number: str | None
    # Brand name (trademarked form, e.g. "FRIGIDAIRE®")
    brand_name: str | None

    # Final & Status
    status: str  # "in_progress" | "needs_review" | "complete" | "failed"
    error: str | None
    logs: list[dict]  # Trace logs for UI
