"""
pipeline/graph.py — LangGraph StateGraph definition.
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from pipeline.state import PipelineState
from pipeline.nodes import (
    node_identity,
    node_taxonomy,
    node_retrieve,
    node_series,
    node_extract,
    node_desc_infer,
    node_validate,
    node_review_gate,
    node_copywrite,
    node_finalize
)

logger = logging.getLogger(__name__)


def route_after_node(state: PipelineState) -> str:
    """Check if failed."""
    if state.get("status") == "failed":
        return "end"
    return "next"

def route_after_review(state: PipelineState) -> str:
    """Conditional routing based on review gate."""
    if state.get("status") == "failed":
        return "end"
    if state.get("status") == "needs_review":
        return "pause"
    return "next"


def build_graph() -> StateGraph:
    builder = StateGraph(PipelineState)

    builder.add_node("identity", node_identity)
    builder.add_node("taxonomy", node_taxonomy)
    builder.add_node("retrieve", node_retrieve)
    builder.add_node("series", node_series)
    builder.add_node("extract", node_extract)
    builder.add_node("desc_infer", node_desc_infer)
    builder.add_node("validate", node_validate)
    builder.add_node("review_gate", node_review_gate)
    builder.add_node("copywrite", node_copywrite)
    builder.add_node("finalize", node_finalize)

    builder.set_entry_point("identity")

    builder.add_conditional_edges("identity", route_after_node, {"end": END, "next": "taxonomy"})
    builder.add_conditional_edges("taxonomy", route_after_node, {"end": END, "next": "retrieve"})
    builder.add_conditional_edges("retrieve", route_after_node, {"end": END, "next": "series"})
    builder.add_conditional_edges("series", route_after_node, {"end": END, "next": "extract"})
    builder.add_conditional_edges("extract", route_after_node, {"end": END, "next": "desc_infer"})
    builder.add_conditional_edges("desc_infer", route_after_node, {"end": END, "next": "validate"})
    builder.add_conditional_edges("validate", route_after_node, {"end": END, "next": "review_gate"})
    
    builder.add_conditional_edges("review_gate", route_after_review, {
        "end": END, 
        "pause": END, # Pause for HITL
        "next": "copywrite"
    })
    
    builder.add_conditional_edges("copywrite", route_after_node, {"end": END, "next": "finalize"})
    builder.add_edge("finalize", END)

    return builder.compile()


def make_initial_state(
    brand: str,
    mpn: str,
    description: str,
    provided_schema: list[str] | None = None,
    strict_schema: bool = False,
    force_review: bool = False,
    product_id: str | None = None,
    job_id: str | None = None,
    # Input CSV passthrough fields
    part_number: str = "",
    dept: str = "",
    class_: str = "",
    fine: str = "",
    sku_my_part_number: str = "",
    input_e1_brand: str = "",
    input_unilog_brand: str = "",
    input_dib_brand: str = "",
    input_part_manuf: str = "",
    input_part_desc: str = "",
) -> PipelineState:
    import uuid
    pid = product_id or str(uuid.uuid4())
    jid = job_id or str(uuid.uuid4())
    return {
        "job_id": jid,
        "product_id": pid,
        "brand": brand,
        "mpn": mpn,
        "description": description,
        "provided_schema": provided_schema,
        "strict_schema": strict_schema,
        "force_review": force_review,
        "status": "in_progress",
        # Input CSV taxonomy passthrough
        "part_number": part_number,
        "dept": dept,
        "class_": class_,
        "fine": fine,
        "sku_my_part_number": sku_my_part_number,
        "input_e1_brand": input_e1_brand,
        "input_unilog_brand": input_unilog_brand,
        "input_dib_brand": input_dib_brand,
        "input_part_manuf": input_part_manuf,
        "input_part_desc": input_part_desc or description,
    }

if __name__ == "__main__":
    app = build_graph()
    print("Graph built successfully.")
