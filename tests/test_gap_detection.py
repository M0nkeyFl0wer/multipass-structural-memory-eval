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

from sme.categories.gap_detection import score_gap_detection

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
