#!/usr/bin/env python3
"""Read-only metrics for the rebuilt good-dog graph. Run with the repo .venv
(ladybug 0.17.1). Reports counts + fragmentation computed several ways so the
comparison to the old baseline is unambiguous, plus an edge integrity sample."""
import sys
try:
    import ladybug as lb
except ImportError:
    import real_ladybug as lb
import networkx as nx
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else "data/graph.lbug"
db = lb.Database(path, read_only=True, buffer_pool_size=256 * 1024 * 1024)
conn = lb.Connection(db)


def rows(q):
    r = conn.execute(q)
    out = []
    while r.has_next():
        out.append(r.get_next())
    return out

n_ent = rows("MATCH (e:Entity) RETURN count(e)")[0][0]
n_doc = rows("MATCH (d:Document) RETURN count(d)")[0][0]
ee = rows(
    "MATCH (a:Entity)-[r]->(b:Entity) "
    "RETURN a.id, a.label, b.id, b.label, r.edge_type, r.evidence"
)
n_edge = len(ee)

# edge_type distribution
etypes = Counter(e[4] or "(none)" for e in ee)

# entity-entity subgraph (only entities that have an entity-entity edge)
G_conn = nx.Graph()
for a_id, a_lbl, b_id, b_lbl, et, ev in ee:
    G_conn.add_node(a_id)
    G_conn.add_node(b_id)
    G_conn.add_edge(a_id, b_id)
conn_nodes = G_conn.number_of_nodes()
conn_comps = nx.number_connected_components(G_conn) if conn_nodes else 0
largest = max((len(c) for c in nx.connected_components(G_conn)), default=0)

# whole-entity-set graph (all entities as nodes; isolates included) -> 466-style
all_ids = [r[0] for r in rows("MATCH (e:Entity) RETURN e.id")]
G_all = nx.Graph()
G_all.add_nodes_from(all_ids)
for a_id, a_lbl, b_id, b_lbl, et, ev in ee:
    G_all.add_edge(a_id, b_id)
all_comps = nx.number_connected_components(G_all) if G_all.number_of_nodes() else 0
isolates = sum(1 for n in G_all.nodes() if G_all.degree(n) == 0)

print("=" * 60)
print(f"  Total entities:            {n_ent}")
print(f"  Total documents:           {n_doc}")
print(f"  Entity-entity edges:       {n_edge}")
print("-" * 60)
print("  Entity-entity subgraph (connected entities only):")
print(f"    nodes (connected):       {conn_nodes}")
print(f"    components:              {conn_comps}")
print(f"    largest component:       {largest}")
print("-" * 60)
print("  Whole entity set (isolates counted, ~the '466' metric):")
print(f"    components:              {all_comps}")
print(f"    isolated entities:       {isolates}")
print("-" * 60)
mentions = etypes.get("mentions", 0)
print(f"  edge_type distribution ({n_edge} edges; mentions={mentions} = "
      f"{100*mentions/n_edge:.0f}%):" if n_edge else "  no edges")
for et, c in etypes.most_common():
    print(f"    {et:18s} {c:5d}  {100*c/n_edge:4.0f}%")
print("-" * 60)
print("  Edge integrity sample (evidence should support the type):")
import textwrap
for a_id, a_lbl, b_id, b_lbl, et, ev in ee[:: max(1, len(ee) // 10)][:10]:
    ev1 = (ev or "")[:90].replace("\n", " ")
    print(f"    [{et}] {a_lbl} -> {b_lbl}")
    print(f"         ev: {ev1}")
print("=" * 60)
del conn, db
