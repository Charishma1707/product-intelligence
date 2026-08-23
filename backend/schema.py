"""
schema.py — Pydantic models for the Product Intelligence Pipeline.

Every extracted field carries:
  - value: the actual data
  - confidence: 0.0–1.0 score
  - method: "extracted" | "inferred" | "human_verified"
  - cause: plain-English reason for the confidence score
  - citation: exactly where the value came from
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Source type enum — tells us exactly what kind of evidence backs a value
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    MFR_WEBPAGE = "mfr_webpage"
    SERIES_KNOWLEDGE = "series_knowledge"
    WEBPAGE_TEXT = "webpage_text"
    PDF_TEXT = "pdf_text"
    PDF_TABLE = "pdf_table"
    PDF_CHART = "pdf_chart"
    INFERRED = "inferred"
    INPUT_DATA = "INPUT_DATA"
    MANUFACTURER_PAGE = "MANUFACTURER_PAGE"
    MANUFACTURER_PDF = "MANUFACTURER_PDF"
    MANUFACTURER_CATALOG = "MANUFACTURER_CATALOG"
    DISTRIBUTOR = "DISTRIBUTOR"
    COMPETITOR = "COMPETITOR"
    CHROMA = "CHROMA"
    KNOWLEDGE_GRAPH = "KNOWLEDGE_GRAPH"
    CACHE = "CACHE"
    LLM_INFERENCE = "LLM_INFERENCE"
    HUMAN_APPROVED = "HUMAN_APPROVED"


# ---------------------------------------------------------------------------
# FieldStatus — provenance quality of a single extracted field
# ---------------------------------------------------------------------------

class FieldStatus(str, Enum):
    """Quality/provenance status for a single extracted field."""
    VERIFIED   = "VERIFIED"     # MPN found on page + value from manufacturer source
    SUPPORTED  = "SUPPORTED"    # Value from approved distributor or secondary source
    INFERRED   = "INFERRED"     # No document evidence; LLM domain-knowledge inference
    CONFLICT   = "CONFLICT"     # Two sources give different values for this field
    MISSING    = "MISSING"      # Field not found in any source, value is None
    PROPAGATED = "PROPAGATED"   # Inherited from a sibling MPN, needs verification
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Low confidence or flagged by validator


# ---------------------------------------------------------------------------
# Citation — full provenance for a single field value
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    """Exactly where a field value came from."""
    retrieval_method: str | None = None             # e.g. "CHROMA", "CACHE", "WEB_SEARCH"
    original_source_type: SourceType | None = None
    source_url: str | None = None                   
    document_id: str | None = None                  
    page: int | None = None                         # 1-indexed page within the PDF
    evidence: str | None = None                     # verbatim quote (webpage_text / pdf_text)
    similar_products_used: list[str] | None = None  # MPNs used for inference


# ---------------------------------------------------------------------------
# FieldValue — one spec field with full provenance
# ---------------------------------------------------------------------------

class FieldValue(BaseModel):
    """A single extracted/inferred specification field with full provenance."""
    value: str | float | int | bool | None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: str | None = None            # e.g. "LLM", "REGEX", "HUMAN"
    status: FieldStatus = FieldStatus.MISSING       # provenance quality label
    source: Citation | None = None
    conflict_values: list[str] | None = None        # if CONFLICT: list of differing values seen
    is_series_shared: bool = False                  # whether this is a shared series attribute



# ---------------------------------------------------------------------------
# ProductRecord — the final output of the pipeline
# ---------------------------------------------------------------------------

class ProductRecord(BaseModel):
    """Commerce-ready product record with full provenance."""
    brand: str
    mpn: str
    category: str
    classpath: str | None = None                    # Unilog Category Path
    description: str
    
    # Unilog specific descriptions
    invoice_desc: str | None = None                 # <=40 chars, ALL CAPS
    mobile_desc: str | None = None                  # 60-80 chars
    short_desc: str | None = None                   # Standardized format
    long_desc: str | None = None                    # Full descriptive paragraph
    retail_desc: str | None = None                  # Retail-facing description
    marketing_description: str | None = None        # Marketing paragraph
    item_features: list[str] = []                   # Up to 20 bullet point features
    unspsc: str | None = None                       # 8-digit UNSPSC code
    manufacturer_name: str | None = None            # Normalized manufacturer name
    
    specifications: dict[str, FieldValue] = {}
    flagged_for_review: list[str] = []
    logs: list[dict] = []                           # Pipeline execution traces
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "complete"                        # "complete" | "needs_review" | "failed"
    product_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_urls: list[str] = []                     # URLs used during web/PDF research
    mfr_url: str | None = None                      # Manufacturer's own product page URL
    ref_urls: list[str] = Field(default_factory=list)  # Approved distributor/datasheet ref URLs

    # --- Unilog Commercial Fields ---
    upc: str | None = None
    ean: str | None = None
    gtin: str | None = None
    warranty: str | None = None
    list_price: str | None = None
    selling_qty: str | None = None
    selling_uom: str | None = None
    standard_packaging_info: str | None = None
    country_of_origin: str | None = None
    standards_approvals: str | None = None
    prop_65: str | None = None
    with_accessories: str | None = None
    application_desc: str | None = None
    includes_desc: str | None = None
    product_name: str | None = None
    trade_name: str | None = None
    alternate_part_number: str | None = None
    discontinued: str | None = None

    # --- Dimensions & Weight ---
    length: str | None = None
    length_uom: str | None = None
    height: str | None = None
    height_uom: str | None = None
    width: str | None = None
    width_uom: str | None = None
    weight: str | None = None
    weight_uom: str | None = None
    volume: str | None = None
    volume_uom: str | None = None

    # --- Media & Documents (manufacturer domain ONLY) ---
    product_image_url: str | None = None            # Primary product image from manufacturer site
    alternate_image_urls: list[str] = Field(default_factory=list)  # Up to 4 alternate images
    spec_sheet_url: str | None = None               # PDF spec sheet URL (manufacturer site)
    sds_url: str | None = None                      # Safety Data Sheet URL (manufacturer site)
    manual_url: str | None = None                   # Owner/user manual URL
    installation_url: str | None = None             # Installation guide URL
    warranty_url: str | None = None                 # Warranty document URL
    catalog_url: str | None = None                  # Product catalog URL
    energy_guide_url: str | None = None             # Energy guide URL

    # --- Input CSV Passthrough (never leave these blank) ---
    input_part_desc: str | None = None
    input_e1_brand: str | None = None
    input_unilog_brand: str | None = None
    input_dib_brand: str | None = None
    input_part_manuf: str | None = None
    # --- Unilog Taxonomy Passthrough (from input CSV) ---
    part_number: str | None = None               # PART_NUMBER from input
    dept: str | None = None                      # Dept from input
    class_: str | None = None                    # Class from input
    fine: str | None = None                      # Fine from input
    sku_my_part_number: str | None = None        # SKU - MY_PART_NUMBER from input

    # --- Copywriter output ---
    brand_name: str | None = None                # Trademarked brand name (e.g. FRIGIDAIRE®)


# ---------------------------------------------------------------------------
# Request / Response models for FastAPI
# ---------------------------------------------------------------------------

class EnrichRequest(BaseModel):
    brand: str = Field(default="", max_length=200)
    mpn: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    part_manuf: str | None = None
    e1_brand: str | None = None
    unilog_brand: str | None = None
    dib_brand: str | None = None
    provided_schema: list[str] | None = None
    strict_schema: bool = False
    force_review: bool = False


class EnrichResponse(BaseModel):
    status: str
    product: ProductRecord | None = None
    error: str | None = None


class BatchResponse(BaseModel):
    total: int
    auto_completed: int
    needs_review: int
    failed: int
    results: list[dict[str, Any]]


class ReviewItem(BaseModel):
    product_id: str
    brand: str
    mpn: str
    category: str
    status: str
    overall_confidence: float
    flagged_count: int


class ResolveRequest(BaseModel):
    corrections: dict[str, Any]       # field_name → corrected_value
    reviewer: str = "human"


class SampleProduct(BaseModel):
    brand: str = ""
    mpn: str = ""
    description: str = ""
    part_manuf: str = ""
    e1_brand: str = ""
    unilog_brand: str = ""
    dib_brand: str = ""
    label: str = ""



