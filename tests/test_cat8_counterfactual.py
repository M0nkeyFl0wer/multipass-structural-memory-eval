"""Tests for the Cat 8 counterfactual re-projection harness.

Mirrors the style of ``tests/test_cat8_external_fit.py``: a small hand-built
graph plus an alignment-derived mapping, asserting the harness's correctness
and its intellectual-honesty properties (no fabricated topology deltas).
"""

from __future__ import annotations

import math

import pytest

from sme.adapters.base import Edge, Entity
from sme.categories.counterfactual import (
    counterfactual_report,
    edge_type_mapping_from_alignments,
    reproject_edges,
)


# ---------------------------------------------------------------------------
# Fixtures: a small, fully-connected-enough hand graph
# ---------------------------------------------------------------------------

def _entities():
    return [
        Entity(id="e1", name="Alice", entity_type="person"),
        Entity(id="e2", name="Bob", entity_type="person"),
        Entity(id="e3", name="Acme", entity_type="org"),
        Entity(id="e4", name="Paper X", entity_type="document"),
        Entity(id="e5", name="Topic Y", entity_type="concept"),
    ]


def _edges():
    # edge types: authored (x2), works_at, mentions, cites
    return [
        Edge(source_id="e1", target_id="e4", edge_type="authored"),
        Edge(source_id="e2", target_id="e4", edge_type="authored"),
        Edge(source_id="e1", target_id="e3", edge_type="works_at"),
        Edge(source_id="e4", target_id="e5", edge_type="mentions"),
        Edge(source_id="e4", target_id="e4", edge_type="cites"),  # self-loop ok
    ]


def _pure_rename_alignments():
    """1:1 rename: each corpus edge type -> a distinct standard term.

    Note ``cites`` is intentionally NOT in the alignments -> stays unmapped.
    """
    return [
        {
            "corpus_term": "authored",
            "corpus_kind": "edge_type",
            "standard_term": "schema:author",
            "confidence": 0.95,
            "outcome": "matched",
        },
        {
            "corpus_term": "works_at",
            "corpus_kind": "edge_type",
            "standard_term": "schema:worksFor",
            "confidence": 0.9,
            "outcome": "matched",
        },
        {
            "corpus_term": "mentions",
            "corpus_kind": "edge_type",
            "standard_term": "schema:mentions",
            "confidence": 0.8,
            "outcome": "matched",
        },
        # An entity-kind alignment that must be ignored by the edge-type filter:
        {
            "corpus_term": "person",
            "corpus_kind": "entity_type",
            "standard_term": "schema:Person",
            "confidence": 0.99,
            "outcome": "matched",
        },
    ]


# ---------------------------------------------------------------------------
# reproject_edges
# ---------------------------------------------------------------------------

def test_reproject_does_not_mutate_inputs():
    edges = _edges()
    original_types = [e.edge_type for e in edges]
    original_ids = [id(e) for e in edges]

    mapping = {"authored": "schema:author"}
    out = reproject_edges(edges, mapping)

    # Inputs untouched.
    assert [e.edge_type for e in edges] == original_types
    assert [id(e) for e in edges] == original_ids
    # Output is a fresh list of fresh objects.
    assert all(id(o) not in original_ids for o in out)


def test_reproject_renames_mapped_and_keeps_unmapped():
    edges = _edges()
    mapping = {"authored": "schema:author", "works_at": "schema:worksFor"}
    out = reproject_edges(edges, mapping)

    out_types = [e.edge_type for e in out]
    assert out_types == [
        "schema:author",
        "schema:author",
        "schema:worksFor",
        "mentions",  # unmapped -> unchanged
        "cites",  # unmapped -> unchanged
    ]
    # Endpoints preserved exactly.
    assert [(e.source_id, e.target_id) for e in out] == [
        (e.source_id, e.target_id) for e in edges
    ]


def test_reproject_property_copy_is_isolated():
    e = Edge(source_id="a", target_id="b", edge_type="x", properties={"w": 1})
    out = reproject_edges([e], {"x": "y"})
    out[0].properties["w"] = 999
    assert e.properties["w"] == 1  # source untouched


# ---------------------------------------------------------------------------
# mapping extraction
# ---------------------------------------------------------------------------

def test_mapping_filters_to_edge_types_only():
    mapping, ambiguous = edge_type_mapping_from_alignments(_pure_rename_alignments())
    assert mapping == {
        "authored": "schema:author",
        "works_at": "schema:worksFor",
        "mentions": "schema:mentions",
    }
    assert "person" not in mapping  # entity_type alignment filtered out
    assert ambiguous == []


