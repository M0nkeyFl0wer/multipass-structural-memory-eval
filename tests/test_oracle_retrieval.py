"""Tests for the oracle retrieval baseline adapter (TREC upper bound).

See ``sme/adapters/oracle_retrieval.py``.
"""

from __future__ import annotations

from sme.adapters.oracle_retrieval import OracleRetrievalAdapter


def _make_questions() -> list[dict]:
    return [
        {
            "text": "what is the capital of france?",
            "expected_sources": ["Paris is the capital of France."],
        },
        {
            "text": "who wrote hamlet?",
            "expected_sources": [
                "Hamlet was written by William Shakespeare.",
                "Shakespeare's tragedies include Hamlet, Macbeth, and Othello.",
            ],
        },
    ]


def test_ingest_corpus_stores_items() -> None:
    adapter = OracleRetrievalAdapter(questions=_make_questions())
    corpus = [{"id": "a", "text": "first"}, {"id": "b", "text": "second"}]
    result = adapter.ingest_corpus(corpus)
    assert result["entities_created"] == 2
    assert result["edges_created"] == 0
    assert result["errors"] == []


def test_query_returns_expected_sources_for_known_question() -> None:
    adapter = OracleRetrievalAdapter(questions=_make_questions())
    adapter.ingest_corpus([])
    result = adapter.query("what is the capital of france?")
    assert result.error is None
    assert len(result.retrieved_entities) == 1
    assert result.retrieved_entities[0].name == "Paris is the capital of France."
    assert result.retrieved_entities[0].entity_type == "oracle_source"
    # Entity ID tracks the gold source string, not a loop index, so
    # per-ID downstream analysis (Cat 4/Cat 5) can map back to the
    # source.
    assert (
        result.retrieved_entities[0].id
        == "oracle:Paris is the capital of France."
    )


def test_query_returns_all_expected_sources() -> None:
    adapter = OracleRetrievalAdapter(questions=_make_questions())
    result = adapter.query("who wrote hamlet?")
    assert result.error is None
    assert len(result.retrieved_entities) == 2


def test_expected_sources_appear_in_context_string() -> None:
    adapter = OracleRetrievalAdapter(questions=_make_questions())
    result = adapter.query("who wrote hamlet?")
    # The scorer uses substring matching, so each expected source must
    # appear verbatim in context_string.
    assert "Hamlet was written by William Shakespeare." in result.context_string
    assert (
        "Shakespeare's tragedies include Hamlet, Macbeth, and Othello."
        in result.context_string
    )


def test_unknown_question_returns_error() -> None:
    adapter = OracleRetrievalAdapter(questions=_make_questions())
    result = adapter.query("a question we have never seen")
    assert result.error == "NO_GOLD_ANSWER"
    assert result.context_string == ""
    assert result.retrieved_entities == []


def test_empty_questions_list_treats_every_query_as_unknown() -> None:
    adapter = OracleRetrievalAdapter()
    result = adapter.query("anything")
    assert result.error == "NO_GOLD_ANSWER"


def test_questions_without_text_or_sources_are_skipped() -> None:
    questions = [
        {"text": "", "expected_sources": ["x"]},
        {"text": "q", "expected_sources": []},
        {"text": "valid", "expected_sources": ["answer"]},
    ]
    adapter = OracleRetrievalAdapter(questions=questions)
    # Only the third entry made it into the gold lookup.
    assert adapter.query("").error == "NO_GOLD_ANSWER"
    assert adapter.query("q").error == "NO_GOLD_ANSWER"
    assert adapter.query("valid").error is None


def test_graph_snapshot_is_empty() -> None:
    adapter = OracleRetrievalAdapter(questions=_make_questions())
    entities, edges = adapter.get_graph_snapshot()
    assert entities == []
    assert edges == []
