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
    WEBPAGE_TEXT = "webpage_text"
    PDF_TEXT = "pdf_text"
    PDF_TABLE = "pdf_table"
    PDF_CHART = "pdf_chart"
    USER_INPUT = "user_input"
    INFERRED = "inferred"


# ---------------------------------------------------------------------------
# Citation — full provenance for a single field value
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    """Exactly where a field value came from."""
    source_type: SourceType
    url: str | None = None                          # for webpage_text
    doc_id: str | None = None                       # UUID of the stored PDF
    doc_name: str | None = None                     # human-readable filename
    page_number: int | None = None                  # 1-indexed page within the PDF
    snippet: str | None = None                      # verbatim quote (webpage_text / pdf_text)
    table_location: str | None = None               # e.g. "Row 3, Column 'Rated Current'"
    chart_description: str | None = None            # e.g. "Read from torque-speed curve at 1500 rpm"
    similar_products_used: list[str] | None = None  # MPNs used for inference


# ---------------------------------------------------------------------------
# FieldValue — one spec field with full provenance
# ---------------------------------------------------------------------------

class FieldValue(BaseModel):
    """A single extracted/inferred specification field with full provenance."""
    value: str | float | int | bool | None
    confidence: float = Field(ge=0.0, le=1.0)
    method: str                                     # "extracted" | "inferred" | "human_verified"
    cause: str                                      # plain-English reason for this confidence
    citation: Citation


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
    brand: str = Field(..., min_length=1, max_length=200)
    mpn: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
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
    brand: str
    mpn: str
    description: str


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    fv = FieldValue(
        value="24 VDC",
        confidence=0.92,
        method="extracted",
        cause="Directly read from PDF text on page 1. Verbatim snippet matches source document.",
        citation=Citation(
            source_type=SourceType.PDF_TEXT,
            doc_id="abc-123",
            doc_name="3RT2015-1BB41.pdf",
            page_number=1,
            snippet="Control Coil Voltage: 24 V DC (operating coil)",
        ),
    )

    record = ProductRecord(
        brand="Siemens",
        mpn="3RT2015-1BB41",
        category="Contactor",
        description="Siemens SIRIUS 3RT2015-1BB41 Power Contactor",
        specifications={"coil_voltage": fv},
        overall_confidence=0.92,
        status="complete",
    )

    print(json.dumps(record.model_dump(), indent=2, default=str))
    print("\n[PASS] schema.py self-test passed.")
