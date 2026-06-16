"""Cat 5 — Burt structural-hole brokerage (TopologyAnalyzer.brokerage).

Distinct from bridges (global cut edges) and topological holes (H1
cycles). Tests that the single broker spanning two otherwise-disjoint
communities is identified, scored with low constraint, and reported as
concentrated brokerage.
"""

import networkx as nx

from sme.adapters.base import Edge, Entity
from sme.topology import TopologyAnalyzer
from sme.topology.analyzer import _gini


def _two_clusters_one_broker():
    """Two 3-cliques joined only through broker ``X``.

        a1-a2-a3 (clique)            b1-b2-b3 (clique)
                  \\                  /
                   X  (the only span)

    X has a structural hole between the two clusters: low constraint,
    high effective size, the sole cross-community broker.
    """
    entities = [Entity(id=n, name=n, entity_type="concept")
                for n in ("a1", "a2", "a3", "b1", "b2", "b3")]
    entities.append(Entity(id="X", name="broker", entity_type="concept"))
    edges = [
        Edge("a1", "a2", "RELATED"), Edge("a2", "a3", "RELATED"),
        Edge("a1", "a3", "RELATED"),
        Edge("b1", "b2", "RELATED"), Edge("b2", "b3", "RELATED"),
        Edge("b1", "b3", "RELATED"),
        Edge("X", "a1", "RELATED"), Edge("X", "b1", "RELATED"),
    ]
    return entities, edges


def test_broker_ranks_first_by_constraint():
    """X spans the structural hole between the two cliques, so it has the
    lowest Burt constraint and ranks first. (Both rim nodes around the
    hole are flagged as cross-community — that's the honest topology — but
    the principled signal puts the true broker on top.)"""
    entities, edges = _two_clusters_one_broker()
    report = TopologyAnalyzer(entities, edges).brokerage(seed=1)

    assert not report.skipped
    assert report.n_communities >= 2
    assert report.n_cross_community_brokers >= 1
    top = report.top_brokers[0]
    assert top.node == "X"
    assert len(top.spans_communities) >= 2
    # The broker has the minimum constraint among all scored nodes.
    assert top.constraint == min(b.constraint for b in report.top_brokers)


def test_adding_parallel_broker_lowers_concentration():
    """A second, independent span between the clusters spreads the
    brokerage mass — concentration must drop relative to the single span."""
    entities, edges = _two_clusters_one_broker()
    conc_single = TopologyAnalyzer(entities, edges).brokerage(seed=1).concentration

    entities = entities + [Entity(id="Y", name="broker2", entity_type="concept")]
    edges = edges + [Edge("Y", "a2", "RELATED"), Edge("Y", "b2", "RELATED")]
    conc_double = TopologyAnalyzer(entities, edges).brokerage(seed=1).concentration

    assert conc_double < conc_single


def test_broker_carries_human_readable_community_labels():
    """spans_labels should name *what* a broker bridges, by dominant
    entity_type, not bare Louvain integer indices."""
    entities = [
        Entity(id="i1", name="LadybugDB", entity_type="infrastructure"),
        Entity(id="i2", name="vault-rag", entity_type="infrastructure"),
        Entity(id="i3", name="Postgres", entity_type="infrastructure"),
        Entity(id="c1", name="Campaign-A", entity_type="campaign"),
        Entity(id="c2", name="Campaign-B", entity_type="campaign"),
        Entity(id="c3", name="Campaign-C", entity_type="campaign"),
        Entity(id="X", name="token-identity", entity_type="concept"),
    ]
    edges = [
        Edge("i1", "i2", "R"), Edge("i2", "i3", "R"), Edge("i1", "i3", "R"),
        Edge("c1", "c2", "R"), Edge("c2", "c3", "R"), Edge("c1", "c3", "R"),
        Edge("X", "i1", "R"), Edge("X", "c1", "R"),
    ]
    top = TopologyAnalyzer(entities, edges).brokerage(seed=1).top_brokers[0]
    assert top.node == "X"
    assert len(top.spans_labels) == len(top.spans_communities) >= 2
    blob = " ".join(top.spans_labels)
    assert "infrastructure" in blob and "campaign" in blob


def test_single_community_has_no_cross_community_brokers():
    """A lone clique is one community — there is no cross-community
    brokerage, and top_brokers must be empty (not interior fallback)."""
    ents = [Entity(id=n, name=n, entity_type="concept") for n in "abcd"]
    edges = [
        Edge("a", "b", "R"), Edge("b", "c", "R"), Edge("c", "d", "R"),
        Edge("a", "c", "R"), Edge("b", "d", "R"), Edge("a", "d", "R"),
    ]
    rep = TopologyAnalyzer(ents, edges).brokerage(seed=1)
    assert rep.n_cross_community_brokers == 0
    assert rep.top_brokers == []
    assert rep.concentration == 0.0


def test_empty_and_edgeless_graphs_are_safe():
    assert TopologyAnalyzer([], []).brokerage().n_nodes_scored == 0
    ents = [Entity(id="a", name="a", entity_type="concept")]
    rep = TopologyAnalyzer(ents, []).brokerage()
    assert rep.n_cross_community_brokers == 0
    assert rep.concentration == 0.0


def test_max_nodes_guard_skips_with_reason():
    entities, edges = _two_clusters_one_broker()
    rep = TopologyAnalyzer(entities, edges).brokerage(max_nodes=3)
    assert rep.skipped
    assert "max_nodes" in rep.skip_reason


def test_frontier_scoping_is_exact():
    """Frontier-scoping (#5) restricts nx.constraint to candidate brokers
    for speed. Because constraint depends only on a node's ego network, the
    value for a scored broker must equal the full-graph computation."""
    entities, edges = _two_clusters_one_broker()
    rep = TopologyAnalyzer(entities, edges).brokerage(seed=1)

    # Full constraint over the undirected simple projection.
    H = nx.Graph()
    for e in edges:
        H.add_edge(e.source_id, e.target_id)
    full = nx.constraint(H)

    assert rep.component_nodes == H.number_of_nodes()
    for b in rep.top_brokers:
        assert b.constraint == full[b.node]


def test_gini_helper():
    assert _gini([]) == 0.0
    assert _gini([0.0, 0.0]) == 0.0
    assert _gini([5.0, 5.0, 5.0]) == 0.0          # perfectly even
    assert _gini([0.0, 0.0, 10.0]) > 0.6          # concentrated
