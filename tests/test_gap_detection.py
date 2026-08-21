"""Correctness tests for Cat 5 (The Missing Room).

Every assertion traces back to a field in the fixture's
``ground_truth`` dict — when a test fails, the reading the scorer
produced for that field is suspect, not the fixture.

Ripser is an optional dependency (``[topology]`` extra). Tests that
need it are marked so pytest skips them cleanly when it isn't
installed; the structural-signal tests (components, bridges,
isolates, candidate gaps) run either way.
"""

from __future__ import annotations

import pytest

from sme.adapters.base import Edge, Entity
from sme.categories.gap_detection import format_report, score_gap_detection

ripser = pytest.importorskip  # alias for readability below


# --- Structural signals (no ripser required) --------------------------


def test_component_count(gap_graph):
    entities, edges, truth = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.components == truth["components"]


def test_largest_component_size(gap_graph):
    entities, edges, truth = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.largest_component_size == truth["largest_component_size"]


def test_isolated_node_count(gap_graph):
    entities, edges, truth = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.isolated_nodes == truth["isolated_nodes"]


def test_structural_bridges(gap_graph):
    entities, edges, truth = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    found = {frozenset(b) for b in report.bridges}
    assert found == truth["bridges"]


def test_nodes_and_edges_match_snapshot(gap_graph):
    entities, edges, truth = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.nodes == truth["nodes"]
    assert report.edges == truth["edges"]


# --- Candidate gaps (heuristic, no ripser required) -------------------


def test_candidate_gap_between_topic_clusters(gap_graph):
    """cluster_a and cluster_b both hold entity_type='topic' nodes
    and are disconnected — the scorer should flag them."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)

    # At least one candidate whose shared_entity_types includes 'topic'.
    matching = [
        gap for gap in report.candidate_gaps if "topic" in gap.shared_entity_types
    ]
    assert matching, "expected a candidate gap on shared entity_type 'topic'"


def test_seeded_gap_recall_is_one(gap_graph):
    entities, edges, truth = gap_graph
    report = score_gap_detection(
        entities,
        edges,
        seeded_missing_edges=truth["seeded_missing_edges"],
        run_homology=False,
    )
    assert report.gap_recall == pytest.approx(1.0)
    # With min_component_size=3 the isolate is filtered out before
    # pairing, so the only considered pair is (cluster_a, cluster_b)
    # — precision is exactly 1.0.
    assert report.gap_precision == pytest.approx(1.0)


def test_candidate_gap_has_score_and_examples(gap_graph):
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.candidate_gaps, "expected at least one candidate gap"
    gap = report.candidate_gaps[0]
    assert gap.score > 0.0
    assert len(gap.example_ids_a) == 3
    assert len(gap.example_ids_b) == 3


def test_candidate_gap_min_size_filters_isolates(gap_graph):
    """With min_component_size=3 the isolate (L, size=1) should not
    participate in any candidate gap. Considered pairs drop to 1."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(
        entities, edges, run_homology=False, min_component_size=3
    )
    assert report.candidate_gaps_considered == 1
    assert len(report.candidate_gaps) == 1
    assert report.components == 3  # the isolate is still counted, just not paired


def test_top_k_caps_output(gap_graph):
    entities, edges, _ = gap_graph
    report = score_gap_detection(
        entities, edges, run_homology=False, top_k=0
    )
    assert report.candidate_gaps == []
    assert report.candidate_gaps_considered >= 1


# --- Persistent homology (requires ripser) ----------------------------


def test_betti_1_on_largest_component(gap_graph):
    """The 5-cycle in cluster_a survives filtration until the skip-one
    distances close it at filtration level 2, giving one persistent H_1
    bar. Triangles would fill in at filtration 1 and contribute nothing."""
    ripser("ripser", reason="Ripser not installed; skipping persistent homology check")

    entities, edges, truth = gap_graph
    report = score_gap_detection(entities, edges)

    assert not report.h1_skipped, report.h1_skip_reason
    assert report.betti_0_largest == 1  # largest component is connected
    assert report.betti_1_largest == truth["betti_1_largest"]
    assert report.h1_max_persistence > 0.0


def test_homology_gracefully_skipped_when_disabled(gap_graph):
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.betti_1_largest == 0
    assert report.h1_max_persistence == 0.0
    assert report.h1_skipped is False  # we opted out, not "skipped by policy"


# --- H1 null model / significance (requires ripser) -------------------


def test_null_model_off_by_default(gap_graph):
    """A Betti-1 reading ships 'observed but not validated' until the
    caller opts into the null model. No p-value, no significance verdict."""
    ripser("ripser", reason="Ripser not installed")
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges)  # null_samples defaults to 0
    assert report.betti_1_largest == 1
    assert report.h1_null_samples == 0
    assert report.h1_null_p_value is None
    assert report.h1_significant is None


def test_null_model_runs_and_is_deterministic(gap_graph):
    """With null_samples>0 the scorer reports a Monte-Carlo p-value, and a
    fixed seed makes it reproducible (a benchmark number must re-run equal)."""
    ripser("ripser", reason="Ripser not installed")
    entities, edges, _ = gap_graph

    r1 = score_gap_detection(entities, edges, null_samples=25)
    r2 = score_gap_detection(entities, edges, null_samples=25)

    assert r1.h1_null_samples == 25
    assert r1.h1_null_p_value is not None
    assert 0.0 < r1.h1_null_p_value <= 1.0
    assert r1.h1_significant is not None
    # Deterministic under the fixed default seed.
    assert r1.h1_null_p_value == r2.h1_null_p_value


