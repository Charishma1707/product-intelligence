"""
pipeline/hitl_agent.py — AI prompter agent for the human loop.
"""

from __future__ import annotations

import logging
import json
import os
import requests
from datetime import datetime, timezone
from pipeline.utils import generate_with_retry, parse_json_response
from pipeline.retriever import _search_web
from pipeline.nodes import node_taxonomy, node_extract

logger = logging.getLogger(__name__)

def execute_agent_prompt(state: dict, prompt: str) -> dict:
    """
    Agent controller for human prompts. Decides what components/tools to trigger:
      - Update taxonomy or category overrides
      - Add new attributes/fields to extract
      - Fetch custom URLs provided by human
      - Search web for custom queries
      - Re-run extraction or validate
    """
    logger.info("Executing Agent Prompt Router: %s", prompt)
    logs = state.get("logs", [])
    logs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "agent_prompter",
        "message": f"Human instruction received: '{prompt}'"
    })
    
    # 1. Ask the LLM to analyze the prompt and output a structured plan
    system_prompt = (
        "You are the master controller agent for a product specification pipeline.\n"
        "Analyze the human's instruction and decide which tools or nodes to execute.\n"
        "Return a JSON object with the following fields:\n"
        "{\n"
        "  \"run_taxonomy\": boolean, // True if the human wants to override the category, subcategory, or unspsc\n"
        "  \"taxonomy_overrides\": { // overrides to apply if run_taxonomy is True\n"
        "    \"category\": \"string or null\",\n"
        "    \"subcategory\": \"string or null\",\n"
        "    \"unspsc\": \"string or null\"\n"
        "  },\n"
        "  \"add_expected_fields\": [\"field_name_1\", \"field_name_2\"], // list of new spec attribute names the human wants to extract\n"
        "  \"custom_urls\": [\"url1\", \"url2\"], // specific URLs the human wants us to read/scrape\n"
        "  \"search_query\": \"string or null\", // Google search query if the human wants us to search for info\n"
        "  \"field_overrides\": { // direct value corrections\n"
        "    \"field_name\": \"value\"\n"
        "  },\n"
        "  \"reasoning\": \"Explain in 1-2 sentences your action plan based on the human request.\"\n"
        "}"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Product: {state.get('brand')} {state.get('mpn')}\nCurrent Category: {state.get('category')}\nHuman Instruction: {prompt}"}
    ]
    
    try:
        response_text = generate_with_retry(messages, response_format={"type": "json_object"})
        plan = parse_json_response(response_text)
        logger.info("Agent Plan: %s", plan)
    except Exception as e:
        logger.error("Failed to parse agent plan: %s", e)
        plan = {"reasoning": f"Failed to plan: {e}", "field_overrides": {}}
        
    reasoning = plan.get("reasoning", "Executing human instruction.")
    logs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "agent_prompter",
        "message": f"Agent Plan: {reasoning}"
    })
    
    # 2. Execute Plan: Taxonomy Overrides
    if plan.get("run_taxonomy") and plan.get("taxonomy_overrides"):
        to = plan["taxonomy_overrides"]
        if to.get("category"): state["category"] = to["category"]
        if to.get("subcategory"): state["subcategory"] = to["subcategory"]
        if to.get("unspsc"): state["unspsc"] = to["unspsc"]
        logger.info("Executing taxonomy resolution node with overrides: %s", to)
        state.update(node_taxonomy(state))
        
    # 3. Execute Plan: Add Expected Fields
    new_fields = plan.get("add_expected_fields") or []
    if new_fields:
        expected = state.get("expected_fields", [])
        for nf in new_fields:
            if nf not in expected:
                expected.append(nf)
        state["expected_fields"] = expected
        logger.info("Added new expected attributes: %s", new_fields)
        
    # 4. Scrape custom URLs or perform searches
    custom_urls = plan.get("custom_urls") or []
    search_q = plan.get("search_query")
    raw_docs = state.get("raw_documents", [])
    
    # Helper to fetch & scrape URL
    def scrape_url_text(url: str) -> str:
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text:
                    return text
        except Exception as e:
            logger.error("Trafilatura failed: %s", e)
        try:
            r = requests.get(url, timeout=10)
            return r.text[:8000]
        except Exception:
            return ""

    if custom_urls:
        for url in custom_urls:
            logger.info("Scraping custom URL: %s", url)
            text = scrape_url_text(url)
            if text:
                raw_docs.append({
                    "text": text[:10000],
                    "source_type": "webpage_text",
                    "url": url,
                    "doc_id": f"custom_{hash(url)}"
                })
                
    if search_q:
        logger.info("Performing google search for: %s", search_q)
        res = _search_web(state.get("brand"), state.get("mpn"), max_results=3, description=search_q)
        urls = res.get("all_urls", [])
        for url in urls:
            logger.info("Scraping search result URL: %s", url)
            text = scrape_url_text(url)
            if text:
                raw_docs.append({
                    "text": text[:10000],
                    "source_type": "webpage_text",
                    "url": url,
                    "doc_id": f"search_{hash(url)}"
                })
                
    state["raw_documents"] = raw_docs
    
    # 5. Re-run Extraction if search, scrape, taxonomy, or new fields were triggered
    if plan.get("run_taxonomy") or new_fields or custom_urls or search_q:
        logger.info("Executing extract node to refresh specifications...")
        state.update(node_extract(state))
        
    # 6. Apply direct field overrides
    field_overrides = plan.get("field_overrides") or {}
    if field_overrides:
        specs = state.get("specifications", {})
        for fname, val in field_overrides.items():
            if fname in specs:
                if isinstance(specs[fname], dict):
                    specs[fname]["value"] = val
                    specs[fname]["confidence"] = 1.0
                    specs[fname]["method"] = "human_verified"
                    specs[fname]["cause"] = f"Direct agent override: '{reasoning}'"
                else:
                    specs[fname].value = val
                    specs[fname].confidence = 1.0
                    specs[fname].method = "human_verified"
                    specs[fname].cause = f"Direct agent override: '{reasoning}'"
            else:
                specs[fname] = {
                    "value": val,
                    "confidence": 1.0,
                    "method": "human_verified",
                    "cause": f"Direct agent addition: '{reasoning}'",
                    "citation": None
                }
        state["specifications"] = specs
        logger.info("Applied direct field overrides: %s", field_overrides)
        
    state["logs"] = logs
    return state
