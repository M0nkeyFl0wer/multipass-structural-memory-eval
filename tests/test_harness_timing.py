"""Tests for harness-level timing wrapper."""

from __future__ import annotations

import time

from sme.adapters.base import QueryResult, SMEAdapter
from sme.harness.wrapper import timed_query


class MockAdapter(SMEAdapter):
    """Adapter that sleeps a fixed amount in query()."""

    def __init__(self, sleep_seconds: float = 0.05) -> None:
        self.sleep_seconds = sleep_seconds

    def ingest_corpus(self, corpus):
        return {"entities_created": 0, "edges_created": 0, "errors": [], "warnings": []}

    def query(self, question):
        time.sleep(self.sleep_seconds)
        return QueryResult(answer="mock")

    def get_graph_snapshot(self):
        return [], []


def test_timed_query_records_latency_and_turns():
    adapter = MockAdapter(sleep_seconds=0.05)
    result = timed_query(adapter, "test question")
    assert result.latency_ms >= 45.0
    assert result.interaction_turns == 1


def test_timed_query_preserves_multi_turn_count():
    class MultiTurnAdapter(SMEAdapter):
        def ingest_corpus(self, corpus):
            return {"entities_created": 0, "edges_created": 0, "errors": [], "warnings": []}

        def query(self, question):
            return QueryResult(answer="mock", interaction_turns=3)

        def get_graph_snapshot(self):
            return [], []

    adapter = MultiTurnAdapter()
    result = timed_query(adapter, "test question")
    assert result.interaction_turns == 3
    assert result.latency_ms >= 0.0
