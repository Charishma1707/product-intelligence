"""
pipeline/knowledge_graph.py — Phase 4: Knowledge Graph

Uses NetworkX to build an in-memory knowledge graph of validated product facts,
and persists it to a .graphml file. Also provides a basic GraphRAG query interface.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

_GRAPH_FILE = Path(__file__).parent.parent / "data" / "knowledge_graph.graphml"

# Ensure data directory exists
_GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_graph() -> nx.MultiDiGraph:
    """Load existing graph or create a new one."""
    if _GRAPH_FILE.exists():
        try:
            return nx.read_graphml(_GRAPH_FILE)
        except Exception as exc:
            logger.warning("Failed to load graph %s: %s", _GRAPH_FILE, exc)
    return nx.MultiDiGraph()


def _save_graph(G: nx.MultiDiGraph) -> None:
    """Save graph to local file."""
    try:
        nx.write_graphml(G, _GRAPH_FILE)
    except Exception as exc:
        logger.error("Failed to save knowledge graph: %s", exc)


def ingest_validated_product(brand: str, mpn: str, category: str, specs: dict[str, Any]) -> None:
    """
    Ingest a validated product into the Knowledge Graph.
    Nodes: Product, Category, Feature/Value
    Edges: BELONGS_TO, HAS_SPEC
    """
    G = _load_graph()
    
    product_id = f"Product:{brand}:{mpn}"
    category_id = f"Category:{category}"

    # Upsert Product Node
    if not G.has_node(product_id):
        G.add_node(product_id, type="Product", brand=brand, mpn=mpn, name=f"{brand} {mpn}")
    
    # Upsert Category Node & Link
    if not G.has_node(category_id):
        G.add_node(category_id, type="Category", name=category)
    G.add_edge(product_id, category_id, type="BELONGS_TO")

    # Upsert Specs
    for spec_name, spec_data in specs.items():
        val_attr = getattr(spec_data, "value", None)
        if val_attr is not None:
            val = str(val_attr)
            value_id = f"SpecValue:{spec_name}:{val}"
            
            if not G.has_node(value_id):
                G.add_node(value_id, type="SpecValue", field=spec_name, value=val, name=f"{spec_name}={val}")
            
            # Link Product -> SpecValue
            G.add_edge(product_id, value_id, type="HAS_SPEC")

    _save_graph(G)
    logger.info("Ingested %s into Knowledge Graph (Nodes: %d, Edges: %d)", product_id, G.number_of_nodes(), G.number_of_edges())


def query_related_specs(category: str) -> str:
    """
    GraphRAG query: Given a category, find common specification fields and values
    to help the copywriter agent ground its generation in graph facts.
    """
    G = _load_graph()
    category_id = f"Category:{category}"
    
    if not G.has_node(category_id):
        return ""
    
    # Find products in this category
    products = [u for u, v, data in G.edges(data=True) if v == category_id and data.get("type") == "BELONGS_TO"]
    
    if not products:
        return ""
    
    # Aggregate specs for these products
    specs_freq: dict[str, set[str]] = {}
    for p in products:
        # Find all HAS_SPEC edges from this product
        spec_nodes = [v for u, v, data in G.edges(p, data=True) if data.get("type") == "HAS_SPEC"]
        for sn in spec_nodes:
            field = G.nodes[sn].get("field")
            val = G.nodes[sn].get("value")
            if field and val:
                specs_freq.setdefault(field, set()).add(val)
                
    # Format output for LLM context
    lines = [f"Common features for {category} in Knowledge Graph:"]
    for field, values in list(specs_freq.items())[:5]: # Top 5 specs
        v_str = ", ".join(list(values)[:3])
        if len(values) > 3:
            v_str += "..."
        lines.append(f" - {field}: e.g., {v_str}")
        
    return "\n".join(lines)
