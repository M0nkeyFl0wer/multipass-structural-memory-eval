"""Tests for the CKG adapter (sme/adapters/ckg.py).

Pins down the three required SMEAdapter methods (ingest_corpus, query,
get_graph_snapshot) plus the CKG-specific Condition C serializer used
by scripts/run_ckg_experiment.py to isolate "did structure earn the
score, or just the content?"

See docs/ckg_benchmark_experiment.md for the experiment methodology
this adapter supports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sme.adapters.ckg import CKGAdapter

# --- Fixtures ---------------------------------------------------------


@pytest.fixture
def tiny_csv(tmp_path: Path) -> Path:
    """A 5-concept DAG with one multi-parent and one taxonomy clash.

    Shape:
        Function (FOUND, root)
          ├── Domain (FOUND)
          ├── Notation (FOUND)
          └── Composite (FOUND, parents=Function|Notation)
                └── Logarithm (LOG, parent=Composite)
    """
    p = tmp_path / "tiny.csv"
    p.write_text(
        "ConceptID,ConceptLabel,Dependencies,TaxonomyID\n"
        "1,Function,,FOUND\n"
        "2,Domain,1,FOUND\n"
        "3,Notation,1,FOUND\n"
        "4,Composite,1|3,FOUND\n"
        "5,Logarithm,4,LOG\n"
    )
    return p


@pytest.fixture
def phantom_csv(tmp_path: Path) -> Path:
    """A CSV with one phantom dependency (parent ConceptID 99 doesn't exist).
    Used to verify Cat 2 ingestion-integrity error reporting.
    """
    p = tmp_path / "phantom.csv"
    p.write_text(
        "ConceptID,ConceptLabel,Dependencies,TaxonomyID\n"
        "1,Alpha,,FOUND\n"
        "2,Beta,99,FOUND\n"
    )
    return p


# --- ingest_corpus / get_graph_snapshot ------------------------------


def test_ingest_loads_via_csv_path(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv)
    report = adapter.ingest_corpus([])
    assert report["entities_created"] == 5
    assert report["edges_created"] == 5  # 1+1+2+1
    assert report["errors"] == []
    assert report["warnings"] == []


def test_ingest_loads_via_corpus_dict_with_csv_path(tiny_csv: Path):
    adapter = CKGAdapter()
    report = adapter.ingest_corpus([{"csv_path": str(tiny_csv)}])
    assert report["entities_created"] == 5
    assert report["edges_created"] == 5


def test_phantom_dependency_is_reported_not_raised(phantom_csv: Path):
    adapter = CKGAdapter(phantom_csv)
    report = adapter.ingest_corpus([])
    assert report["entities_created"] == 2
    assert report["edges_created"] == 0  # phantom edge dropped
    assert any("phantom" in e for e in report["errors"])


def test_get_graph_snapshot_returns_typed_objects(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv)
    adapter.ingest_corpus([])
    entities, edges = adapter.get_graph_snapshot()
    assert {e.id for e in entities} == {"1", "2", "3", "4", "5"}
    assert all(e.entity_type for e in entities)
    composite_parents = {e.target_id for e in edges if e.source_id == "4"}
    assert composite_parents == {"1", "3"}  # multi-parent preserved


# --- query (Condition B) ---------------------------------------------


def test_query_finds_target_by_substring(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv, hop_budget=1)
    adapter.ingest_corpus([])
    result = adapter.query("What is Composite?")
    assert result.error is None
    target_ids = [e.id for e in result.retrieved_entities if e.name == "Composite"]
    assert target_ids == ["4"]


def test_query_returns_no_match_for_unknown_concept(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv)
    adapter.ingest_corpus([])
    result = adapter.query("What is Xenomorph?")
    # falls through to token-overlap matcher; with no overlap, returns NO_MATCH
    if result.error is None:
        # If matcher found something via fuzzy match, retrieved must be non-empty
        assert result.retrieved_entities
    else:
        assert result.error == "NO_MATCH"


def test_query_traverses_to_hop_budget(tiny_csv: Path):
    """Composite has parents Function, Notation and child Logarithm.
    At hop_budget=1, B should retrieve {Composite, Function, Notation, Logarithm}.
    Not {Domain} — Domain is 2 hops away (Composite→Function→Domain).
    """
    adapter = CKGAdapter(tiny_csv, hop_budget=1)
    adapter.ingest_corpus([])
    result = adapter.query("Composite")
    names = {e.name for e in result.retrieved_entities}
    assert names == {"Composite", "Function", "Notation", "Logarithm"}


def test_query_context_string_includes_typed_triples(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv)
    adapter.ingest_corpus([])
    result = adapter.query("Composite")
    assert "DEPENDS_ON" in result.context_string
    assert "<Composite>" in result.context_string


# --- get_flat_retrieval (Condition A) --------------------------------


def test_flat_retrieval_returns_top_k(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv, n_flat_results=3)
    adapter.ingest_corpus([])
    result = adapter.get_flat_retrieval("What is Composite Function?")
    assert result.error is None
    assert 1 <= len(result.retrieved_entities) <= 3


def test_flat_retrieval_handles_empty_query(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv)
    adapter.ingest_corpus([])
    result = adapter.get_flat_retrieval("")
    assert result.error == "EMPTY_QUERY"


# --- Condition C serializer ------------------------------------------


def test_condition_c_omits_typed_triple_format(tiny_csv: Path):
    """Condition C is the same node set as B but no edges — prose only."""
    adapter = CKGAdapter(tiny_csv)
    adapter.ingest_corpus([])
    res_b = adapter.query("Composite")
    c_text = adapter.condition_c_serialization(res_b.retrieved_entities)
    assert "DEPENDS_ON" not in c_text  # no typed-triple syntax
    assert "Composite" in c_text  # but the labels survive


# --- get_ontology_source ---------------------------------------------


def test_ontology_source_is_declared(tiny_csv: Path):
    adapter = CKGAdapter(tiny_csv)
    source = adapter.get_ontology_source()
    assert source["type"] == "declared"
    field_names = {f["field"] for f in source["schema"]}
    assert field_names == {"ConceptID", "ConceptLabel", "Dependencies", "TaxonomyID"}
