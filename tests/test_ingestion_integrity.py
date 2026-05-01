"""Correctness tests for Cat 4 (The Threshold).

Every assertion traces back to a field in the fixture's
``ground_truth`` dict — when a test fails, the reading the scorer
produced for that field is the suspect, not the fixture.
"""

from __future__ import annotations

from sme.categories.ingestion_integrity import (
    default_canonical_key,
    score_ingestion_integrity,
)


def test_canonical_key_case_insensitive():
    assert default_canonical_key("Docker", "tool") == default_canonical_key(
        "docker", "tool"
    )
    assert default_canonical_key("DOCKER", "tool") == default_canonical_key(
        "Docker", "tool"
    )


def test_canonical_key_whitespace_normalized():
    assert default_canonical_key("Docker  Swarm", "tool") == default_canonical_key(
        "Docker Swarm", "tool"
    )
    assert default_canonical_key("  Docker  ", "tool") == default_canonical_key(
        "Docker", "tool"
    )


def test_canonical_key_type_matters():
    assert default_canonical_key("Docker", "tool") != default_canonical_key(
        "Docker", "project"
    )


def test_canonical_key_empty_name_returns_empty():
    assert default_canonical_key("", "tool") == ""
    assert default_canonical_key(None, "tool") == ""


def test_entity_and_edge_counts(duplicates_graph):
    entities, edges, truth = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    assert report.entities == truth["entities"]
    assert report.edges == len(edges)


def test_canonical_collisions_match_truth(duplicates_graph):
    entities, edges, truth = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    assert report.canonical_collisions == truth["canonical_collisions"]
    assert report.unique_canonical_keys == truth["unique_canonical_keys"]


def test_collision_group_contains_all_docker_variants(duplicates_graph):
    entities, edges, _ = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    tool_docker = [
        g
        for g in report.collision_groups
        if g.entity_type == "tool"
        and default_canonical_key("Docker", "tool") == g.canonical_key
    ]
    assert len(tool_docker) == 1
    group = tool_docker[0]
    assert set(group.ids) == {"e1", "e2", "e3", "e4"}


def test_same_name_different_type_is_not_a_collision(duplicates_graph):
    """e5 is 'Docker' at entity_type='project' — must not merge with
    the tool-type Docker variants."""
    entities, edges, _ = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    for group in report.collision_groups:
        assert "e5" not in group.ids


def test_required_field_gap_detected(duplicates_graph):
    entities, edges, truth = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    assert report.required_field_gaps == truth["required_field_gaps"]
    assert "e8" in report.gap_examples  # the empty-name entity


def test_required_field_coverage(duplicates_graph):
    entities, edges, truth = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    expected = (truth["entities"] - truth["required_field_gaps"]) / truth["entities"]
    assert abs(report.required_field_coverage - expected) < 1e-9


def test_edge_type_distribution(duplicates_graph):
    entities, edges, truth = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    assert report.edge_type_counts == truth["edge_type_counts"]
    assert report.dominant_edge_type == truth["dominant_edge_type"]
    assert abs(
        report.dominant_edge_type_fraction - truth["dominant_edge_type_fraction"]
    ) < 1e-9


def test_normalized_entropy_bounded(duplicates_graph):
    entities, edges, _ = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    assert 0.0 <= report.edge_type_entropy_normalized <= 1.0


def test_custom_canonicalize_function_is_respected():
    """Adapter can override canonicalization if the pipeline uses a
    richer rule (strip articles, punct, etc.). Cat 4 must honour it."""
    from sme.adapters.base import Entity

    entities = [
        Entity(id="a", name="The Docker",  entity_type="tool"),
        Entity(id="b", name="Docker",      entity_type="tool"),
    ]
    # Default rule: 'The Docker' != 'Docker', no collision.
    default_report = score_ingestion_integrity(entities, [])
    assert default_report.canonical_collisions == 0

    def strip_articles(name: str, etype: str) -> str:
        norm = " ".join(name.split()).lower()
        for article in ("the ", "a ", "an "):
            if norm.startswith(article):
                norm = norm[len(article):]
        return f"{etype}::{norm}"

    custom_report = score_ingestion_integrity(
        entities, [], canonicalize=strip_articles
    )
    assert custom_report.canonical_collisions == 1


def test_empty_graph_is_all_zeros():
    report = score_ingestion_integrity([], [])
    assert report.entities == 0
    assert report.canonical_collisions == 0
    assert report.required_field_coverage == 1.0
    assert report.edge_type_counts == {}
    assert report.dominant_edge_type is None
