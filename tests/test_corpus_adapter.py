"""Tests for the backend-free CorpusAdapter.

The adapter turns a markdown vault's answer-key frontmatter into an SME
graph snapshot, so the structural categories (cat4/cat5/cat8) can run on a
shipped corpus with no database. Every assertion here is a claim about that
projection: field mapping, dedup, stub creation, and tolerance of the
double-nested-edges authoring slip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sme.adapters.corpus import CorpusAdapter

GOOD_DOG_VAULT = (
    Path(__file__).resolve().parent.parent
    / "sme"
    / "corpora"
    / "good-dog-corpus"
    / "vault"
)


def _write(vault: Path, rel: str, frontmatter: str) -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\n\nbody text\n")


# --- Field mapping ----------------------------------------------------


def test_frontmatter_maps_to_entity_and_edge_fields(tmp_path):
    _write(
        tmp_path,
        "a.md",
        """
note_id: n1
entities:
  - id: breed_amstaff
    type: breed
    canonical: "AmStaff"
    aliases: ["Staffy"]
edges:
  - from: pub_x
    type: mentions
    to: breed_amstaff
    evidence: "title mentions the breed"
""".strip(),
    )
    entities, edges = CorpusAdapter(tmp_path).get_graph_snapshot()

    by_id = {e.id: e for e in entities}
    amstaff = by_id["breed_amstaff"]
    assert amstaff.name == "AmStaff"          # canonical -> name
    assert amstaff.entity_type == "breed"     # type -> entity_type
    assert amstaff.properties["aliases"] == ["Staffy"]  # extra keys preserved

    assert len(edges) == 1
    edge = edges[0]
    assert (edge.source_id, edge.edge_type, edge.target_id) == (
        "pub_x", "mentions", "breed_amstaff",
    )
    assert edge.properties["evidence"] == "title mentions the breed"


def test_name_falls_back_to_id_when_no_canonical(tmp_path):
    _write(tmp_path, "a.md", "entities:\n  - id: bare_ent\n    type: concept")
    entities, _ = CorpusAdapter(tmp_path).get_graph_snapshot()
    assert {e.id: e.name for e in entities}["bare_ent"] == "bare_ent"


# --- Stubs and dedup --------------------------------------------------


def test_edge_endpoint_without_declaration_becomes_a_stub(tmp_path):
    """An edge to an entity nobody declared must not drop the edge; it
    should create a typed 'unknown' stub so topology stays intact."""
    _write(
        tmp_path,
        "a.md",
        """
entities:
  - id: declared
    type: concept
edges:
  - from: declared
    type: mentions
    to: never_declared
""".strip(),
    )
    entities, edges = CorpusAdapter(tmp_path).get_graph_snapshot()
    by_id = {e.id: e for e in entities}
    assert len(edges) == 1                       # edge preserved
    assert "never_declared" in by_id             # stub created
    assert by_id["never_declared"].entity_type == "unknown"
    assert by_id["never_declared"].properties.get("stub") is True
    assert by_id["declared"].properties.get("stub") is not True


def test_duplicate_entity_id_later_declaration_wins(tmp_path):
    _write(tmp_path, "a.md", "entities:\n  - id: dup\n    type: breed\n    canonical: First")
    _write(tmp_path, "b.md", "entities:\n  - id: dup\n    type: breed\n    canonical: Second")
    entities, _ = CorpusAdapter(tmp_path).get_graph_snapshot()
    names = {e.id: e.name for e in entities}
    assert names["dup"] == "Second"              # b.md sorts after a.md, wins
    assert len([e for e in entities if e.id == "dup"]) == 1  # no duplication


# --- Robustness -------------------------------------------------------


def test_double_nested_edges_are_flattened_not_fatal(tmp_path):
    """The `edges: [[ {...} ]]` authoring slip must be recovered, not crash
    (the corpus validator used to AttributeError on exactly this)."""
    _write(
        tmp_path,
        "a.md",
        """
entities:
  - id: p
    type: publication
edges:
  - from: p
    type: mentions
    to: c1
  - - from: p
      type: mentions
      to: c2
""".strip(),
    )
    entities, edges = CorpusAdapter(tmp_path).get_graph_snapshot()
    pairs = {(e.source_id, e.target_id) for e in edges}
    assert ("p", "c1") in pairs
    assert ("p", "c2") in pairs                   # recovered from the nesting


def test_malformed_edge_missing_fields_is_skipped(tmp_path):
    _write(
        tmp_path,
        "a.md",
        "entities:\n  - id: p\n    type: publication\n"
        "edges:\n  - from: p\n    type: mentions\n",  # no 'to'
    )
    _, edges = CorpusAdapter(tmp_path).get_graph_snapshot()
    assert edges == []                            # dropped, no crash


def test_snapshot_is_cached(tmp_path):
    _write(tmp_path, "a.md", "entities:\n  - id: e\n    type: concept")
    adapter = CorpusAdapter(tmp_path)
    assert adapter.get_graph_snapshot() is adapter.get_graph_snapshot()


# --- Ontology source (Cat 8) ------------------------------------------


def test_ontology_source_reads_sibling_ontology_yaml(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (tmp_path / "ontology.yaml").write_text(
        "entity_types:\n  - id: breed\nedge_types:\n  - id: mentions\n"
    )
    _write(vault, "a.md", "entities:\n  - id: e\n    type: breed")
    src = CorpusAdapter(vault).get_ontology_source()
    assert src["type"] == "declared"
    assert {"id": "breed"} in src["schema"]


# --- Real corpus smoke ------------------------------------------------


@pytest.mark.skipif(not GOOD_DOG_VAULT.exists(), reason="good-dog vault not present")
def test_good_dog_snapshot_is_nonempty():
    entities, edges = CorpusAdapter(GOOD_DOG_VAULT).get_graph_snapshot()
    assert len(entities) > 50
    assert len(edges) > 50


@pytest.mark.skipif(not GOOD_DOG_VAULT.exists(), reason="good-dog vault not present")
def test_good_dog_runs_through_cat5():
    pytest.importorskip("ripser", reason="Ripser not installed")
    from sme.categories.gap_detection import score_gap_detection

    entities, edges = CorpusAdapter(GOOD_DOG_VAULT).get_graph_snapshot()
    report = score_gap_detection(entities, edges, null_samples=0)
    assert report.nodes == len(entities)
    assert report.components >= 1
