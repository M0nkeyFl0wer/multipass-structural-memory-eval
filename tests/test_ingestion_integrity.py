"""Correctness tests for Cat 4 (The Threshold).

Every assertion traces back to a field in the fixture's
``ground_truth`` dict — when a test fails, the reading the scorer
produced for that field is the suspect, not the fixture.
"""

from __future__ import annotations

from sme.categories.ingestion_integrity import (
    COLLISION_GROUP_ID_RENDER_LIMIT,
    default_canonical_key,
    format_report,
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


def test_collision_group_id_degrees_populated(duplicates_graph):
    """Issue #13 — each collision group surfaces per-ID degree so the
    operator can tell which ID is the canonical one when deduplicating."""
    entities, edges, truth = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    tool_docker = [
        g
        for g in report.collision_groups
        if g.entity_type == "tool"
        and default_canonical_key("Docker", "tool") == g.canonical_key
    ]
    assert len(tool_docker) == 1
    group = tool_docker[0]
    assert group.id_degrees == truth["collision_id_degrees"]


def test_format_report_shows_collision_degree_and_keeper(duplicates_graph):
    """Issue #13 — the collision-group section should print per-ID degree
    and mark the highest-degree ID with the '← keep' hint."""
    entities, edges, _ = duplicates_graph
    report = score_ingestion_integrity(entities, edges)
    rendered = format_report(report)
    # e1 is the only Docker variant with edges (degree 4); the others
    # are degree 0 stragglers.
    assert "e1  (deg=4)" in rendered
    assert "e2  (deg=0)" in rendered
    assert "← keep" in rendered
    # The keep marker should be on the e1 line, not on e2/e3/e4.
    e1_line = next(line for line in rendered.splitlines() if "e1  (deg=4)" in line)
    assert "← keep" in e1_line
    for losing_id in ("e2", "e3", "e4"):
        losing_line = next(
            line for line in rendered.splitlines() if f"{losing_id}  (deg=0)" in line
        )
        assert "← keep" not in losing_line


def test_format_report_truncates_large_collision_group():
    """A collision group with more than COLLISION_GROUP_ID_RENDER_LIMIT IDs
    renders the top-N by degree and footer-summarizes the rest."""
    from sme.adapters.base import Edge, Entity

    n_ids = COLLISION_GROUP_ID_RENDER_LIMIT + 7
    # All IDs canonicalize to the same key (same name + type).
    entities = [
        Entity(id=f"d{i:02d}", name="Docker", entity_type="tool")
        for i in range(n_ids)
    ]
    # Give each ID a distinct degree so ranking is unambiguous: d00 highest.
    edges = []
    for i in range(n_ids):
        for _ in range(n_ids - i):
            edges.append(
                Edge(source_id=f"d{i:02d}", target_id="sink", edge_type="uses")
            )

    report = score_ingestion_integrity(entities, edges)
    rendered = format_report(report)

    # Exactly the top-N IDs are rendered; the footer accounts for the rest.
    assert "... and 7 more" in rendered
    rendered_id_lines = [
        line for line in rendered.splitlines() if "(deg=" in line
    ]
    assert len(rendered_id_lines) == COLLISION_GROUP_ID_RENDER_LIMIT
    # Highest-degree ID is rendered and kept; a low-rank ID is truncated.
    assert "d00  (deg=" in rendered
    assert "d16  (deg=" not in rendered


def test_format_report_keeper_is_deterministic_on_tie():
    """When several IDs tie at the max degree, exactly one is marked the
    keeper, tie-broken lexicographically on ID for stability across runs."""
    from sme.adapters.base import Edge, Entity

    # Three IDs canonicalize together; two tie at the max degree.
    entities = [
        Entity(id="zeta", name="Docker", entity_type="tool"),
        Entity(id="alpha", name="Docker", entity_type="tool"),
        Entity(id="mid", name="Docker", entity_type="tool"),
    ]
    # zeta and alpha both have degree 2 (tie at max); mid has degree 1.
    edges = [
        Edge(source_id="zeta", target_id="x", edge_type="uses"),
        Edge(source_id="zeta", target_id="y", edge_type="uses"),
        Edge(source_id="alpha", target_id="x", edge_type="uses"),
        Edge(source_id="alpha", target_id="y", edge_type="uses"),
        Edge(source_id="mid", target_id="x", edge_type="uses"),
    ]

    report = score_ingestion_integrity(entities, edges)
    rendered = format_report(report)

    keep_lines = [line for line in rendered.splitlines() if "← keep" in line]
    assert len(keep_lines) == 1
    # 'alpha' < 'zeta' lexicographically, so alpha is the deterministic keeper.
    assert "alpha" in keep_lines[0]
    assert "zeta" not in keep_lines[0]
