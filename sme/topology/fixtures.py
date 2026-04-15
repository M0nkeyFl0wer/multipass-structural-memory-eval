"""Ground-truth synthetic graphs for Cat 5 (The Missing Room) and
other topology-layer tests.

Adapter-agnostic: fixtures return ``(entities, edges, ground_truth)``
tuples using the core ``Entity``/``Edge`` dataclasses, so they can be
fed to any scorer that accepts a graph snapshot.

The ground-truth dict states what the graph *is*, so scorer output
can be compared against a known answer rather than asserted about
itself.
"""

from __future__ import annotations

from sme.adapters.base import Edge, Entity


def synthetic_gap_graph() -> tuple[list[Entity], list[Edge], dict]:
    """Known-topology graph with a seeded structural gap.

    Layout::

        cluster_a (6 nodes, 6 edges):
          5-cycle  A → B → C → D → E → A
          leaf     A → F

        cluster_b (5 nodes, 5 edges):
          4-cycle  G → H → I → J → G
          leaf     G → K

        isolate:  L (no edges)

        seeded gap: no edge between E and G. They share entity_type
          "topic" and represent neighbouring subjects that a fully-
          enriched graph would connect. A Cat 5 scorer should flag
          the (cluster_a, cluster_b) disconnect as a candidate gap.

    Ground-truth readings:
      - 12 nodes, 11 edges, 3 weakly-connected components
      - largest component = cluster_a (6 nodes)
      - 1 isolated node (L)
      - 2 structural bridges on the undirected projection:
          (A, F) and (G, K) — removing either isolates a leaf
      - Betti_1 on the largest component = 1  (the 5-cycle;
          triangles would fill in at filtration 1 on hop-distance)
      - Seeded missing edge: (E, G)
    """
    entities = [
        # cluster_a
        Entity(id="A", name="topic-a", entity_type="topic"),
        Entity(id="B", name="topic-b", entity_type="topic"),
        Entity(id="C", name="topic-c", entity_type="topic"),
        Entity(id="D", name="topic-d", entity_type="topic"),
        Entity(id="E", name="topic-e", entity_type="topic"),
        Entity(id="F", name="note-f",  entity_type="note"),
        # cluster_b
        Entity(id="G", name="topic-g", entity_type="topic"),
        Entity(id="H", name="topic-h", entity_type="topic"),
        Entity(id="I", name="topic-i", entity_type="topic"),
        Entity(id="J", name="topic-j", entity_type="topic"),
        Entity(id="K", name="note-k",  entity_type="note"),
        # isolate
        Entity(id="L", name="orphan-tag", entity_type="tag"),
    ]

    edges = [
        # cluster_a: 5-cycle + leaf
        Edge("A", "B", "RELATED"),
        Edge("B", "C", "RELATED"),
        Edge("C", "D", "RELATED"),
        Edge("D", "E", "RELATED"),
        Edge("E", "A", "RELATED"),
        Edge("A", "F", "MENTIONS"),
        # cluster_b: 4-cycle + leaf
        Edge("G", "H", "RELATED"),
        Edge("H", "I", "RELATED"),
        Edge("I", "J", "RELATED"),
        Edge("J", "G", "RELATED"),
        Edge("G", "K", "MENTIONS"),
    ]

    ground_truth = {
        "nodes": 12,
        "edges": 11,
        "components": 3,
        "largest_component_size": 6,
        "largest_component_nodes": {"A", "B", "C", "D", "E", "F"},
        "isolated_nodes": 1,
        "isolated_ids": {"L"},
        # Bridges reported as frozensets so direction doesn't matter.
        "bridges": {frozenset({"A", "F"}), frozenset({"G", "K"})},
        "betti_1_largest": 1,
        "seeded_missing_edges": [("E", "G")],
    }

    return entities, edges, ground_truth
