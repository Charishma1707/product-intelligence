"""
orchestrator.py — Runs all 4 pipeline stages and assembles the final ProductRecord.

Also exposes an async batch function for concurrent processing with rate-limit protection.

Standalone test:
    cd backend
    python -m pipeline.orchestrator
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from schema import ProductRecord, FieldValue

logger = logging.getLogger(__name__)

_BATCH_CONCURRENCY = 5   # max simultaneous pipeline runs


# ---------------------------------------------------------------------------
# Single product pipeline
# ---------------------------------------------------------------------------

def run_pipeline(brand: str, mpn: str, description: str) -> ProductRecord:
    """
    Run the full 4-stage pipeline for a single product.
    Returns a ProductRecord on success.
    Raises on unrecoverable error (caller should catch for batch mode).
    """
    from pipeline.interpreter import interpret
    from pipeline.retriever import retrieve
    from pipeline.extractor import extract
    from pipeline.validator import validate

    logger.info("=== Pipeline START: %s %s ===", brand, mpn)

    # Stage 1 — Interpret
    logger.info("[Stage 1] Interpreting product category...")
    interp = interpret(brand, mpn, description)
    logger.info("[Stage 1] Category: %s | Fields: %s", interp.category, interp.expected_fields)

    # Stage 2 — Retrieve
    logger.info("[Stage 2] Retrieving product documentation...")
    ret = retrieve(brand, mpn, description, interp.category)
    logger.info("[Stage 2] Source: %s (%s) — %d chars", ret.source_url, ret.source_type, len(ret.text))

    # Stage 3 — Extract
    logger.info("[Stage 3] Extracting specification fields via LLM...")
    raw_fields = extract(
        brand=brand,
        mpn=mpn,
        description=description,
        category=interp.category,
        expected_fields=interp.expected_fields,
        retrieved_text=ret.text,
        source_url=ret.source_url,
    )
    logger.info("[Stage 3] Extracted %d fields", len(raw_fields))

    # Stage 4 — Validate
    logger.info("[Stage 4] Validating and scoring fields...")
    val = validate(
        raw_fields=raw_fields,
        raw_text=ret.text,
        source_url=ret.source_url,
        source_type=ret.source_type,
        description=description,
    )
    logger.info("[Stage 4] Overall confidence: %.2f | Flagged: %s", val.overall_confidence, val.flagged_for_review)

    record = ProductRecord(
        brand=brand,
        mpn=mpn,
        category=interp.category,
        subcategory=interp.subcategory,
        description=description,
        specifications=val.specifications,
        certifications=val.certifications,
        flagged_for_review=val.flagged_for_review,
        overall_confidence=val.overall_confidence,
    )

    logger.info("=== Pipeline END: %s %s ===", brand, mpn)
    return record


# ---------------------------------------------------------------------------
# Async wrapper so FastAPI can await it without blocking the event loop
# ---------------------------------------------------------------------------

async def run_pipeline_async(brand: str, mpn: str, description: str) -> ProductRecord:
    """Async wrapper that runs the synchronous pipeline in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_pipeline, brand, mpn, description)


# ---------------------------------------------------------------------------
# Batch processing with concurrency limit
# ---------------------------------------------------------------------------

async def run_batch_async(
    products: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Process a list of {brand, mpn, description} dicts concurrently.
    Returns list of result dicts (ProductRecord.model_dump() or error dicts).
    Uses a semaphore to limit concurrency to _BATCH_CONCURRENCY.
    """
    semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
    results: list[dict[str, Any]] = [{}] * len(products)

    async def _process(idx: int, product: dict[str, str]) -> None:
        brand = product.get("brand", "")
        mpn = product.get("mpn", "")
        description = product.get("description", "")
        async with semaphore:
            try:
                record = await run_pipeline_async(brand, mpn, description)
                results[idx] = {"status": "success", **record.model_dump()}
            except Exception as exc:
                logger.exception("Batch pipeline failed for %s %s: %s", brand, mpn, exc)
                results[idx] = {
                    "status": "failed",
                    "brand": brand,
                    "mpn": mpn,
                    "description": description,
                    "error": str(exc),
                }

    tasks = [_process(i, p) for i, p in enumerate(products)]
    await asyncio.gather(*tasks)
    return results


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)

    sample_products = [
        {"brand": "Siemens",           "mpn": "3RT2015-1BB41",    "description": "Contactor 3-pole 7A 24VDC coil"},
        {"brand": "Schneider Electric","mpn": "LC1D09BD",          "description": "TeSys D contactor 3-pole 9A 24VDC coil"},
        {"brand": "SKF",               "mpn": "6205-2RS1",         "description": "Deep groove ball bearing 25x52x15mm sealed"},
        {"brand": "FAG",               "mpn": "6204-2Z",           "description": "Ball bearing 20x47x14mm shielded"},
        {"brand": "Omron",             "mpn": "E2E-X5ME1",         "description": "Inductive proximity sensor 5mm sensing distance NPN"},
        {"brand": "Pepperl+Fuchs",     "mpn": "NBB5-18GM50-E0",    "description": "Inductive sensor M18 5mm NPN normally open"},
        {"brand": "ABB",               "mpn": "AF09-30-10-13",     "description": "Contactor 3-pole 9A 100-250V AC/DC coil"},
        {"brand": "Honeywell",         "mpn": "922AA1WA-A4",       "description": "Limit switch roller lever actuator SPDT"},
    ]

    print("\n=== Running batch pipeline on all 8 sample products ===\n")
    results = asyncio.run(run_batch_async(sample_products))

    for r in results:
        status = r.get("status", "?")
        brand = r.get("brand", "?")
        mpn = r.get("mpn", "?")
        conf = r.get("overall_confidence", "N/A")
        cat = r.get("category", "?")
        if status == "success":
            print(f"  [OK] {brand} {mpn} | {cat} | confidence={conf:.2f}")
        else:
            print(f"  [FAIL] {brand} {mpn} | FAILED: {r.get('error', '?')}")

    print("\n[PASS] orchestrator.py standalone test complete.")

