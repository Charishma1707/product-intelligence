import networkx as nx
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

G = nx.read_graphml('data/knowledge_graph.graphml')
nodes = list(G.nodes(data=True))
edges = list(G.edges(data=True))

with open('kg_dump.md', 'w', encoding='utf-8') as f:
    f.write('# Knowledge Graph Extract\n\n')
    f.write('## Nodes (54 Total)\n')
    for n, data in nodes:
        f.write(f"- **{n}**: {data}\n")
    
    f.write('\n## Edges (53 Total)\n')
    for u, v, data in edges:
        t = data.get("type", "")
        f.write(f"- {u} --[{t}]--> {v}\n")
