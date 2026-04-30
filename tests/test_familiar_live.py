"""Gated live-smoke test for FamiliarAdapter.

Skipped unless FAMILIAR_BASE_URL is set, e.g.:
    FAMILIAR_BASE_URL=http://familiar:8080 pytest tests/test_familiar_live.py
"""

from __future__ import annotations

import os

import pytest

from sme.adapters.familiar import FamiliarAdapter


pytestmark = pytest.mark.skipif(
    not os.environ.get("FAMILIAR_BASE_URL"),
    reason="set FAMILIAR_BASE_URL to run live smoke",
)


@pytest.fixture
def adapter() -> FamiliarAdapter:
    return FamiliarAdapter(
        base_url=os.environ["FAMILIAR_BASE_URL"],
        timeout_s=15.0,
        mock_inference=True,
    )


def test_live_query_returns_query_result(adapter: FamiliarAdapter):
    """At minimum, query() returns a QueryResult — no exceptions even if
    palace is rebuilding (which surfaces as a WARN: error string)."""
    result = adapter.query("realm projects")
    assert hasattr(result, "answer")
    assert hasattr(result, "context_string")
    assert hasattr(result, "retrieved_entities")
    assert hasattr(result, "retrieved_edges")
    if result.error:
        # Acceptable error shapes for live test: WARN: prefix or HTTP code
        assert (
            "WARN" in result.error
            or "endpoint" in result.error
            or "timeout" in result.error.lower()
            or "connection" in result.error.lower()
        )


def test_live_get_graph_snapshot_returns_lists(adapter: FamiliarAdapter):
    entities, edges = adapter.get_graph_snapshot()
    assert isinstance(entities, list)
    assert isinstance(edges, list)
    if not entities:
        pytest.skip("graph endpoint returned empty — palace may be rebuilding")
