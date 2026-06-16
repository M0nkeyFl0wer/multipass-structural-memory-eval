"""Tests for the random retrieval baseline adapter (TREC lower bound).

See ``sme/adapters/random_retrieval.py``.
"""

from __future__ import annotations

from sme.adapters.random_retrieval import RandomRetrievalAdapter


def _make_corpus(n: int) -> list[dict]:
    return [
        {"id": f"item_{i}", "source_file": f"file_{i}.md", "text": f"body {i}"}
        for i in range(n)
    ]


def test_ingest_corpus_stores_items() -> None:
    adapter = RandomRetrievalAdapter()
    corpus = _make_corpus(5)
    result = adapter.ingest_corpus(corpus)
    assert result["entities_created"] == 5
    assert result["edges_created"] == 0
    assert result["errors"] == []
    assert result["warnings"] == []


def test_query_returns_n_results_items() -> None:
    adapter = RandomRetrievalAdapter(n_results=3)
    adapter.ingest_corpus(_make_corpus(10))
    result = adapter.query("anything")
    assert result.error is None
    assert len(result.retrieved_entities) == 3
    # All selected items should reference real corpus sources.
    for ent in result.retrieved_entities:
        assert ent.name.startswith("file_")
        assert ent.entity_type == "random_selection"
        # Entity IDs track the corpus item's intrinsic id, not a loop
        # index, so per-ID downstream analysis (Cat 4/Cat 5) can map a
        # returned entity back to the source corpus item.
        assert ent.id.startswith("random:item_")
    # Context string is non-empty and contains source labels.
    assert result.context_string
    assert "[1]" in result.context_string


def test_query_caps_at_corpus_size() -> None:
    adapter = RandomRetrievalAdapter(n_results=100)
    adapter.ingest_corpus(_make_corpus(4))
    result = adapter.query("anything")
    assert len(result.retrieved_entities) == 4


def test_seeded_queries_are_reproducible() -> None:
    corpus = _make_corpus(20)
    a = RandomRetrievalAdapter(seed=42, n_results=5)
    b = RandomRetrievalAdapter(seed=42, n_results=5)
    a.ingest_corpus(corpus)
    b.ingest_corpus(corpus)
    res_a = a.query("q")
    res_b = b.query("q")
    names_a = [e.name for e in res_a.retrieved_entities]
    names_b = [e.name for e in res_b.retrieved_entities]
    assert names_a == names_b


def test_different_seeds_diverge() -> None:
    corpus = _make_corpus(50)
    a = RandomRetrievalAdapter(seed=1, n_results=10)
    b = RandomRetrievalAdapter(seed=2, n_results=10)
    a.ingest_corpus(corpus)
    b.ingest_corpus(corpus)
    names_a = [e.name for e in a.query("q").retrieved_entities]
    names_b = [e.name for e in b.query("q").retrieved_entities]
    assert names_a != names_b


def test_empty_corpus_returns_error() -> None:
    adapter = RandomRetrievalAdapter()
    result = adapter.query("anything")
    assert result.error == "NO_CORPUS"
    assert result.context_string == ""
    assert result.retrieved_entities == []


def test_graph_snapshot_is_empty() -> None:
    adapter = RandomRetrievalAdapter()
    adapter.ingest_corpus(_make_corpus(3))
    entities, edges = adapter.get_graph_snapshot()
    assert entities == []
    assert edges == []
