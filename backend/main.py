"""
main.py — FastAPI application for the Product Intelligence Pipeline.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from pydantic import BaseModel

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "unihack")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

from schema import (
    EnrichRequest, EnrichResponse, SampleProduct, ProductRecord, FieldValue, Citation
)
from pipeline.job_store import init_db, save_job, load_job, list_jobs
from pipeline.graph import build_graph, make_initial_state
from pipeline.state import PipelineState
from exporter import export_to_unilog_format

_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("main")

app = FastAPI(
    title="Product Intelligence Pipeline",
    description="Enriches minimal product info into a structured product record using LangGraph.",
    version="2.0.0",
)

@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info("Job store initialized.")

_SAMPLE_CSV = _BACKEND_DIR / "sample_data" / "sample_products.csv"

@app.get("/sample-products", response_model=list[SampleProduct])
async def get_sample_products():
    """Return the sample_products.csv as a JSON list for the frontend demo loader."""
    if not _SAMPLE_CSV.exists():
        raise HTTPException(status_code=404, detail="sample_products.csv not found")

    products: list[SampleProduct] = []
    with _SAMPLE_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(SampleProduct(
                brand=row["brand"].strip(),
                mpn=row["mpn"].strip(),
                description=row["description"].strip(),
            ))
    return products

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LGEnrichResponse(BaseModel):
    status: str
    job_id: str
    hitl_required: bool = False
    product: ProductRecord | None = None
    error: str | None = None


class HITLResumeRequest(BaseModel):
    job_id: str
    corrections: dict[str, Any]
    reviewer: str = "human"


def _state_to_record(state: PipelineState) -> ProductRecord:
    return ProductRecord(
        brand=state.get("brand", ""),
        mpn=state.get("mpn", ""),
        category=state.get("category", "Unknown"),
        classpath=state.get("classpath"),
        description=state.get("description", ""),
        invoice_desc=state.get("invoice_desc"),
        mobile_desc=state.get("mobile_desc"),
        short_desc=state.get("short_desc"),
        long_desc=state.get("long_desc"),
        retail_desc=state.get("retail_desc"),
        marketing_description=state.get("marketing_description"),
        item_features=state.get("item_features", []),
        unspsc=state.get("unspsc"),
        manufacturer_name=state.get("manufacturer_name"),
        brand_name=state.get("brand_name"),
        specifications=state.get("specifications", {}),
        flagged_for_review=state.get("flagged_for_review", []),
        logs=state.get("logs", []),
        overall_confidence=state.get("overall_confidence", 0.0),
        status=state.get("status", "failed"),
        product_id=state.get("product_id", ""),
        source_urls=state.get("source_urls", []),
        mfr_url=state.get("mfr_url"),
        ref_urls=state.get("ref_urls", []),
        # Commercial fields
        upc=state.get("upc"),
        ean=state.get("ean"),
        gtin=state.get("gtin"),
        warranty=state.get("warranty"),
        list_price=state.get("list_price"),
        selling_qty=state.get("selling_qty"),
        selling_uom=state.get("selling_uom"),
        standard_packaging_info=state.get("standard_packaging_info"),
        country_of_origin=state.get("country_of_origin"),
        standards_approvals=state.get("standards_approvals"),
        prop_65=state.get("prop_65"),
        with_accessories=state.get("with_accessories"),
        application_desc=state.get("application_desc"),
        includes_desc=state.get("includes_desc"),
        product_name=state.get("product_name"),
        trade_name=state.get("trade_name"),
        alternate_part_number=state.get("alternate_part_number"),
        discontinued=state.get("discontinued"),
        # Dimensions
        length=state.get("length"),
        length_uom=state.get("length_uom"),
        height=state.get("height"),
        height_uom=state.get("height_uom"),
        width=state.get("width"),
        width_uom=state.get("width_uom"),
        weight=state.get("weight"),
        weight_uom=state.get("weight_uom"),
        volume=state.get("volume"),
        volume_uom=state.get("volume_uom"),
        # Media & Documents (manufacturer domain only)
        product_image_url=state.get("product_image_url"),
        alternate_image_urls=state.get("alternate_image_urls", []),
        spec_sheet_url=state.get("spec_sheet_url"),
        sds_url=state.get("sds_url"),
        manual_url=state.get("manual_url"),
        installation_url=state.get("installation_url"),
        warranty_url=state.get("warranty_url"),
        catalog_url=state.get("catalog_url"),
        energy_guide_url=state.get("energy_guide_url"),
        # Input CSV passthrough
        input_part_desc=state.get("input_part_desc"),
        input_e1_brand=state.get("input_e1_brand"),
        input_unilog_brand=state.get("input_unilog_brand"),
        input_dib_brand=state.get("input_dib_brand"),
        input_part_manuf=state.get("input_part_manuf"),
        # Taxonomy passthrough
        part_number=state.get("part_number"),
        dept=state.get("dept"),
        class_=state.get("class_"),
        fine=state.get("fine"),
        sku_my_part_number=state.get("sku_my_part_number"),
    )


@app.post("/enrich/v2", response_model=LGEnrichResponse, tags=["LangGraph v2"])
async def enrich_v2(request: EnrichRequest, user: str = Depends(authenticate)):
    # Check for caching/deduplication
    existing_jobs = list_jobs(status="complete", limit=1000)
    for job in existing_jobs:
        if job.get("brand") == request.brand and job.get("mpn") == request.mpn:
            logger.info("Cache hit for %s %s. Returning existing completed job %s", request.brand, request.mpn, job["job_id"])
            return LGEnrichResponse(
                status="complete",
                job_id=job["job_id"],
                product=_state_to_record(job),
                hitl_required=False
            )

    job_id = str(uuid.uuid4())
    initial_state = make_initial_state(
        brand=request.brand,
        mpn=request.mpn,
        description=request.description,
        provided_schema=request.provided_schema,
        strict_schema=request.strict_schema,
        force_review=request.force_review,
        job_id=job_id,
    )

    loop = asyncio.get_running_loop()
    try:
        def _run():
            graph = build_graph()
            return graph.invoke(initial_state)

        final_state = await loop.run_in_executor(None, _run)
        save_job(final_state)

        record = _state_to_record(final_state)
        hitl = final_state.get("status") == "needs_review"

        return LGEnrichResponse(
            status=final_state.get("status", "failed"),
            job_id=job_id,
            product=record,
            hitl_required=hitl,
            error=final_state.get("error"),
        )
    except Exception as exc:
        logger.exception("LG pipeline v2 failed for %s %s", request.brand, request.mpn)
        return LGEnrichResponse(
            status="failed",
            job_id=job_id,
            error=str(exc),
        )


@app.post("/enrich/resume", response_model=LGEnrichResponse, tags=["LangGraph v2"])
async def resume_hitl(req: HITLResumeRequest, user: str = Depends(authenticate)):
    state = load_job(req.job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found.")
    if state.get("status") != "needs_review":
        raise HTTPException(
            status_code=400,
            detail=f"Job {req.job_id} is not in needs_review state.",
        )

    specs = state.get("specifications", {})
    for field_name, corrected_value in req.corrections.items():
        if field_name in specs:
            if hasattr(specs[field_name], "value"):
                specs[field_name].value = corrected_value
                specs[field_name].confidence = 1.0
                specs[field_name].method = "human_verified"
                specs[field_name].cause = f"Corrected by {req.reviewer}"
            else:
                specs[field_name]["value"] = corrected_value
                specs[field_name]["confidence"] = 1.0
                specs[field_name]["method"] = "human_verified"
                specs[field_name]["cause"] = f"Corrected by {req.reviewer}"

    state["specifications"] = specs
    state["status"] = "in_progress" # Resume

    # Re-compute overall confidence
    if specs:
        total_conf = 0
        for f in specs.values():
            if isinstance(f, dict):
                total_conf += f.get("confidence", 0)
            else:
                total_conf += getattr(f, "confidence", 0.0)
        state["overall_confidence"] = round(total_conf / len(specs), 3)

    # Resume from copywrite
    loop = asyncio.get_running_loop()
    try:
        def _run_resume():
            # Create a subgraph or just call nodes directly since we only have 2 left
            from pipeline.nodes import node_copywrite, node_finalize
            state.update(node_copywrite(state))
            state.update(node_finalize(state))
            return state

        final_state = await loop.run_in_executor(None, _run_resume)
        save_job(final_state)

        record = _state_to_record(final_state)
        return LGEnrichResponse(
            status=final_state.get("status", "completed"),
            job_id=req.job_id,
            product=record,
            hitl_required=False,
        )
    except Exception as exc:
        logger.exception("HITL resume failed for job %s", req.job_id)
        return LGEnrichResponse(status="failed", job_id=req.job_id, error=str(exc))


@app.get("/jobs", tags=["LangGraph v2"])
async def get_jobs(status: str | None = None, limit: int = 50):
    return {"jobs": list_jobs(status=status, limit=limit)}


@app.get("/jobs/{job_id}", tags=["LangGraph v2"])
async def get_job(job_id: str):
    state = load_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return _state_to_record(state)

@app.get("/export/csv", tags=["LangGraph v2"])
async def export_csv(status: str | None = "complete"):
    """
    Export all completed jobs as a CSV matching the 252-column Unilog format.
    Deduplicates by MPN so the same product is never written twice.
    """
    from fastapi.responses import PlainTextResponse

    # Load all jobs (or filter by status)
    summary_states = list_jobs(status=status, limit=1000)
    states = [load_job(s["job_id"]) for s in summary_states if load_job(s["job_id"]) is not None]
    records = [_state_to_record(s) for s in states]

    # Deduplicate by MPN — keep the most-recent record for each MPN
    seen_mpns: set[str] = set()
    deduped_records = []
    for rec in reversed(records):  # reversed so most-recent wins
        key = (rec.mpn or "").strip().upper()
        if key and key not in seen_mpns:
            seen_mpns.add(key)
            deduped_records.append(rec)
    deduped_records.reverse()  # restore original order

    if not deduped_records:
        raise HTTPException(status_code=404, detail="No records found to export.")

    csv_string = export_to_unilog_format(deduped_records)

    # Save a permanent copy on the backend
    try:
        with open("Master_Unilog_Output.csv", "w", encoding="utf-8") as f:
            f.write(csv_string)
        logger.info("Saved Master_Unilog_Output.csv (%d records, %d unique MPNs).",
                    len(records), len(deduped_records))
    except Exception as e:
        logger.error("Failed to save Master_Unilog_Output.csv: %s", e)

    return PlainTextResponse(
        content=csv_string,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Unilog_Submission.csv"}
    )

@app.get("/sample-products", tags=["LangGraph v2"])
async def get_sample_products():
    # Pull directly from the Unihack dataset instead of the mock CSV
    sample_file = _BACKEND_DIR.parent / "Unihack_ Sample Dataset - Input.csv"
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Unihack Sample Dataset not found")
    
    samples = []
    with open(sample_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 30: # Limit dropdown to 30 items
                break
                
            brand = (row.get("Part_Manuf") or row.get("E1_Brand") or "").strip()
            mpn = (row.get("Mfg_Part_Num") or "").strip()
            desc = (row.get("Part_Desc") or "").strip()
            
            # Skip empty or unbranded rows for a cleaner dropdown
            if not mpn or brand == "-- Unbranded --" or not brand:
                continue
                
            samples.append({
                "brand": brand,
                "mpn": mpn,
                "description": desc
            })
    return samples

@app.post("/enrich/batch", tags=["LangGraph v2"])
async def enrich_batch(
    file: UploadFile = File(...),
    provided_schema: str = Form(None),
    strict_schema: bool = Form(False),
    force_review: bool = Form(False),
    user: str = Depends(authenticate)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")
    
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
        
    reader = csv.DictReader(io.StringIO(text))
    
    schema_list = None
    if provided_schema:
        schema_list = [s.strip() for s in provided_schema.split(",") if s.strip()]

    results = []
    total = 0
    succeeded = 0
    failed = 0
    existing_jobs_cache = list_jobs(status="complete", limit=1000)
    
    loop = asyncio.get_running_loop()
    
    for row in reader:
        brand = (row.get("brand") or row.get("Part_Manuf") or "").strip()
        mpn = (row.get("mpn") or row.get("Mfg_Part_Num") or "").strip()
        desc = (row.get("description") or row.get("Part_Desc") or "").strip()

        # Capture all input CSV columns for passthrough
        input_e1_brand = (row.get("E1_Brand") or "").strip()
        input_unilog_brand = (row.get("Unilog_Brand") or "").strip()
        input_dib_brand = (row.get("DIB_Brand") or "").strip()
        input_part_manuf = (row.get("Part_Manuf") or "").strip()

        if not brand or not mpn:
            continue

        total += 1
        # Cache check
        cached_job = None
        for job in existing_jobs_cache:
            if job.get("brand") == brand and job.get("mpn") == mpn:
                cached_job = job
                break
                
        if cached_job:
            logger.info("Batch cache hit for %s %s. Skipping pipeline.", brand, mpn)
            record = _state_to_record(cached_job)
            results.append({
                "brand": record.brand,
                "mpn": record.mpn,
                "category": record.category,
                "overall_confidence": record.overall_confidence,
                "flagged_for_review": record.flagged_for_review,
                "status": "success",
                "error": None
            })
            succeeded += 1
            continue

        job_id = str(uuid.uuid4())
        initial_state = make_initial_state(
            brand=brand,
            mpn=mpn,
            description=desc,
            provided_schema=schema_list,
            strict_schema=strict_schema,
            force_review=force_review,
            job_id=job_id,
            # Pass ALL input CSV columns through
            part_number=(row.get("PART_NUMBER") or "").strip(),
            dept=(row.get("Dept") or "").strip(),
            class_=(row.get("Class") or "").strip(),
            fine=(row.get("Fine") or "").strip(),
            sku_my_part_number=(row.get("SKU - MY_PART_NUMBER") or "").strip(),
            input_e1_brand=(row.get("E1_Brand") or "").strip(),
            input_unilog_brand=(row.get("Unilog_Brand") or "").strip(),
            input_dib_brand=(row.get("DIB_Brand") or "").strip(),
            input_part_manuf=(row.get("Part_Manuf") or "").strip(),
            input_part_desc=desc,
        )
        
        try:
            def _run():
                from pipeline.graph import build_graph
                graph = build_graph()
                return graph.invoke(initial_state)

            final_state = await loop.run_in_executor(None, _run)
            save_job(final_state)
            # Add to local cache list so duplicates in the SAME batch are also cached
            if final_state.get("status") in ("completed", "needs_review"):
                existing_jobs_cache.append(final_state)
            
            record = _state_to_record(final_state)
            results.append({
                "brand": record.brand,
                "mpn": record.mpn,
                "category": record.category,
                "overall_confidence": record.overall_confidence,
                "flagged_for_review": record.flagged_for_review,
                "status": "success" if record.status in ("completed", "needs_review") else "failed",
                "error": final_state.get("error")
            })
            if record.status in ("completed", "needs_review"):
                succeeded += 1
            else:
                failed += 1
                
        except Exception as e:
            logger.exception("Batch LG v2 failed")
            results.append({
                "brand": brand,
                "mpn": mpn,
                "status": "failed",
                "error": str(e)
            })
            failed += 1
            
    return {
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "results": results
    }