def test_lone_cycle_in_near_regular_graph_is_not_significant(gap_graph):
    """The fixture's largest component is a near-2-regular 6-node graph; a
    graph with that degree sequence is almost obliged to contain a cycle,
    so the 5-cycle should NOT beat a degree-matched null. This is the whole
    point of the null model — it stops a structurally-inevitable loop from
    being reported as a 'real gap'."""
    ripser("ripser", reason="Ripser not installed")
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, null_samples=99)
    assert report.betti_1_largest == 1
    # Not distinguishable from chance for a graph of this size/degree.
    assert report.h1_significant is False


def test_tree_has_zero_persistence_and_is_not_significant():
    """A path (tree) has no H1 loop: observed persistence 0, so the
    Monte-Carlo tail p-value is exactly 1.0 and the reading is not
    significant. Guards the 'no loop → no false gap' end of the scale."""
    ripser("ripser", reason="Ripser not installed")
    entities = [Entity(id=c, name=c, entity_type="topic") for c in "ABCD"]
    edges = [Edge("A", "B", "RELATED"), Edge("B", "C", "RELATED"), Edge("C", "D", "RELATED")]
    report = score_gap_detection(entities, edges, null_samples=25)
    assert report.betti_1_largest == 0
    assert report.h1_max_persistence == 0.0
    assert report.h1_null_p_value == pytest.approx(1.0)
    assert report.h1_significant is False

# --- flat_rarity_mode flagging ----------------------------------------


def test_flat_rarity_mode_flagged_when_two_sized_components(gap_graph):
    """The synthetic_gap_graph fixture has exactly two sized clusters
    once the isolate is filtered out. The rarity-weighting fallback
    fires (every shared type weighted 1.0), and the report should
    flag it so JSON consumers can see why scores are inflated."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.flat_rarity_mode is True


def test_flat_rarity_mode_off_for_no_candidate_pairs():
    """When there aren't enough sized components to form a pair,
    flat_rarity_mode stays False — there's nothing to fall back on."""
    report = score_gap_detection([], [], run_homology=False)
    assert report.flat_rarity_mode is False


def test_flat_rarity_mode_text_in_format_report(gap_graph):
    """format_report must surface the flag so a maintainer reading the
    rendered card sees the warning, not just the JSON consumer."""
    from sme.categories.gap_detection import format_report

    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    rendered = format_report(report)
    assert "flat-rarity mode" in rendered


# --- Empty-graph guardrail -------------------------------------------


def test_empty_graph_is_all_zeros():
    report = score_gap_detection([], [], run_homology=False)
    assert report.nodes == 0
    assert report.edges == 0
    assert report.components == 0
    assert report.largest_component_size == 0
    assert report.isolated_nodes == 0
    assert report.bridges == []
    assert report.candidate_gaps == []
    assert report.flat_rarity_mode is False


# --- Isolated-by-type (#14) -------------------------------------------


def test_isolated_by_type(gap_graph):
    """Issue #14 — isolates broken out by entity_type."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.isolated_by_type == {"tag": 1}


def test_format_report_shows_isolate_types(gap_graph):
    """Issue #14 — format_report includes type breakdown for isolates."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    rendered = format_report(report)
    assert "tag: 1" in rendered


# --- Representative cycles (#16) -------------------------------------


def test_representative_cycles(gap_graph):
    """Issue #16 — representative cycles from largest component."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert len(report.representative_cycles) >= 1
    cycle_nodes = [set(c) for c in report.representative_cycles]
    five_cycle_nodes = {"A", "B", "C", "D", "E"}
    assert any(five_cycle_nodes <= nodes for nodes in cycle_nodes)


def test_format_report_shows_cycles(gap_graph):
    """Issue #16 — format_report includes cycle descriptions."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    rendered = format_report(report)
    assert "Representative cycles" in rendered
    assert "-cycle]" in rendered


# --- Component-size distribution (#17) --------------------------------


def test_component_size_distribution(gap_graph):
    """Issue #17 — component-size distribution buckets."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert report.component_size_distribution["1"] == 1
    assert report.component_size_distribution["2-5"] == 1
    assert report.component_size_distribution["6-20"] == 1
    assert report.component_size_distribution[">20"] == 0


def test_non_trivial_components(gap_graph):
    """Issue #17 — non-trivial components with type distributions."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    assert len(report.non_trivial_components) == 2
    assert report.non_trivial_components[0]["size"] == 6
    assert report.non_trivial_components[1]["size"] == 5
    assert report.non_trivial_components[0]["types"]["topic"] == 5
    assert report.non_trivial_components[0]["types"]["note"] == 1


def test_format_report_shows_distribution(gap_graph):
    """Issue #17 — format_report includes distribution and type breakdown."""
    entities, edges, _ = gap_graph
    report = score_gap_detection(entities, edges, run_homology=False)
    rendered = format_report(report)
    assert "Component-size distribution" in rendered
    assert "Non-trivial components" in rendered
    assert "[6 nodes]" in rendered
