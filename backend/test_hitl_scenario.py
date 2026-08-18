"""Test HITL scenario: truncated doc forces inference + tests KG with 2 products."""
import os
from pathlib import Path

os.chdir(Path(__file__).parent)

# First, run with full doc (Siemens)
from pipeline.graph import build_graph, make_initial_state

# Test 1: SKF bearing (should have its own reference doc)
print("="*60)
print("TEST 1: SKF 6205-2RS1 (bearing)")
print("="*60)
state1 = make_initial_state(brand="SKF", mpn="6205-2RS1", description="Deep groove ball bearing sealed", job_id="test-skf")
graph1 = build_graph()
final1 = graph1.invoke(state1)
specs1 = final1.get('specifications', {})
print(f"Status: {final1.get('status')}")
print(f"Overall confidence: {final1.get('overall_confidence')}")
print(f"HITL required: {final1.get('hitl_required')}")
print(f"Fields: {len(specs1)}")
for fname, f in specs1.items():
    print(f"  {fname}: {f['value']} ({f['method']}, conf={f['confidence']:.2f})")
    if f.get('citation') and f['citation'].get('verbatim_snippet'):
        print(f"    -> Found in doc: \"{f['citation']['verbatim_snippet'][:80]}\"")
    elif f['method'] == 'inferred':
        print(f"    -> Source: AI Domain Knowledge (no doc evidence)")

# Check KG now has both products
print("\n" + "="*60)
print("KNOWLEDGE GRAPH STATE")
print("="*60)
import networkx as nx
kg = Path("data/knowledge_graph.graphml")
if kg.exists():
    G = nx.read_graphml(kg)
    print(f"Total Nodes: {G.number_of_nodes()}")
    print(f"Total Edges: {G.number_of_edges()}")
    products = [n for n, d in G.nodes(data=True) if d.get('type') == 'Product']
    categories = [n for n, d in G.nodes(data=True) if d.get('type') == 'Category']
    specs = [n for n, d in G.nodes(data=True) if d.get('type') == 'SpecValue']
    print(f"Products: {len(products)}")
    for p in products:
        print(f"  - {G.nodes[p].get('name')}")
    print(f"Categories: {len(categories)}")
    for c in categories:
        print(f"  - {G.nodes[c].get('name')}")
    print(f"Spec Values: {len(specs)}")

# Test GraphRAG query
from pipeline.knowledge_graph import query_related_specs
print("\nGraphRAG Query for 'Electrical Switchgear':")
print(query_related_specs("Electrical Switchgear"))
print("\nGraphRAG Query for 'Bearings':")
print(query_related_specs("Bearings"))