def test_mapping_records_ambiguous_terms_deterministically():
    alignments = [
        {
            "corpus_term": "rel",
            "corpus_kind": "edge_type",
            "standard_term": "B",
            "confidence": 0.5,
        },
        {
            "corpus_term": "rel",
            "corpus_kind": "edge_type",
            "standard_term": "A",
            "confidence": 0.9,  # higher confidence wins
        },
    ]
    mapping, ambiguous = edge_type_mapping_from_alignments(alignments)
    assert ambiguous == ["rel"]
    assert mapping["rel"] == "A"  # highest confidence deterministic pick


# ---------------------------------------------------------------------------
# report: counts
# ---------------------------------------------------------------------------

def test_report_counts_remapped_and_unmapped():
    entities, edges = _entities(), _edges()
    report = counterfactual_report(
        entities, edges, _pure_rename_alignments(), reference_set="schema.org"
    )
    assert report["n_edges"] == 5
    # authored x2 + works_at + mentions = 4 remapped; cites = 1 unmapped.
    assert report["n_remapped"] == 4
    assert report["n_unmapped"] == 1
    assert report["reference_set"] == "schema.org"
    assert report["full_graph"] is True
    assert "caveat" not in report


# ---------------------------------------------------------------------------
# report: vocabulary-level deltas
# ---------------------------------------------------------------------------

def test_report_computes_entropy_and_distinct_count():
    entities, edges = _entities(), _edges()
    report = counterfactual_report(entities, edges, _pure_rename_alignments())

    before, after, deltas = report["before"], report["after"], report["deltas"]

    # Distinct edge types: before {authored, works_at, mentions, cites} = 4.
    assert before["n_distinct_edge_types"] == 4
    # Pure 1:1 rename onto distinct, non-colliding standard labels -> still 4.
    assert after["n_distinct_edge_types"] == 4
    assert deltas["n_distinct_edge_types"] == 0

    # Entropy must be a real, computed number.
    assert isinstance(before["edge_type_entropy"], float)
    assert before["edge_type_entropy"] > 0
    # Pure rename preserves the label-multiset partition -> entropy unchanged.
    assert math.isclose(deltas["edge_type_entropy"], 0.0, abs_tol=1e-12)


def test_merge_moves_vocabulary_deltas():
    """Collapsing two corpus types onto one standard term IS a merge: it must
    drop distinct-count and lower entropy (more concentrated distribution)."""
    entities, edges = _entities(), _edges()
    merge_alignments = [
        # authored AND works_at both collapse to one standard relation.
        {"corpus_term": "authored", "corpus_kind": "edge_type",
         "standard_term": "schema:relatedTo", "confidence": 0.9},
        {"corpus_term": "works_at", "corpus_kind": "edge_type",
         "standard_term": "schema:relatedTo", "confidence": 0.9},
    ]
    report = counterfactual_report(entities, edges, merge_alignments)

    assert report["n_merged_groups"] == 1
    assert report["merged_groups"] == {"schema:relatedTo": ["authored", "works_at"]}
    # 4 distinct -> 3 distinct (authored+works_at fused).
    assert report["deltas"]["n_distinct_edge_types"] == -1
    # Fewer, more concentrated types -> entropy drops.
    assert report["deltas"]["edge_type_entropy"] < 0


# ---------------------------------------------------------------------------
# honesty: topology cannot move under a pure rename
# ---------------------------------------------------------------------------

def test_component_count_delta_is_zero_under_pure_rename():
    entities, edges = _entities(), _edges()
    report = counterfactual_report(entities, edges, _pure_rename_alignments())
    assert report["deltas"]["n_components"] == 0
    assert report["deltas"]["largest_component_size"] == 0


def test_component_count_delta_is_zero_under_merge_too():
    """Even a merge must not move relation-agnostic connectivity."""
    entities, edges = _entities(), _edges()
    merge_alignments = [
        {"corpus_term": "authored", "corpus_kind": "edge_type",
         "standard_term": "rel", "confidence": 0.9},
        {"corpus_term": "works_at", "corpus_kind": "edge_type",
         "standard_term": "rel", "confidence": 0.9},
    ]
    report = counterfactual_report(entities, edges, merge_alignments)
    assert report["deltas"]["n_components"] == 0
    assert report["deltas"]["largest_component_size"] == 0


# ---------------------------------------------------------------------------
# #45 precondition
# ---------------------------------------------------------------------------

def test_full_graph_false_adds_caveat():
    entities, edges = _entities(), _edges()
    report = counterfactual_report(
        entities, edges, _pure_rename_alignments(), full_graph=False
    )
    assert report["full_graph"] is False
    assert "caveat" in report
    assert "sampling bias" in report["caveat"].lower()


def test_full_graph_true_has_no_caveat():
    entities, edges = _entities(), _edges()
    report = counterfactual_report(
        entities, edges, _pure_rename_alignments(), full_graph=True
    )
    assert "caveat" not in report


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
