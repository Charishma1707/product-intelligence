"""
ui.py — Streamlit Enterprise 252-Column Product Intelligence Review Station.
"""

import streamlit as st
import os
from pathlib import Path
import json
import sqlite3

# Must be run from the backend directory
from pipeline.job_store import init_db as init_jobs, list_jobs, load_job, save_job, _get_conn as _get_job_conn
from pipeline.knowledge_store import (
    init_db as init_knowledge, 
    get_all_metrics, 
    save_human_review, 
    save_brand_alias, 
    save_series_knowledge,
    increment_metric
)
from pipeline.extractor import is_series_shared
from pipeline.nodes import node_copywrite, node_finalize
from pipeline.hitl_agent import execute_agent_prompt
from exporter import _split_uom

st.set_page_config(
    page_title="Unilog 252-Column Review Station", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Custom high-contrast, crystal-clear enterprise styling for readability
st.markdown("""
<style>
    /* Main Background & Text */
    .stApp { 
        background-color: #070a12 !important; 
        color: #f8fafc !important;
    }
    [data-testid="stSidebar"] { 
        background-color: #0c1220 !important; 
        border-right: 1px solid #1e293b !important;
    }
    
    /* Global Typography Visibility Overrides */
    p, span, div, label {
        color: #f1f5f9 !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-weight: 800 !important;
    }
    h1 { font-size: 1.7rem !important; margin-bottom: 0.2rem !important; }
    h2 { font-size: 1.35rem !important; margin-top: 0.4rem !important; margin-bottom: 0.4rem !important; }
    h3 { font-size: 1.15rem !important; margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    h4 { font-size: 1.0rem !important; margin-top: 0.2rem !important; margin-bottom: 0.2rem !important; }
    
    /* Sidebar text visibility */
    [data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #60a5fa !important;
        font-weight: 800 !important;
    }
    
    /* Form Labels - Bold & Clear */
    [data-testid="stWidgetLabel"] p, label, .stTextInput label, .stTextArea label, .stSelectbox label {
        font-size: 0.88rem !important;
        font-weight: 700 !important;
        color: #e2e8f0 !important;
        letter-spacing: 0.02em !important;
    }
    
    /* Captions - Readable Light Blue/Slate */
    .stCaption, [data-testid="stCaptionContainer"] p, small {
        color: #94a3b8 !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
    }
    
    /* Compact layout adjustments */
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; padding-left: 2rem; padding-right: 2rem; }
    
    /* Metric Card Display */
    div[data-testid="stMetricValue"] { 
        font-size: 1.45rem !important; 
        font-weight: 900 !important;
        color: #ffffff !important;
    }
    div[data-testid="stMetricLabel"] { 
        font-size: 0.82rem !important; 
        font-weight: 700 !important;
        color: #93c5fd !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    
    /* High-contrast Input Boxes */
    .stTextInput > div > div > input { 
        padding: 8px 12px; 
        font-size: 0.9rem; 
        background-color: #0f172a !important; 
        color: #ffffff !important; 
        border: 1.5px solid #334155 !important; 
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.3) !important;
    }
    .stTextArea > div > div > textarea { 
        font-size: 0.9rem; 
        background-color: #0f172a !important; 
        color: #ffffff !important; 
        border: 1.5px solid #334155 !important; 
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .stTextArea > div > div > textarea:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.3) !important;
    }
    
    /* Buttons - Enterprise Gradient */
    .stButton > button {
        background: linear-gradient(135deg, #0062cc 0%, #0080ff 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 8px 18px !important;
        box-shadow: 0 4px 14px rgba(0, 128, 255, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #0080ff 0%, #38bdf8 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(0, 128, 255, 0.5) !important;
    }
    
    /* Alert / Callout Boxes */
    [data-testid="stAlert"] {
        background-color: #0f172a !important;
        border: 1.5px solid #334155 !important;
        border-radius: 8px !important;
    }
    [data-testid="stAlert"] p {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
    }
    
    /* Section badge styling - Solid Enterprise Chips */
    .sec-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 800;
        margin-right: 6px;
        color: #ffffff !important;
    }
    .badge-blue { background: #0284c7; border: 1px solid #38bdf8; }
    .badge-purple { background: #7c3aed; border: 1px solid #c084fc; }
    .badge-green { background: #059669; border: 1px solid #34d399; }
    .badge-amber { background: #d97706; border: 1px solid #fbbf24; }
    
    /* Provenance Badges */
    .prov-chroma { background-color: #be185d; color: #ffffff !important; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 0.78rem; display: inline-block; }
    .prov-knowledge { background-color: #15803d; color: #ffffff !important; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 0.78rem; display: inline-block; }
    .prov-llm { background-color: #b45309; color: #ffffff !important; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 0.78rem; display: inline-block; }
    .prov-human { background-color: #1d4ed8; color: #ffffff !important; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 0.78rem; display: inline-block; }
    
    /* Expander styling */
    [data-testid="stExpander"] {
        background-color: #0f172a !important;
        border: 1.5px solid #1e293b !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary {
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }
    
    /* Table / DataFrame */
    [data-testid="stDataFrame"] {
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize DBs
init_jobs()
init_knowledge()

# ---------------------------------------------------------------------------
# TOP HEADER & COMPACT METRICS
# ---------------------------------------------------------------------------

h_col1, h_col2 = st.columns([1.5, 3.5])
with h_col1:
    st.markdown("## Unilog Review Station")
    st.caption("252-Column Provenance & Human Learning Engine")

metrics = get_all_metrics()
all_jobs = list_jobs(limit=500)
total_jobs = len(all_jobs)
completed_jobs = sum(1 for j in all_jobs if j.get("status") == "complete")
review_queue_jobs = sum(1 for j in all_jobs if j.get("status") in ("needs_review", "needs_review_identity", "needs_review_retrieval", "needs_review_extraction", "needs_review_final"))

with h_col2:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Searches Saved", metrics.get("searches_avoided", 0) + metrics.get("series_hits", 0) * 2)
    m2.metric("Documents Reused", metrics.get("documents_cached", 0))
    m3.metric("Series Cached", metrics.get("unique_series_cached", 0))
    m4.metric("Enriched", completed_jobs)
    m5.metric("In Review", review_queue_jobs)

st.write("")

# ---------------------------------------------------------------------------
# RESUME & LEARNING LOOP HELPER
# ---------------------------------------------------------------------------

def resume_and_learn(state: dict, corrections: dict, top_level_overrides: dict = None):
    current_status = state.get("status", "needs_review")
    
    if current_status == "needs_review_identity":
        if "brand" in corrections:
            state["brand"] = corrections["brand"]
        if "mpn" in corrections:
            state["mpn"] = corrections["mpn"]
        if "manufacturer_name" in corrections:
            state["manufacturer_name"] = corrections["manufacturer_name"]
            
        from pipeline.nodes import node_retrieve
        res_state = node_retrieve(state)
        state.update(res_state)
        state["status"] = "needs_review_retrieval"
        save_job(state)
        
    elif current_status == "needs_review_retrieval":
        url_fields = ["mfr_url", "spec_sheet_url", "manual_url", "installation_url", "warranty_url", "catalog_url", "energy_guide_url", "sds_url", "product_image_url"]
        for f in url_fields:
            if f in corrections:
                state[f] = corrections[f]
                
        from pipeline.nodes import node_taxonomy, node_series, node_extract
        state.update(node_taxonomy(state))
        state.update(node_series(state))
        state.update(node_extract(state))
        state["status"] = "needs_review_extraction"
        save_job(state)
        
    elif current_status in ("needs_review_extraction", "needs_review"):
        specs = state.get("specifications", {})
        brand = state.get("brand", "")
        series = state.get("series") or (specs.get("series", {}).get("value") if isinstance(specs.get("series"), dict) else getattr(specs.get("series"), "value", None))
        pid = state.get("product_id") or state.get("job_id")
        
        for fname, cval in corrections.items():
            if fname in specs:
                old_val = specs[fname].get("value") if isinstance(specs[fname], dict) else getattr(specs[fname], "value", None)
                if isinstance(specs[fname], dict):
                    specs[fname]["value"] = cval
                    specs[fname]["confidence"] = 1.0
                    specs[fname]["method"] = "human_verified"
                    specs[fname]["cause"] = "Verified and corrected by human reviewer."
                else:
                    specs[fname].value = cval
                    specs[fname].confidence = 1.0
                    specs[fname].method = "human_verified"
                    specs[fname].cause = "Verified and corrected by human reviewer."

                save_human_review(pid, fname, str(old_val), str(cval), "approved_with_correction")

                if series and is_series_shared(fname):
                    save_series_knowledge(
                        manufacturer=brand,
                        series=str(series),
                        attribute=fname,
                        value=str(cval),
                        scope="series",
                        confidence=1.0,
                        source="human_verified"
                    )
                    increment_metric("series_hits", 1)
            elif fname in ("category", "subcategory", "unspsc"):
                state[fname] = cval
                
        if top_level_overrides:
            for k, v in top_level_overrides.items():
                if v is not None and str(v).strip() != "":
                    state[k] = v

        state["specifications"] = specs
        
        from pipeline.nodes import node_validate, node_copywrite, node_finalize
        state.update(node_validate(state))
        state.update(node_copywrite(state))
        state.update(node_finalize(state))
        state["status"] = "needs_review_final"
        save_job(state)
        
    elif current_status == "needs_review_final":
        for k, v in corrections.items():
            state[k] = v
        state["status"] = "complete"
        save_job(state)

# ---------------------------------------------------------------------------
# MAIN TABS
# ---------------------------------------------------------------------------

tab_inspector, tab_master = st.tabs([
    "252-Column Product Inspector", 
    "Master Catalog Overview"
])

# ---------------------------------------------------------------------------
# TAB 1: 252-COLUMN PRODUCT INSPECTOR & REVIEW
# ---------------------------------------------------------------------------

with tab_inspector:
    with st.expander("Review Station Guide", expanded=False):
        st.markdown("""
        - **1. Select Product:** Choose a product from the left sidebar queue.
        - **2. Inspect & Edit:** Expand any section below to view sources, PDF snippets, and edit values or units.
        - **3. Value & Unit Split:** Measurements (like `120 V` or `41 dBA`) are split into **Value** and **Unit (UOM)** fields.
        - **4. Save & Learn:** Click **'Save Corrections & Learn'** at the bottom. Fixes are saved in SQLite and reused for all sibling products in the same series.
        """)

    # Sidebar setup
    st.sidebar.header("Product Queue")
    status_filter = st.sidebar.selectbox("Filter Status:", ["all", "needs_review", "complete"])
    dedup_latest = st.sidebar.checkbox("Show Latest per MPN", value=True)
    
    raw_jobs = list_jobs(status=status_filter if status_filter != "all" else None, limit=100)
    
    if dedup_latest:
        seen_mpns = set()
        filtered_jobs = []
        for j in raw_jobs:
            mpn_key = (j.get("brand", ""), j.get("mpn", ""))
            if mpn_key not in seen_mpns:
                seen_mpns.add(mpn_key)
                filtered_jobs.append(j)
    else:
        filtered_jobs = raw_jobs

    if not filtered_jobs:
        st.info("No products match the selected filter.")
        st.stop()

    selected_job_id = st.sidebar.radio(
        "Select Product to Review:",
        options=[job["job_id"] for job in filtered_jobs],
        format_func=lambda jid: next((f"{j['brand']} — {j['mpn']} ({j['status'].upper()})" for j in filtered_jobs if j["job_id"] == jid), jid)
    )

    if selected_job_id:
        state = load_job(selected_job_id)
        if not state:
            st.error("Could not load job state.")
            st.stop()

        specs = state.get("specifications", {})
        overall_conf = state.get("overall_confidence", 0.0)
        
        # -------------------------------------------------------------------
        # PROGRESSIVE STAGE BAR INDICATOR
        # -------------------------------------------------------------------
        current_status = state.get("status", "needs_review")
        
        stages_info = [
            ("needs_review_identity", "1. Identity"),
            ("needs_review_retrieval", "2. Sourcing URLs"),
            ("needs_review_extraction", "3. Extraction"),
            ("needs_review_final", "4. Final Description")
        ]
        
        cols = st.columns(4)
        for i, (stg_status, stg_label) in enumerate(stages_info):
            with cols[i]:
                if current_status == stg_status:
                    st.markdown(f"<div style='text-align:center; padding: 10px; background: rgba(0, 128, 255, 0.25); border: 2px solid #0080ff; border-radius: 8px; font-weight: 800; color: #ffffff !important; box-shadow: 0 0 15px rgba(0, 128, 255, 0.4);'>{stg_label} (Active)</div>", unsafe_allow_html=True)
                elif current_status in ("complete", "stopped"):
                    st.markdown(f"<div style='text-align:center; padding: 10px; background: rgba(16, 185, 129, 0.15); border: 1.5px solid #10b981; border-radius: 8px; color: #34d399 !important; font-weight: 700;'>{stg_label}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align:center; padding: 10px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #94a3b8 !important; font-weight: 600;'>{stg_label}</div>", unsafe_allow_html=True)
        
        st.write("")

        corrections = {}
        top_overrides = {}

        # -------------------------------------------------------------------
        # STAGE 1: IDENTITY REVIEW
        # -------------------------------------------------------------------
        if current_status == "needs_review_identity":
            st.markdown("### Step 1: Brand & Manufacturer Identity")
            st.info("Verify and correct the brand identity and part number. This controls the target websites search.")
            
            c1, c2, c3 = st.columns(3)
            corrections["brand"] = c1.text_input("Brand / Label Name:", value=state.get("brand") or "", key=f"brand_{selected_job_id}")
            corrections["manufacturer_name"] = c2.text_input("Manufacturer Name (Normalized):", value=state.get("manufacturer_name") or "", key=f"manuf_{selected_job_id}")
            corrections["mpn"] = c3.text_input("MPN (Manufacturer Part Number):", value=state.get("mpn") or "", key=f"mpn_{selected_job_id}")
            
            st.write("")
            if st.button("Approve Identity — Proceed to Sourcing", type="primary", use_container_width=True):
                with st.spinner("Finding websites, spec sheet PDFs, and alternate images..."):
                    resume_and_learn(state, corrections)
                st.success("Identity approved. Advanced to Step 2: Sourcing URLs.")
                st.rerun()

        # -------------------------------------------------------------------
        # STAGE 2: SOURCING URLs REVIEW
        # -------------------------------------------------------------------
        elif current_status == "needs_review_retrieval":
            st.markdown("### Step 2: Sourcing URLs & Datasheet Documents")
            st.info("Check and confirm official product websites, datasheet PDFs, manuals, and image assets.")
            
            u1, u2 = st.columns(2)
            corrections["mfr_url"] = u1.text_input("MFR URL (Official Product Page):", value=state.get("mfr_url") or "", key=f"mfr_url_{selected_job_id}")
            corrections["spec_sheet_url"] = u2.text_input("Specification Sheet URL (PDF):", value=state.get("spec_sheet_url") or "", key=f"spec_url_{selected_job_id}")
            
            r1, r2 = st.columns(2)
            corrections["manual_url"] = r1.text_input("Owners/User Manual URL (PDF):", value=state.get("manual_url") or "", key=f"manual_url_{selected_job_id}")
            corrections["installation_url"] = r2.text_input("Installation Guide URL (PDF):", value=state.get("installation_url") or "", key=f"install_url_{selected_job_id}")
            
            d1, d2 = st.columns(2)
            corrections["product_image_url"] = d1.text_input("Product Image Filename/URL:", value=state.get("product_image_url") or f"{state.get('brand')}_{state.get('mpn')}.jpg", key=f"img_{selected_job_id}")
            corrections["sds_url"] = d2.text_input("Safety Data Sheet (SDS) URL:", value=state.get("sds_url") or "", key=f"sds_url_{selected_job_id}")
            
            st.write("")
            if st.button("Approve Sourcing — Proceed to Extraction", type="primary", use_container_width=True):
                with st.spinner("Classifying taxonomy and extracting 252 specification columns..."):
                    resume_and_learn(state, corrections)
                st.success("Sourcing approved. Advanced to Step 3: Extraction.")
                st.rerun()

        # -------------------------------------------------------------------
        # STAGE 3: TAXONOMY & ATTRIBUTE EXTRACTION REVIEW
        # -------------------------------------------------------------------
        elif current_status in ("needs_review_extraction", "needs_review"):
            st.markdown("### Step 3: Taxonomy & Attribute Verification")
            st.caption("Extracted and inferred specification fields with explicit provenance and Value + Unit (UOM) splitting.")
            
            t1, t2, t3 = st.columns(3)
            corrections["category"] = t1.text_input("Category (Taxonomy Root):", value=state.get("category") or "", key=f"cat_{selected_job_id}")
            corrections["subcategory"] = t2.text_input("Subcategory (Taxonomy Leaf):", value=state.get("subcategory") or "", key=f"subcat_{selected_job_id}")
            corrections["unspsc"] = t3.text_input("UNSPSC Code:", value=state.get("unspsc") or "", key=f"unspsc_{selected_job_id}")
            
            st.write("---")
            
            if not specs:
                st.warning("No attributes extracted yet.")
            else:
                spec_keys = list(specs.keys())
                col_left, col_right = st.columns(2)
                
                for idx, fname in enumerate(spec_keys):
                    target_col = col_left if idx % 2 == 0 else col_right
                    spec_obj = specs[fname]
                    
                    val = spec_obj.get("value") if isinstance(spec_obj, dict) else getattr(spec_obj, "value", None)
                    conf = spec_obj.get("confidence", 0.5) if isinstance(spec_obj, dict) else getattr(spec_obj, "confidence", 0.5)
                    cause = spec_obj.get("cause", "") if isinstance(spec_obj, dict) else getattr(spec_obj, "cause", "")
                    snippet = spec_obj.get("citation", {}).get("snippet") if isinstance(spec_obj, dict) else getattr(getattr(spec_obj, "citation", None), "snippet", None)
                    
                    c_val, c_uom = _split_uom(str(val)) if val is not None else ("", "")
                    
                    is_bad_val = str(val).strip().lower() in ("yes", "no", "true", "false", "null", "none", "unknown", "display only")
                    badge_class = "badge-green" if conf >= 0.85 else "badge-amber" if conf >= 0.65 else "badge-blue"
                    
                    with target_col:
                        st.markdown(f"<div style='margin-bottom: 6px;'><span class='sec-badge {badge_class}'>{conf*100:.0f}% Conf</span> <strong style='font-size: 1rem; color: #ffffff !important;'>{fname.replace('_', ' ').title()}</strong></div>", unsafe_allow_html=True)
                        if is_bad_val:
                            st.error(f"Invalid placeholder '{val}'. Enter confirmed value:")
                        
                        v_c1, v_c2 = st.columns([2.2, 1.2])
                        new_v = v_c1.text_input("Value", value="" if is_bad_val else c_val, key=f"v_{fname}_{selected_job_id}", label_visibility="collapsed")
                        new_u = v_c2.text_input("UOM", value=c_uom, key=f"u_{fname}_{selected_job_id}", placeholder="Unit", label_visibility="collapsed")
                        
                        if snippet:
                            st.markdown(f"<div style='font-size:0.83rem; color:#93c5fd !important; background: rgba(0, 128, 255, 0.12); border: 1px solid rgba(0, 128, 255, 0.3); border-radius: 4px; padding: 6px 10px; margin: 4px 0 6px 0;'><i>\"{snippet[:120]}...\"</i></div>", unsafe_allow_html=True)
                            st.markdown("<div style='margin-bottom: 10px;'><span class='prov-chroma'>Source: ChromaDB / PDF Chunks</span></div>", unsafe_allow_html=True)
                        elif cause:
                            if "verified on" in cause.lower() or "pdf" in cause.lower():
                                st.markdown(f"<div style='font-size:0.82rem; color:#cbd5e1 !important; margin-bottom: 4px;'><b>Reason:</b> {cause[:100]}</div>", unsafe_allow_html=True)
                                st.markdown("<div style='margin-bottom: 10px;'><span class='prov-chroma'>Source: ChromaDB / PDF Chunks</span></div>", unsafe_allow_html=True)
                            elif "knowledge graph" in cause.lower() or "series" in cause.lower() or "reused" in cause.lower():
                                st.markdown(f"<div style='font-size:0.82rem; color:#cbd5e1 !important; margin-bottom: 4px;'><b>Reason:</b> {cause[:100]}</div>", unsafe_allow_html=True)
                                st.markdown("<div style='margin-bottom: 10px;'><span class='prov-knowledge'>Source: Knowledge Graph (Series Cache)</span></div>", unsafe_allow_html=True)
                            elif "human" in cause.lower():
                                st.markdown(f"<div style='font-size:0.82rem; color:#cbd5e1 !important; margin-bottom: 4px;'><b>Reason:</b> {cause[:100]}</div>", unsafe_allow_html=True)
                                st.markdown("<div style='margin-bottom: 10px;'><span class='prov-human'>Source: Human Verified</span></div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div style='font-size:0.82rem; color:#cbd5e1 !important; margin-bottom: 4px;'><b>Reason:</b> {cause[:100]}</div>", unsafe_allow_html=True)
                                st.markdown("<div style='margin-bottom: 10px;'><span class='prov-llm'>Source: Inferred from Description</span></div>", unsafe_allow_html=True)
                        
                        combined = f"{new_v.strip()} {new_u.strip()}".strip() if new_u.strip() else new_v.strip()
                        corrections[fname] = combined
                        st.write("---")
            
            # Category overrides
            d1, d2, d3, d4 = st.columns(4)
            top_overrides["length"] = d1.text_input("Length:", value=str(state.get("length") or "24"), key=f"l_{selected_job_id}")
            top_overrides["width"] = d2.text_input("Width:", value=str(state.get("width") or "24"), key=f"w_{selected_job_id}")
            top_overrides["height"] = d3.text_input("Height:", value=str(state.get("height") or "34"), key=f"h_{selected_job_id}")
            top_overrides["country_of_origin"] = d4.text_input("Country of Origin:", value=str(state.get("country_of_origin") or "US"), key=f"coo_{selected_job_id}")

            c1, c2 = st.columns(2)
            top_overrides["warranty"] = c1.text_input("Warranty Terms:", value=str(state.get("warranty") or "1 Year Manufacturer"), key=f"war_{selected_job_id}")
            top_overrides["selling_uom"] = c2.text_input("Selling UOM:", value=str(state.get("selling_uom") or "Each"), key=f"su_{selected_job_id}")
            
            st.write("")
            if st.button("Approve Specifications — Proceed to Descriptions", type="primary", use_container_width=True):
                with st.spinner("Generating commercial descriptions and taxonomy tags..."):
                    resume_and_learn(state, corrections, top_overrides)
                st.success("Specifications approved. Advanced to Step 4: Descriptions.")
                st.rerun()

        # -------------------------------------------------------------------
        # STAGE 4: FINAL DESCRIPTIONS REVIEW & AGENT INTERACTIVES
        # -------------------------------------------------------------------
        elif current_status == "needs_review_final":
            st.markdown("### Step 4: Commercial Copywriting & Taxonomy")
            st.info("Verify descriptions. Use the query console below to execute specific extraction tasks.")
            
            corrections["invoice_desc"] = st.text_input("INVOICE DESC (≤40 chars, ALL CAPS):", value=str(state.get("invoice_desc") or ""), max_chars=40, key=f"inv_{selected_job_id}")
            corrections["short_desc"] = st.text_area("SHORT DESC:", value=str(state.get("short_desc") or ""), key=f"short_{selected_job_id}", height=65)
            corrections["long_desc"] = st.text_area("LONG DESC:", value=str(state.get("long_desc") or ""), key=f"long_{selected_job_id}", height=90)
            
            # Interactive Prompter Panel
            st.write("---")
            st.markdown("#### Interactive Query Console")
            agent_prompt = st.text_input("Direct search query or parameter instruction:", key=f"agent_prompt_{selected_job_id}")
            
            if st.button("Execute Query & Enrich", use_container_width=True):
                if agent_prompt.strip():
                    with st.spinner("Executing query and updating state..."):
                        updated_state = execute_agent_prompt(state, agent_prompt)
                        # Re-run nodes to reflect updates
                        from pipeline.nodes import node_validate, node_copywrite, node_finalize
                        updated_state.update(node_validate(updated_state))
                        updated_state.update(node_copywrite(updated_state))
                        updated_state.update(node_finalize(updated_state))
                        save_job(updated_state)
                    st.success("Query executed. Updated product specifications.")
                    st.rerun()
                else:
                    st.warning("Please enter an instruction.")
            
            # Final submit actions
            st.write("---")
            b_col1, b_col2 = st.columns([1.5, 1])
            with b_col1:
                if st.button("Complete Enrichment & Persist", type="primary", use_container_width=True):
                    with st.spinner("Finalizing product details..."):
                        resume_and_learn(state, corrections)
                    st.success("Product finalized. Knowledge saved for series reuse.")
                    st.rerun()

            with b_col2:
                if st.button("Stop Pipeline", use_container_width=True):
                    state["status"] = "stopped"
                    save_job(state)
                    st.warning("Pipeline execution stopped.")
                    st.rerun()

        # -------------------------------------------------------------------
        # FINALIZED OR STOPPED READONLY SUMMARY VIEW
        # -------------------------------------------------------------------
        else:
            st.markdown(f"### {'Enrichment Complete' if current_status == 'complete' else 'Pipeline Stopped'}")
            st.json({
                "brand": state.get("brand"),
                "mpn": state.get("mpn"),
                "category": state.get("category"),
                "unspsc": state.get("unspsc"),
                "mfr_url": state.get("mfr_url"),
                "invoice_desc": state.get("invoice_desc"),
                "short_desc": state.get("short_desc")
            })
            if st.button("Reset to Step 1", use_container_width=True):
                state["status"] = "needs_review_identity"
                save_job(state)
                st.rerun()

# ---------------------------------------------------------------------------
# TAB 2: MASTER CATALOG OVERVIEW
# ---------------------------------------------------------------------------

with tab_master:
    with st.expander("Master Portfolio Guide", expanded=False):
        st.markdown("""
        - This table lists all products in the database.
        - Displays **Confidence %**, **Specs Extracted count**, **MFR Source URL**, and **Status**.
        - To edit a product, switch to the **'252-Column Product Inspector'** tab.
        """)

    master_rows = []
    for j in all_jobs:
        jid = j.get("job_id")
        jstate = load_job(jid) or j
        specs_count = len(jstate.get("specifications", {}))
        conf = jstate.get("overall_confidence", 0.0)
        status = jstate.get("status", "unknown").upper()
        mfr_u = jstate.get("mfr_url") or "Not found"
        
        master_rows.append({
            "Job ID": jid,
            "Brand": jstate.get("brand", "—"),
            "MPN": jstate.get("mpn", "—"),
            "Category Leaf": jstate.get("subcategory") or jstate.get("category") or "—",
            "UNSPSC": jstate.get("unspsc") or "—",
            "Confidence": f"{conf*100:.0f}%",
            "Specs Extracted": specs_count,
            "MFR Source URL": mfr_u[:45] + ("..." if len(mfr_u) > 45 else ""),
            "Status": "COMPLETE" if status == "COMPLETE" else "NEEDS_REVIEW" if status == "NEEDS_REVIEW" else status
        })
        
    st.dataframe(master_rows, use_container_width=True, height=280)
    st.markdown(f"**Total Records:** `{len(master_rows)}` | **Completed:** `{completed_jobs}` | **In Review:** `{review_queue_jobs}`")
