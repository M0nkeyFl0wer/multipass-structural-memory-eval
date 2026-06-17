"""Tests for sme.categories.ontology_coherence (Cat 8).

Covers all five sub-tests plus the claim library and hall usage:

- 8a Type coverage (incl. prefix matching for ``drawer:hall_X``)
- 8b Edge vocabulary (incl. case-insensitive fallback)
- 8c Schema-data alignment (top-type concentration warning, entropy
  passthrough from structural_health)
- 8d Drift score and hall_usage scorer for MemPalace-shaped graphs
- 8e Claim verification: library pattern matching, untestable denylist,
  inline operational_override, cross-category deferral (Cat 7/3/2b),
  temporal/provenance coverage metrics
- ``Cat8Report.to_dict()`` shape contract
- ``ImpliedOntology.load()`` round-trip via a YAML fixture
"""
from __future__ import annotations

import textwrap

import pytest

from sme.adapters.base import Edge, Entity
from sme.categories.ontology_coherence import (
    Cat8Report,
    ClaimResult,
    ImpliedOntology,
    _score_claim,
    _score_hall_usage,
    is_untestable,
    load_claim_library,
    match_claim_pattern,
    score_cat8,
)


# ── Helpers ────────────────────────────────────────────────────────


def _ent(eid: str, etype: str, **props) -> Entity:
    return Entity(id=eid, name=eid, entity_type=etype, properties=dict(props))


def _edge(s: str, t: str, etype: str, **props) -> Edge:
    return Edge(source_id=s, target_id=t, edge_type=etype, properties=dict(props))


@pytest.fixture
def empty_claim_library() -> dict:
    """A claim library with no claims and no untestable patterns."""
    return {"claims": [], "untestable_patterns": []}


# ── load_claim_library ─────────────────────────────────────────────


def test_load_claim_library_uses_repo_default():
    """The default path resolves relative to the package root and loads
    the shipped structural_claims.yaml."""
    lib = load_claim_library()
    assert "claims" in lib
    assert any("hierarchical" in c.get("pattern", "") for c in lib["claims"])
    assert "untestable_patterns" in lib


# ── Pattern matching helpers ───────────────────────────────────────


def test_match_claim_pattern_finds_hierarchical():
    lib = load_claim_library()
    entry = match_claim_pattern(
        "The graph is hierarchical with nested wings", lib
    )
    assert entry is not None
    assert entry["name"] == "Hierarchical structure"


def test_match_claim_pattern_returns_none_when_no_match(empty_claim_library):
    assert match_claim_pattern("anything", empty_claim_library) is None


def test_match_claim_pattern_case_insensitive():
    lib = load_claim_library()
    entry = match_claim_pattern("HIERARCHICAL", lib)
    assert entry is not None


def test_is_untestable_flags_ux_claims():
    lib = load_claim_library()
    assert is_untestable("It is intuitive and easy to use", lib)
    assert is_untestable("Highly scalable", lib)
    assert not is_untestable("Edges have provenance tracking", lib)


# ── ImpliedOntology.load() ────────────────────────────────────────


def test_implied_ontology_load_round_trip(tmp_path):
    p = tmp_path / "ont.yaml"
    p.write_text(
        textwrap.dedent(
            """
            version: v0.1
            source: declared
            entity_types: [drawer, wing, room]
            edge_types: [member_of, tunnel]
            hall_vocabulary: [code, decisions]
            structural_claims:
              - id: c1
                text: "The graph is hierarchical"
            vocabulary_claims:
              - id: v1
                text: "Hall vocabulary"
            retrieval_claims:
              - id: r1
                text: "Structure improves retrieval"
            """
        ).strip()
    )
    ont = ImpliedOntology.load(p)
    assert ont.version == "v0.1"
    assert ont.source == "declared"
    assert "drawer" in ont.entity_types
    assert "tunnel" in ont.edge_types
    assert ont.hall_vocabulary == ["code", "decisions"]
    assert ont.structural_claims[0]["id"] == "c1"
    assert ont.retrieval_claims[0]["text"] == "Structure improves retrieval"


