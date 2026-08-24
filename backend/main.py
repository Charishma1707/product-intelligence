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


from schema import (
    EnrichRequest, EnrichResponse, SampleProduct, ProductRecord, FieldValue, Citation
)
from pipeline.job_store import init_db as init_job_store, save_job, load_job, list_jobs
from pipeline.knowledge_store import init_db as init_knowledge_store
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

import subprocess

@app.post("/reset")
async def reset_pipeline():
    try:
        # Allow passing the correct python executable
        subprocess.run(['python', 'reset_pipeline.py'], check=True, cwd=str(Path(__file__).parent))
        return {"status": "success", "message": "Pipeline completely reset!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.on_event("startup")
async def startup_event():
    try:
        init_job_store()
    except Exception as e:
        logger.error(f"Failed to init job store: {e}")
    try:
        init_knowledge_store()
    except Exception as e:
        logger.error(f"Failed to init knowledge store: {e}")
    logger.info("Stores initialized.")

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
    implicit_boost_count: int = 0
    post_approval_summary: dict | None = None


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
        specifications=state.get("specifications") or state.get("extracted_fields") or {},
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
async def enrich_v2(request: EnrichRequest):
    effective_brand = request.brand or request.part_manuf or request.e1_brand or ""
    # Check for caching/deduplication — return if already processed (complete OR pending review)
    all_cached_jobs = list_jobs(limit=2000)
    for job in all_cached_jobs:
        job_status = job.get("status", "")
        if job.get("mpn") == request.mpn and job.get("brand", "").lower() == effective_brand.lower():
            if job_status == "complete":
                logger.info("[Cache] Returning already-completed job %s for %s %s", job["job_id"], effective_brand, request.mpn)
                full_job = load_job(job["job_id"]) or job
                return LGEnrichResponse(
                    status="complete",
                    job_id=job["job_id"],
                    product=_state_to_record(full_job),
                    hitl_required=False
                )
            elif job_status.startswith("needs_review"):
                logger.info("[Cache] Returning in-progress HITL job %s for %s %s", job["job_id"], effective_brand, request.mpn)
                full_job = load_job(job["job_id"]) or job
                return LGEnrichResponse(
                    status=job_status,
                    job_id=job["job_id"],
                    product=_state_to_record(full_job),
                    hitl_required=True
                )

    job_id = str(uuid.uuid4())
    initial_state = make_initial_state(
        brand=effective_brand,
        mpn=request.mpn,
        description=request.description,
        provided_schema=request.provided_schema,
        strict_schema=request.strict_schema,
        force_review=request.force_review,
        job_id=job_id,
        input_part_manuf=request.part_manuf or "",
        input_e1_brand=request.e1_brand or "",
        input_unilog_brand=request.unilog_brand or "",
        input_dib_brand=request.dib_brand or "",
        input_part_desc=request.description or "",
    )

    loop = asyncio.get_running_loop()
    try:
        def _run():
            from pipeline.nodes import node_identity, node_taxonomy
            id_update = node_identity(initial_state)
            initial_state.update(id_update)
            tax_update = node_taxonomy(initial_state)
            initial_state.update(tax_update)
            initial_state["status"] = "needs_review_identity"
            return initial_state

        final_state = await loop.run_in_executor(None, _run)
        save_job(final_state)

        record = _state_to_record(final_state)
        hitl = True

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
async def resume_hitl(req: HITLResumeRequest):
    state = load_job(req.job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found.")
    
    current_status = state.get("status", "needs_review")
    valid_review_statuses = (
        "needs_review", "needs_review_identity", "needs_review_retrieval",
        "needs_review_extraction", "needs_review_final", "needs_review_delivery"
    )
    if current_status not in valid_review_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Job {req.job_id} is in status '{current_status}' and cannot be resumed.",
        )

    loop = asyncio.get_running_loop()
    try:
        from pipeline.nodes import node_hitl_supervisor, apply_implicit_confidence_boost, node_post_approval_persist

        implicit_boost_count = 0
        post_approval_summary = None

        def _run_supervisor():
            nonlocal implicit_boost_count, post_approval_summary
            # Detect if human advanced without making any field changes
            no_field_changes = len(req.corrections) == 0
            stage_map = {
                "needs_review_identity": 1,
                "needs_review_retrieval": 2,
                "needs_review_extraction": 3,
                "needs_review": 3,
                "needs_review_final": 4,
                "needs_review_delivery": 5,
            }
            stage_num = stage_map.get(current_status, 3)

            if no_field_changes and stage_num in (1, 2, 3, 4, 5):
                updated_state, boosted = apply_implicit_confidence_boost(
                    state, stage_num, req.corrections, req.reviewer
                )
                implicit_boost_count = len(boosted)
                state.update(updated_state)

            # If Stage 5 final delivery accept → run post-approval persist
            if current_status == "needs_review_delivery":
                result = node_post_approval_persist(state, req.reviewer)
                state.update(result)
                post_approval_summary = state.get("post_approval_summary")
                return state

            return node_hitl_supervisor(state, req.corrections, req.reviewer)

        state = await loop.run_in_executor(None, _run_supervisor)
        save_job(state)

        record = _state_to_record(state)
        hitl = state.get("status") in (
            "needs_review_identity", "needs_review_retrieval",
            "needs_review_extraction", "needs_review_final", "needs_review_delivery"
        )

        return LGEnrichResponse(
            status=state.get("status", "complete"),
            job_id=req.job_id,
            product=record,
            hitl_required=hitl,
            implicit_boost_count=implicit_boost_count,
            post_approval_summary=post_approval_summary,
        )
    except Exception as exc:
        logger.exception("HITL resume failed for job %s", req.job_id)
        return LGEnrichResponse(status="failed", job_id=req.job_id, error=str(exc))


class HITLAgentPromptRequest(BaseModel):
    job_id: str
    prompt: str


@app.post("/enrich/agent/prompt", response_model=LGEnrichResponse, tags=["LangGraph v2"])
async def agent_prompt(req: HITLAgentPromptRequest):
    state = load_job(req.job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found.")

    from pipeline.hitl_agent import execute_agent_prompt
    from pipeline.nodes import node_validate, node_copywrite, node_finalize

    loop = asyncio.get_running_loop()
    try:
        def _run_agent():
            s = execute_agent_prompt(state, req.prompt)
            # Re-run nodes to reflect the updates
            s.update(node_validate(s))
            s.update(node_copywrite(s))
            s.update(node_finalize(s))
            s["status"] = "needs_review_final"
            return s

        updated_state = await loop.run_in_executor(None, _run_agent)
        save_job(updated_state)

        record = _state_to_record(updated_state)
        return LGEnrichResponse(
            status="needs_review_final",
            job_id=req.job_id,
            product=record,
            hitl_required=True,
        )
    except Exception as exc:
        logger.exception("Agent prompt execution failed for job %s", req.job_id)
        return LGEnrichResponse(status="failed", job_id=req.job_id, error=str(exc))


class HITLStopRequest(BaseModel):
    job_id: str


@app.post("/enrich/stop", response_model=LGEnrichResponse, tags=["LangGraph v2"])
async def stop_enrich(req: HITLStopRequest):
    state = load_job(req.job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found.")

    state["status"] = "stopped"
    save_job(state)

    record = _state_to_record(state)
    return LGEnrichResponse(
        status="stopped",
        job_id=req.job_id,
        product=record,
        hitl_required=False,
    )


@app.get("/metrics", tags=["Metrics"])
async def get_metrics():
    from pipeline.knowledge_store import get_all_metrics
    return get_all_metrics()


@app.get("/test-jobs")
async def test_jobs():
    try:
        from pipeline.job_store import list_jobs
        res = list_jobs()
        return {"count": len(res), "items": res}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.get("/jobs", tags=["LangGraph v2"])
async def get_jobs(status: str | None = None, limit: int = 50):
    try:
        jobs_data = list_jobs(status=status, limit=limit)
        return JSONResponse(status_code=200, content={"jobs": jobs_data})
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        return JSONResponse(status_code=200, content={"jobs": []})


@app.get("/jobs/{job_id}", tags=["LangGraph v2"])
async def get_job(job_id: str):
    state = load_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    try:
        return _state_to_record(state)
    except Exception as e:
        logger.error(f"Error building record for job {job_id}: {e}")
        return JSONResponse(status_code=200, content=state)


class ExportSaveRequest(BaseModel):
    job_id: str | None = None


@app.post("/export/save", tags=["LangGraph v2"])
async def export_save(req: ExportSaveRequest):
    """
    Persist the final product record to the product_attributes DB table.
    If job_id is provided, saves that specific job. Otherwise saves all complete jobs.
    """
    from pipeline.knowledge_store import save_product_attribute

    if req.job_id:
        states = [load_job(req.job_id)]
        states = [s for s in states if s]
    else:
        summary_states = list_jobs(status="complete", limit=1000)
        states = [load_job(s["job_id"]) for s in summary_states]
        states = [s for s in states if s]

    saved_count = 0
    for state in states:
        brand = state.get("brand", "")
        mpn = state.get("mpn", "")
        specs = state.get("specifications", {})
        for fname, fval_obj in specs.items():
            val = (fval_obj.get("value") if isinstance(fval_obj, dict)
                   else getattr(fval_obj, "value", None))
            conf = (fval_obj.get("confidence", 0.0) if isinstance(fval_obj, dict)
                    else getattr(fval_obj, "confidence", 0.0))
            if val is not None:
                try:
                    save_product_attribute(brand, mpn, fname, str(val), conf, "pipeline", user)
                    saved_count += 1
                except Exception:
                    pass

    return {"status": "saved", "attributes_saved": saved_count, "products_saved": len(states)}

@app.get("/export/csv", tags=["LangGraph v2"])
async def export_csv(status: str | None = "complete"):
    """
    Export all completed jobs as a CSV matching the 252-column Unilog format.
    Deduplicates by MPN so the same product is never written twice.
    """
    from fastapi.responses import PlainTextResponse

    # Load all jobs (or filter by status, falling back to all if empty)
    summary_states = list_jobs(status=status, limit=1000)
    if not summary_states and status:
        summary_states = list_jobs(status=None, limit=1000)

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
        # Return header-only CSV instead of 404 error
        from exporter import UNILOG_HEADERS
        csv_string = ",".join(UNILOG_HEADERS) + "\n"
    else:
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

DEFAULT_SAMPLES = [
    SampleProduct(
        brand="3M",
        mpn="3MABR-7100075690",
        description="3M 775L Stikit Film P180 - Cubitron II 50 Disc/Box",
        part_manuf="3M",
        e1_brand="3M",
        unilog_brand="3M",
        dib_brand="3M",
        label="3M — 3MABR-7100075690 (Cubitron II Disc)"
    ),
    SampleProduct(
        brand="Schneider Electric",
        mpn="SQD-HOM2150",
        description="Square D Homeline 150 Amp Two-Pole Circuit Breaker",
        part_manuf="Schneider Electric",
        e1_brand="Square D",
        unilog_brand="Schneider Electric",
        dib_brand="Square D",
        label="Schneider Electric — SQD-HOM2150 (Circuit Breaker)"
    ),
    SampleProduct(
        brand="DEWALT",
        mpn="DCD791B",
        description="DEWALT 20V MAX XR Cordless Drill/Driver 1/2-Inch Tool Only",
        part_manuf="DEWALT",
        e1_brand="Dewalt",
        unilog_brand="DEWALT",
        dib_brand="Dewalt",
        label="DEWALT — DCD791B (20V Cordless Drill)"
    ),
    SampleProduct(
        brand="Milwaukee",
        mpn="2767-20",
        description="Milwaukee M18 FUEL 1/2 High Torque Impact Wrench Friction Ring",
        part_manuf="Milwaukee Tool",
        e1_brand="Milwaukee",
        unilog_brand="Milwaukee Tool",
        dib_brand="Milwaukee",
        label="Milwaukee — 2767-20 (Impact Wrench)"
    ),
    SampleProduct(
        brand="Fluke",
        mpn="FLUKE-117",
        description="Fluke 117 Electrician's Multimeter with Non-Contact Voltage",
        part_manuf="Fluke Corporation",
        e1_brand="Fluke",
        unilog_brand="Fluke",
        dib_brand="Fluke",
        label="Fluke — FLUKE-117 (Digital Multimeter)"
    )
]

@app.get("/sample-products", tags=["LangGraph v2"], response_model=list[SampleProduct])
async def get_sample_products():
    # Search for sample dataset file (checking common naming variations)
    possible_files = [
        _BACKEND_DIR.parent / "Unihack_ Sample Dataset - Input.csv",
        _BACKEND_DIR.parent / "Unihack_Sample_Dataset_Input.csv",
        _BACKEND_DIR.parent / "Unihack_Sample_Dataset - Input.csv",
        _BACKEND_DIR.parent / "sample_input.csv",
    ]
    sample_file = next((f for f in possible_files if f.exists()), None)
    if not sample_file:
        return DEFAULT_SAMPLES
    
    samples = []
    try:
        with open(sample_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=2):  # Row 2 is the first data row
                if len(samples) >= 30: # Limit dropdown to 30 items
                    break
                    
                manuf = (row.get("Part_Manuf") or "").strip()
                e1 = (row.get("E1_Brand") or "").strip()
                unilog = (row.get("Unilog_Brand") or "").strip()
                dib = (row.get("DIB_Brand") or "").strip()
                mpn = (row.get("Mfg_Part_Num") or "").strip()
                desc = (row.get("Part_Desc") or "").strip()
                
                if not mpn:
                    continue
                    
                label = f"[Row {i}] {mpn} — {desc[:35]}..." if desc else f"[Row {i}] {mpn}"
                
                samples.append(SampleProduct(
                    brand=manuf or e1 or "",
                    mpn=mpn,
                    description=desc,
                    part_manuf=manuf,
                    e1_brand=e1,
                    unilog_brand=unilog,
                    dib_brand=dib,
                    label=label
                ))
    except Exception as e:
        logger.warning(f"Could not parse sample file: {e}")
        return DEFAULT_SAMPLES

    return samples if samples else DEFAULT_SAMPLES

@app.post("/enrich/batch", tags=["LangGraph v2"])
async def enrich_batch(
    file: UploadFile = File(...),
    provided_schema: str = Form(None),
    strict_schema: bool = Form(False),
    force_review: bool = Form(False)
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
            if final_state.get("status") in ("complete", "needs_review"):
                existing_jobs_cache.append(final_state)
            
            record = _state_to_record(final_state)
            results.append({
                "brand": record.brand,
                "mpn": record.mpn,
                "category": record.category,
                "overall_confidence": record.overall_confidence,
                "flagged_for_review": record.flagged_for_review,
                "status": "success" if record.status in ("complete", "needs_review") else "failed",
                "error": final_state.get("error")
            })
            if record.status in ("complete", "needs_review"):
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
