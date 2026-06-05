"""Tests for sme.eval.deterministic_overlays.

All assertions are deterministic — no API calls, no stochastic behaviour.
"""

from __future__ import annotations

import sys


from sme.adapters.base import Entity, QueryResult
from sme.eval.deterministic_overlays import (
    contextual_precision_proxy,
    token_utilization,
)


# --- contextual_precision_proxy ------------------------------------------


def test_contextual_precision_proxy_perfect_match():
    """All retrieved entities match expected sources."""
    result = QueryResult(
        answer="",
        retrieved_entities=[
            Entity(id="doc_1", name="Alice", entity_type="person"),
            Entity(id="doc_2", name="Bob", entity_type="person"),
        ],
    )
    assert contextual_precision_proxy(result, ["doc_1", "doc_2"]) == 1.0


def test_contextual_precision_proxy_partial_match():
    """Only one of two retrieved entities matches expected sources."""
    result = QueryResult(
        answer="",
        retrieved_entities=[
            Entity(id="doc_1", name="Alice", entity_type="person"),
            Entity(id="doc_3", name="Charlie", entity_type="person"),
        ],
    )
    assert contextual_precision_proxy(result, ["doc_1", "doc_2"]) == 0.5


def test_contextual_precision_proxy_empty_expected_sources():
    """No oracle → None."""
    result = QueryResult(
        answer="",
        retrieved_entities=[
            Entity(id="doc_1", name="Alice", entity_type="person"),
        ],
    )
    assert contextual_precision_proxy(result, []) is None


def test_contextual_precision_proxy_empty_retrieved_entities():
    """Nothing retrieved → 0.0."""
    result = QueryResult(answer="")
    assert contextual_precision_proxy(result, ["doc_1"]) == 0.0


def test_contextual_precision_proxy_match_by_name():
    """Substring match in entity.name is sufficient."""
    result = QueryResult(
        answer="",
        retrieved_entities=[
            Entity(id="e_1", name="Alice in Wonderland", entity_type="book"),
        ],
    )
    assert contextual_precision_proxy(result, ["Wonderland"]) == 1.0


def test_contextual_precision_proxy_no_match():
    """Zero of two retrieved entities match."""
    result = QueryResult(
        answer="",
        retrieved_entities=[
            Entity(id="doc_3", name="Charlie", entity_type="person"),
            Entity(id="doc_4", name="Dana", entity_type="person"),
        ],
    )
    assert contextual_precision_proxy(result, ["doc_1", "doc_2"]) == 0.0


# --- token_utilization ----------------------------------------------------


def test_token_utilization_normal_case():
    """Ratio of answer tokens to context tokens with real tiktoken."""
    result = QueryResult(
        answer="The quick brown fox.",
        context_string="Lorem ipsum dolor sit amet.",
    )
    ratio = token_utilization(result)
    assert ratio is not None
    assert ratio > 0.0


def test_token_utilization_empty_context():
    """Empty context_string → None."""
    result = QueryResult(answer="Some answer.", context_string="")
    assert token_utilization(result) is None


def test_token_utilization_tiktoken_missing(monkeypatch, caplog):
    """When tiktoken is unavailable, fallback to whitespace split."""
    # Remove tiktoken from sys.modules so the import inside the
    # function body raises ModuleNotFoundError.
    monkeypatch.delitem(sys.modules, "tiktoken", raising=False)
    monkeypatch.setitem(sys.modules, "tiktoken", None)

    result = QueryResult(
        answer="one two",
        context_string="a b c d",
    )
    ratio = token_utilization(result)
    assert ratio == 2 / 4
    assert "tiktoken not installed" in caplog.text


def test_token_utilization_zero_context_tokens_fallback(monkeypatch):
    """Edge case: context_string is whitespace-only, so fallback split
    yields zero tokens → None."""
    result = QueryResult(answer="answer", context_string="   \n\t  ")
    # Force fallback path by hiding tiktoken.
    monkeypatch.delitem(sys.modules, "tiktoken", raising=False)
    monkeypatch.setitem(sys.modules, "tiktoken", None)
    assert token_utilization(result) is None