def test_implied_ontology_load_missing_fields(tmp_path):
    """Missing optional keys default to empty lists, no crash."""
    p = tmp_path / "ont.yaml"
    p.write_text("version: v0.1\nsource: inferred\n")
    ont = ImpliedOntology.load(p)
    assert ont.entity_types == []
    assert ont.edge_types == []
    assert ont.structural_claims == []


# ── 8a Type coverage ──────────────────────────────────────────────


def test_8a_type_coverage_exact_match(empty_claim_library):
    ont = ImpliedOntology(
        version="t",
        source="declared",
        entity_types=["wing", "room"],
    )
    entities = [_ent("e1", "wing"), _ent("e2", "room")]
    report = score_cat8(
        ont, entities, [], {"edge_type_entropy_bits": 0.0},
        claim_library=empty_claim_library,
    )
    assert report.type_coverage == pytest.approx(1.0)
    assert sorted(report.types_found) == ["room", "wing"]
    assert report.types_missing == []


def test_8a_type_coverage_prefix_match(empty_claim_library):
    """A declared 'drawer' matches 'drawer:hall_code' via prefix rule."""
    ont = ImpliedOntology(
        version="t", source="declared", entity_types=["drawer"]
    )
    entities = [_ent("e1", "drawer:hall_code")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    assert "drawer" in report.types_found
    assert report.types_missing == []


def test_8a_undeclared_types_surfaced(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared", entity_types=["wing"]
    )
    entities = [_ent("e1", "wing"), _ent("e2", "drawer:hall_code")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    # 'drawer:hall_code' has prefix 'drawer' which isn't declared
    assert "drawer:hall_code" in report.types_undeclared


def test_8a_missing_declared_type(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared", entity_types=["wing", "ghost"]
    )
    entities = [_ent("e1", "wing")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    assert "ghost" in report.types_missing
    assert report.type_coverage == pytest.approx(0.5)


def test_8a_empty_declared_types_yields_perfect_coverage(empty_claim_library):
    """No declared types → vacuously 1.0 coverage."""
    ont = ImpliedOntology(version="t", source="inferred")
    entities = [_ent("e1", "x")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    assert report.type_coverage == pytest.approx(1.0)


# ── 8b Edge vocabulary ────────────────────────────────────────────


def test_8b_edge_vocabulary_exact_match(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing"],
        edge_types=["member_of", "tunnel"],
    )
    entities = [_ent("a", "wing"), _ent("b", "wing")]
    edges = [
        _edge("a", "b", "member_of"),
        _edge("a", "b", "tunnel"),
    ]
    report = score_cat8(
        ont, entities, edges, {}, claim_library=empty_claim_library,
    )
    assert report.edge_vocabulary_coverage == pytest.approx(1.0)


def test_8b_edge_case_insensitive_fallback(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing"],
        edge_types=["Member_Of"],
    )
    entities = [_ent("a", "wing"), _ent("b", "wing")]
    edges = [_edge("a", "b", "member_of")]
    report = score_cat8(
        ont, entities, edges, {}, claim_library=empty_claim_library,
    )
    # Different case but same word — falls back via case-insensitive match
    assert "Member_Of" in report.edges_found
    assert report.edge_vocabulary_coverage == pytest.approx(1.0)


def test_8b_missing_and_undeclared(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing"], edge_types=["member_of", "missing_edge"],
    )
    entities = [_ent("a", "wing"), _ent("b", "wing")]
    edges = [_edge("a", "b", "member_of"), _edge("a", "b", "tunnel")]
    report = score_cat8(
        ont, entities, edges, {}, claim_library=empty_claim_library,
    )
    assert "missing_edge" in report.edges_missing
    assert "tunnel" in report.edges_undeclared


def test_8b_empty_declared_yields_perfect_coverage(empty_claim_library):
    ont = ImpliedOntology(version="t", source="inferred", entity_types=["x"])
    entities = [_ent("a", "x")]
    edges = [_edge("a", "a", "self")]
    report = score_cat8(
        ont, entities, edges, {}, claim_library=empty_claim_library,
    )
    assert report.edge_vocabulary_coverage == pytest.approx(1.0)


# ── 8c Schema-data alignment ──────────────────────────────────────


def test_8c_concentration_warning_above_threshold(empty_claim_library):
    ont = ImpliedOntology(version="t", source="declared", entity_types=["x"])
    # 9 of type 'x', 1 of type 'y' → 90% > 80% triggers warning
    entities = [_ent(f"e{i}", "x") for i in range(9)] + [_ent("eY", "y")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    assert report.entity_type_concentration is not None
    assert report.entity_type_concentration["top_type"] == "x"
    assert report.entity_type_concentration["fraction"] == pytest.approx(0.9)
    assert report.concentration_warning is not None


def test_8c_no_warning_below_threshold(empty_claim_library):
    ont = ImpliedOntology(version="t", source="declared", entity_types=["x"])
    # 5 of 'x', 5 of 'y' → 50%, no warning
    entities = [_ent(f"e{i}", "x") for i in range(5)] + [
        _ent(f"y{i}", "y") for i in range(5)
    ]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    assert report.concentration_warning is None


def test_8c_entropy_bits_taken_from_structural_health(empty_claim_library):
    ont = ImpliedOntology(version="t", source="declared", entity_types=["x"])
    entities = [_ent("e1", "x")]
    report = score_cat8(
        ont, entities, [],
        {"edge_type_entropy_bits": 2.5},
        claim_library=empty_claim_library,
    )
    assert report.edge_type_entropy_bits == pytest.approx(2.5)


def test_8c_no_entities_no_concentration(empty_claim_library):
    ont = ImpliedOntology(version="t", source="declared")
    report = score_cat8(
        ont, [], [], {}, claim_library=empty_claim_library,
    )
    assert report.entity_type_concentration is None
    assert report.concentration_warning is None


# ── 8d Drift score ─────────────────────────────────────────────────


def test_8d_drift_zero_when_all_declared_present(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing"], edge_types=["member_of"],
    )
    entities = [_ent("a", "wing"), _ent("b", "wing")]
    edges = [_edge("a", "b", "member_of")]
    report = score_cat8(
        ont, entities, edges, {}, claim_library=empty_claim_library,
    )
    assert report.drift_score == pytest.approx(0.0)


def test_8d_drift_proportional_to_missing(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing", "ghost"],
        edge_types=["member_of", "phantom"],
    )
    entities = [_ent("a", "wing"), _ent("b", "wing")]
    edges = [_edge("a", "b", "member_of")]
    report = score_cat8(
        ont, entities, edges, {}, claim_library=empty_claim_library,
    )
    # 2 of 4 declared names actually used → 50% drift
    assert report.drift_score == pytest.approx(0.5)


def test_8d_drift_zero_when_nothing_declared(empty_claim_library):
    ont = ImpliedOntology(version="t", source="inferred")
    report = score_cat8(
        ont, [], [], {}, claim_library=empty_claim_library,
    )
    assert report.drift_score == pytest.approx(0.0)


# ── 8d hall_usage scorer (MemPalace-specific) ─────────────────────


def test_hall_usage_empty_drawers():
    out = _score_hall_usage([], ["code", "decisions"])
    assert out["total_drawers"] == 0
    assert out["fraction_populated"] == 0.0
    assert out["distribution"] == {}


def test_hall_usage_from_properties():
    drawers = [
        _ent("d1", "drawer", hall="code"),
        _ent("d2", "drawer", hall="decisions"),
        _ent("d3", "drawer", hall=""),  # unpopulated
    ]
    out = _score_hall_usage(drawers, ["code", "decisions"])
    assert out["total_drawers"] == 3
    assert out["populated_count"] == 2
    assert out["fraction_populated"] == pytest.approx(2 / 3)
    assert out["distribution"] == {"code": 1, "decisions": 1}
    assert out["in_vocabulary_count"] == 2


def test_hall_usage_falls_back_to_entity_type_suffix():
    """If hall property is empty, the suffix after ``drawer:`` is used."""
    drawers = [
        _ent("d1", "drawer:hall_code"),
        _ent("d2", "drawer:untyped"),  # 'untyped' is filtered out
    ]
    out = _score_hall_usage(drawers, ["hall_code"])
    assert out["populated_count"] == 1
    assert "hall_code" in out["distribution"]
    # 'untyped' is filtered, not counted
    assert "untyped" not in out["distribution"]


def test_hall_usage_in_vocab_accepts_prefix_form():
    """The 'hall_X' form matches a 'X' declared vocabulary entry."""
    drawers = [_ent("d1", "drawer", hall="hall_code")]
    out = _score_hall_usage(drawers, ["code"])
    assert out["in_vocabulary_count"] == 1


def test_hall_usage_ignores_non_drawers():
    """Entities whose type doesn't start with 'drawer' are excluded."""
    ents = [
        _ent("w1", "wing"),
        _ent("r1", "room"),
        _ent("d1", "drawer", hall="code"),
    ]
    out = _score_hall_usage(ents, ["code"])
    assert out["total_drawers"] == 1


def test_score_cat8_populates_hall_usage_when_vocab_declared(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["drawer"], hall_vocabulary=["code"],
    )
    entities = [_ent("d1", "drawer", hall="code")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    assert report.hall_usage is not None
    assert report.hall_usage["populated_count"] == 1


def test_score_cat8_hall_usage_none_when_no_vocab(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared", entity_types=["drawer"]
    )
    entities = [_ent("d1", "drawer", hall="code")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    assert report.hall_usage is None


# ── 8e Claim verification ──────────────────────────────────────────


def test_claim_untestable_via_denylist():
    """An 'easy to use' UX claim matches the untestable pattern."""
    lib = load_claim_library()
    claim = {"id": "c_ux", "text": "intuitive and easy to use"}
    result = _score_claim(claim, [], [], {}, lib)
    assert result.status == "untestable"
    assert "denylist" in result.operational_definition


def test_claim_untestable_when_no_library_match(empty_claim_library):
    claim = {"id": "c_x", "text": "some unmatched claim"}
    result = _score_claim(claim, [], [], {}, empty_claim_library)
    assert result.status == "untestable"


def test_claim_temporal_coverage_pass():
    """An edge with _created_at → temporal claim passes when coverage > 0.5."""
    lib = load_claim_library()
    claim = {"id": "c_t", "text": "Edges track temporal validity"}
    edges = [
        _edge("a", "b", "x", _created_at="2026-01-01"),
        _edge("a", "b", "y", _created_at="2026-01-02"),
        _edge("a", "b", "z"),
    ]
    result = _score_claim(claim, [], edges, {}, lib)
    assert result.status == "pass"
    assert result.metrics["fraction_edges_with_created_at"] == pytest.approx(2 / 3)


def test_claim_temporal_coverage_fail_below_threshold():
    lib = load_claim_library()
    claim = {"id": "c_t", "text": "Temporal tracking is supported"}
    edges = [
        _edge("a", "b", "x"),
        _edge("a", "b", "y"),
        _edge("a", "b", "z", _created_at="2026-01-01"),
    ]
    result = _score_claim(claim, [], edges, {}, lib)
    assert result.status == "fail"


def test_claim_provenance_coverage_pass():
    lib = load_claim_library()
    claim = {"id": "c_p", "text": "We provide provenance tracking"}
    edges = [_edge("a", "b", "x", _created_by="extractor_v1") for _ in range(3)]
    result = _score_claim(claim, [], edges, {}, lib)
    assert result.status == "pass"


def test_claim_cat7_deferral_skipped_without_results():
    lib = load_claim_library()
    claim = {"id": "c_r", "text": "Structure improves retrieval"}
    result = _score_claim(claim, [], [], {}, lib, cat7_results=None)
    assert result.status == "skipped"
    assert "Cat 7" in result.notes


def test_claim_cat7_pass_when_recall_lifts_more_than_5pp():
    lib = load_claim_library()
    claim = {"id": "c_r", "text": "Structure improves retrieval"}
    result = _score_claim(
        claim, [], [], {}, lib,
        cat7_results={"graph_mean_recall": 0.70, "flat_mean_recall": 0.60},
    )
    assert result.status == "pass"
    assert result.metrics["delta_recall"] == pytest.approx(0.10)


def test_claim_cat7_fail_when_recall_within_5pp():
    lib = load_claim_library()
    claim = {"id": "c_r", "text": "boost retrieval"}
    result = _score_claim(
        claim, [], [], {}, lib,
        cat7_results={"graph_mean_recall": 0.62, "flat_mean_recall": 0.60},
    )
    assert result.status == "fail"


def test_claim_cat3_pass_when_contradiction_pairs_present():
    lib = load_claim_library()
    claim = {"id": "c_c", "text": "We detect contradictions"}
    result = _score_claim(
        claim, [], [], {}, lib,
        cat3_results={"contradiction_pairs": 3},
    )
    assert result.status == "pass"


def test_claim_cat3_skipped_without_results():
    lib = load_claim_library()
    claim = {"id": "c_c", "text": "Disagreement surfaces contradictions"}
    result = _score_claim(claim, [], [], {}, lib, cat3_results=None)
    assert result.status == "skipped"


def test_claim_cat2b_pass_above_threshold():
    lib = load_claim_library()
    claim = {"id": "c_d", "text": "We dedup entities"}
    result = _score_claim(
        claim, [], [], {}, lib,
        cat2b_results={"canonicalization_recall": 0.7},
    )
    assert result.status == "pass"


def test_claim_inline_override_cat7_delta_recall_pass():
    """operational_override with metric=cat7_delta_recall — 'not a moat'
    passes when |delta| < 10pp."""
    claim = {
        "id": "c_o",
        "text": "Structure is not a moat",
        "operational_override": {
            "metric": "cat7_delta_recall",
            "pass_condition": "abs delta < 10pp",
            "description": "within ±10pp band",
        },
    }
    result = _score_claim(
        claim, [], [], {},
        {"claims": [], "untestable_patterns": []},
        cat7_results={"graph_mean_recall": 0.55, "flat_mean_recall": 0.52},
    )
    assert result.status == "pass"


def test_claim_inline_override_cat7_delta_recall_fail():
    claim = {
        "id": "c_o",
        "text": "Structure is not a moat",
        "operational_override": {
            "metric": "cat7_delta_recall",
            "pass_condition": "abs delta < 10pp",
        },
    }
    result = _score_claim(
        claim, [], [], {},
        {"claims": [], "untestable_patterns": []},
        cat7_results={"graph_mean_recall": 0.75, "flat_mean_recall": 0.50},
    )
    assert result.status == "fail"


def test_claim_inline_override_unknown_metric():
    claim = {
        "id": "c_o",
        "text": "anything",
        "operational_override": {"metric": "unknown_metric"},
    }
    result = _score_claim(
        claim, [], [], {},
        {"claims": [], "untestable_patterns": []},
    )
    assert result.status == "untestable"
    assert "no override handler" in result.notes


# ── score_cat8 end-to-end ────────────────────────────────────────


def test_score_cat8_perfect_alignment(empty_claim_library):
    """Graph matches the declared ontology perfectly."""
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing", "room"],
        edge_types=["member_of"],
    )
    entities = [
        _ent("w1", "wing"),
        _ent("w2", "wing"),
        _ent("r1", "room"),
    ]
    edges = [_edge("r1", "w1", "member_of")]
    report = score_cat8(
        ont, entities, edges, {"edge_type_entropy_bits": 0.0},
        claim_library=empty_claim_library,
    )
    assert report.type_coverage == pytest.approx(1.0)
    assert report.edge_vocabulary_coverage == pytest.approx(1.0)
    assert report.drift_score == pytest.approx(0.0)
    assert report.types_missing == []
    assert report.edges_missing == []


def test_score_cat8_complete_mismatch(empty_claim_library):
    """Declared types don't appear; graph has only undeclared ones."""
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing", "room"],
        edge_types=["member_of"],
    )
    entities = [_ent("a", "alien"), _ent("b", "stranger")]
    edges = [_edge("a", "b", "weird")]
    report = score_cat8(
        ont, entities, edges, {}, claim_library=empty_claim_library,
    )
    assert report.type_coverage == pytest.approx(0.0)
    assert report.edge_vocabulary_coverage == pytest.approx(0.0)
    assert report.drift_score == pytest.approx(1.0)
    assert sorted(report.types_undeclared) == ["alien", "stranger"]


def test_score_cat8_empty_graph(empty_claim_library):
    """No entities, no edges — everything is missing, coverage is zero."""
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["wing"], edge_types=["member_of"],
    )
    report = score_cat8(
        ont, [], [], {}, claim_library=empty_claim_library,
    )
    assert report.type_coverage == pytest.approx(0.0)
    assert report.edge_vocabulary_coverage == pytest.approx(0.0)
    assert report.entity_type_concentration is None


def test_score_cat8_claim_pass_rate(empty_claim_library):
    """Two structural claims: one passes (temporal), one fails (provenance)."""
    lib = load_claim_library()
    ont = ImpliedOntology(
        version="t", source="declared", entity_types=["x"],
        structural_claims=[
            {"id": "c1", "text": "Edges have temporal validity"},
            {"id": "c2", "text": "Provenance lineage tracking"},
        ],
    )
    entities = [_ent("a", "x"), _ent("b", "x")]
    # All edges have _created_at (temporal passes); none have _created_by
    edges = [
        _edge("a", "b", "e1", _created_at="2026-01-01"),
        _edge("a", "b", "e2", _created_at="2026-01-02"),
    ]
    report = score_cat8(ont, entities, edges, {}, claim_library=lib)
    assert report.claims_tested == 2
    assert report.claims_passed == 1
    assert report.claims_pass_rate == pytest.approx(0.5)


def test_score_cat8_vocabulary_claim_passes_when_halls_populated(
    empty_claim_library,
):
    """The 'five_standard_halls' vocab claim passes if ≥50% drawers have hall."""
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["drawer"],
        hall_vocabulary=["code", "decisions"],
        vocabulary_claims=[
            {"id": "five_standard_halls", "text": "Five halls declared"}
        ],
    )
    entities = [
        _ent("d1", "drawer", hall="code"),
        _ent("d2", "drawer", hall="decisions"),
    ]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    hall_claim = next(c for c in report.claims if c.claim_id == "five_standard_halls")
    assert hall_claim.status == "pass"
    assert hall_claim.metrics["populated_count"] == 2


def test_score_cat8_vocabulary_claim_fails_when_halls_empty(empty_claim_library):
    ont = ImpliedOntology(
        version="t", source="declared",
        entity_types=["drawer"],
        hall_vocabulary=["code"],
        vocabulary_claims=[
            {"id": "five_standard_halls", "text": "Five halls declared"}
        ],
    )
    entities = [_ent("d1", "drawer")]  # no hall property
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    hall_claim = next(c for c in report.claims if c.claim_id == "five_standard_halls")
    assert hall_claim.status == "fail"


def test_score_cat8_introspection_score_is_zero_by_default(empty_claim_library):
    ont = ImpliedOntology(version="t", source="declared")
    report = score_cat8(
        ont, [], [], {}, claim_library=empty_claim_library,
    )
    assert report.introspection_score == 0.0
    assert report.introspection_available == []


# ── to_dict() shape contract ─────────────────────────────────────


def test_to_dict_top_level_keys(empty_claim_library):
    ont = ImpliedOntology(version="t", source="declared", entity_types=["x"])
    entities = [_ent("a", "x")]
    report = score_cat8(
        ont, entities, [], {}, claim_library=empty_claim_library,
    )
    d = report.to_dict()
    assert {
        "8a_type_coverage",
        "8b_edge_vocabulary",
        "8c_schema_alignment",
        "8d_drift",
        "8e_claims",
        "introspection",
    } <= set(d.keys())


def test_to_dict_claim_detail_round_trip(empty_claim_library):
    report = Cat8Report()
    report.claims = [
        ClaimResult(
            claim_id="x",
            claim_text="foo",
            status="pass",
            operational_definition="def",
            metrics={"m": 1.0},
            notes="ok",
        )
    ]
    d = report.to_dict()
    detail = d["8e_claims"]["detail"][0]
    assert detail["id"] == "x"
    assert detail["status"] == "pass"
    assert detail["metrics"]["m"] == 1.0
