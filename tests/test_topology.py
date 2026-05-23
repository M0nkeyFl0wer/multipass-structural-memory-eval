"""Tests for TopologyAnalyzer (issue #18).

Exercises structural_health, community_structure, edge_type_components,
and filtered_subgraph with synthetic graphs — no adapter or file I/O.
Betti numbers are not tested here (requires ripser).
"""

from __future__ import annotations

import pytest

from sme.adapters.base import Edge, Entity
from sme.topology import TopologyAnalyzer


def _e(eid: str, etype: str = "thing") -> Entity:
    return Entity(id=eid, name=eid, entity_type=etype)


def _edge(src: str, tgt: str, etype: str = "related") -> Edge:
    return Edge(source_id=src, target_id=tgt, edge_type=etype)


class TestStructuralHealth:
    def test_empty_graph(self):
        topo = TopologyAnalyzer([], [])
        h = topo.structural_health()
        assert h["nodes"] == 0
        assert h["edges"] == 0
        assert h["components"] == 0

    def test_single_node(self):
        topo = TopologyAnalyzer([_e("a")], [])
        h = topo.structural_health()
        assert h["nodes"] == 1
        assert h["isolated_nodes"] == 1
        assert h["components"] == 1

    def test_triangle(self):
        ents = [_e("a"), _e("b"), _e("c")]
        edges = [_edge("a", "b"), _edge("b", "c"), _edge("c", "a")]
        topo = TopologyAnalyzer(ents, edges)
        h = topo.structural_health()
        assert h["nodes"] == 3
        assert h["edges"] == 3
        assert h["components"] == 1
        assert h["isolated_nodes"] == 0
        assert h["largest_component_size"] == 3
        assert h["largest_component_ratio"] == pytest.approx(1.0)

    def test_two_components(self):
        ents = [_e("a"), _e("b"), _e("c"), _e("d")]
        edges = [_edge("a", "b"), _edge("c", "d")]
        topo = TopologyAnalyzer(ents, edges)
        h = topo.structural_health()
        assert h["components"] == 2
        assert h["largest_component_size"] == 2

    def test_entity_type_distribution(self):
        ents = [_e("a", "person"), _e("b", "person"), _e("c", "place")]
        topo = TopologyAnalyzer(ents, [])
        h = topo.structural_health()
        assert h["entity_type_distribution"]["person"] == 2
        assert h["entity_type_distribution"]["place"] == 1

    def test_edge_type_entropy_single_type(self):
        ents = [_e("a"), _e("b")]
        edges = [_edge("a", "b", "related")]
        topo = TopologyAnalyzer(ents, edges)
        h = topo.structural_health()
        assert h["edge_type_entropy_bits"] == 0.0

    def test_edge_type_entropy_two_equal_types(self):
        ents = [_e("a"), _e("b"), _e("c")]
        edges = [_edge("a", "b", "knows"), _edge("b", "c", "owns")]
        topo = TopologyAnalyzer(ents, edges)
        h = topo.structural_health()
        assert h["edge_type_entropy_bits"] == pytest.approx(1.0)

    def test_dangling_edge_ignored(self):
        ents = [_e("a")]
        edges = [_edge("a", "nonexistent", "broken")]
        topo = TopologyAnalyzer(ents, edges)
        h = topo.structural_health()
        assert h["edges"] == 0


class TestCommunityStructure:
    def test_empty_graph(self):
        topo = TopologyAnalyzer([], [])
        c = topo.community_structure()
        assert c.count == 0
        assert c.modularity == 0.0

    def test_two_cliques(self):
        ents = [_e(f"a{i}") for i in range(4)] + [_e(f"b{i}") for i in range(4)]
        edges = []
        for i in range(4):
            for j in range(i + 1, 4):
                edges.append(_edge(f"a{i}", f"a{j}"))
                edges.append(_edge(f"b{i}", f"b{j}"))
        edges.append(_edge("a0", "b0"))
        topo = TopologyAnalyzer(ents, edges)
        c = topo.community_structure()
        assert c.count >= 2
        assert c.modularity > 0

    def test_unsupported_method_raises(self):
        topo = TopologyAnalyzer([_e("a")], [])
        with pytest.raises(NotImplementedError):
            topo.community_structure(method="spectral")


class TestFilteredSubgraph:
    def test_include_filter(self):
        ents = [_e("a"), _e("b"), _e("c")]
        edges = [_edge("a", "b", "knows"), _edge("b", "c", "owns")]
        topo = TopologyAnalyzer(ents, edges)
        sub = topo.filtered_subgraph(["knows"])
        assert sub.G.number_of_edges() == 1

    def test_exclude_filter(self):
        ents = [_e("a"), _e("b"), _e("c")]
        edges = [_edge("a", "b", "knows"), _edge("b", "c", "owns")]
        topo = TopologyAnalyzer(ents, edges)
        sub = topo.filtered_subgraph(["knows"], include=False)
        assert sub.G.number_of_edges() == 1

    def test_preserves_all_nodes(self):
        ents = [_e("a"), _e("b"), _e("c")]
        edges = [_edge("a", "b", "knows")]
        topo = TopologyAnalyzer(ents, edges)
        sub = topo.filtered_subgraph(["knows"])
        assert sub.G.number_of_nodes() == 3


class TestEdgeTypeComponents:
    def test_single_type(self):
        ents = [_e("a"), _e("b"), _e("c"), _e("d")]
        edges = [_edge("a", "b", "knows"), _edge("c", "d", "knows")]
        topo = TopologyAnalyzer(ents, edges)
        etc = topo.edge_type_components()
        assert etc["knows"] == 2

    def test_two_types_different_components(self):
        ents = [_e("a"), _e("b"), _e("c"), _e("d")]
        edges = [_edge("a", "b", "knows"), _edge("c", "d", "owns")]
        topo = TopologyAnalyzer(ents, edges)
        etc = topo.edge_type_components()
        # "knows" subgraph: a-b connected, c and d isolated → 3 components
        assert etc["knows"] == 3
        # "owns" subgraph: c-d connected, a and b isolated → 3 components
        assert etc["owns"] == 3
