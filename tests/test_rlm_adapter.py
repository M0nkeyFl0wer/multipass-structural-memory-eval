"""Unit tests for RlmAdapter.

We don't exercise the real RLM/portkey/openai backend in tests because
that would burn API credits and require live network. Instead we patch
the RLM class so completion() returns a stubbed response and triggers
mempalace_search via the captured tool callable.

A live A/B benchmark (rlm vs familiar on jp-realm-v0.1) belongs in
baselines/, not in unit tests — it's a research run, not a contract
check.

The `rlm` package itself is not installable from PyPI under that name
(the distribution is `rlms`, source on GitHub) and requires Python
>=3.11, so it sits behind the `[rlm]` extra in pyproject. On a fresh
clone without that extra installed, this whole test module skips.
Install via:
    pip install -e ".[rlm]"
"""

from __future__ import annotations

import pytest

pytest.importorskip("rlm")

import json  # noqa: E402  (intentionally after importorskip)
from unittest.mock import MagicMock, patch  # noqa: E402
from urllib import request as _urlrequest  # noqa: E402


def _stub_palace_response(results: list[dict]) -> bytes:
    return json.dumps({"query": "x", "results": results}).encode("utf-8")


def test_query_aggregates_tool_calls_into_context_string(monkeypatch):
    captured_tool: list = []

    class _StubRLM:
        def __init__(self, *args, **kwargs):
            # Capture the mempalace_search tool the adapter passed to RLM.
            tools = kwargs["custom_tools"]
            self._search = tools["mempalace_search"]["tool"]
            captured_tool.append(self._search)

        def completion(self, q):
            # Simulate the LM calling mempalace_search as part of its REPL.
            self._search("hermes-agent", limit=2)
            self._search("rlm recursive", limit=2)
            return MagicMock(response="rlm-orchestrated answer")

    # Stub palace-daemon over urllib — return two different result sets.
    call_count = {"n": 0}

    class _Resp:
        def __init__(self, body): self._body = body
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self._body

    def _stub_urlopen(req, timeout=None):
        call_count["n"] += 1
        if "hermes" in req.full_url:
            return _Resp(_stub_palace_response([
                {"drawer_id": "drawer_x1", "text": "hermes-agent is a JP fork", "wing": "projects", "room": "forks", "similarity": 0.78},
            ]))
        return _Resp(_stub_palace_response([
            {"drawer_id": "drawer_x2", "text": "rlm is a recursive language model paradigm", "wing": "projects", "room": "forks", "similarity": 0.82},
        ]))

    with patch("rlm.RLM", _StubRLM), patch.object(_urlrequest, "urlopen", _stub_urlopen):
        from sme.adapters.rlm_adapter import RlmAdapter
        a = RlmAdapter(api_url="http://test:8085", api_key="k", backend="openai")
        out = a.query("tell me about hermes-agent and rlm")

    assert out.error is None
    assert out.answer == "rlm-orchestrated answer"
    # Both captured tool calls' results land in context_string.
    assert "hermes-agent is a JP fork" in out.context_string
    assert "rlm is a recursive language model paradigm" in out.context_string
    # The synthesized answer is also there, so substring-scorers that
    # match on what the system surfaced see both retrieval + synthesis.
    assert "── RLM answer ──" in out.context_string
    assert "rlm-orchestrated answer" in out.context_string
    # And in retrieved_entities, in call order.
    ids = [e.id for e in out.retrieved_entities]
    assert ids == ["drawer_x1", "drawer_x2"]
    # retrieval_path notes the rlm step + tool count (single string entry,
    # cli formats it via '; '.join).
    assert "rlm_completion" in out.retrieval_path[0]
    assert "2 tool calls" in out.retrieval_path[0]


def test_query_capture_resets_between_calls():
    """Two consecutive query() calls should not leak entities between them."""

    class _StubRLM:
        def __init__(self, *args, **kwargs):
            self._search = kwargs["custom_tools"]["mempalace_search"]["tool"]

        def completion(self, q):
            self._search("first call", limit=1)
            return MagicMock(response="ok")

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return _stub_palace_response([
            {"drawer_id": "d1", "text": "t", "wing": "w", "room": "r", "similarity": 0.5},
        ])

    def _stub_urlopen(req, timeout=None):
        return _Resp()

    with patch("rlm.RLM", _StubRLM), patch.object(_urlrequest, "urlopen", _stub_urlopen):
        from sme.adapters.rlm_adapter import RlmAdapter
        a = RlmAdapter(api_url="http://test:8085", api_key="k", backend="openai")
        first = a.query("q1")
        second = a.query("q2")

    # Each call captures exactly one drawer; second call doesn't see first's.
    assert len(first.retrieved_entities) == 1
    assert len(second.retrieved_entities) == 1


def test_search_failure_returned_as_error_dict_not_raised():
    """Network failures inside mempalace_search shouldn't crash query()."""

    class _StubRLM:
        def __init__(self, *args, **kwargs):
            self._search = kwargs["custom_tools"]["mempalace_search"]["tool"]

        def completion(self, q):
            results = self._search("anything")
            return MagicMock(response=f"saw {len(results)} candidates")

    def _stub_urlopen(req, timeout=None):
        raise OSError("connection refused")

    with patch("rlm.RLM", _StubRLM), patch.object(_urlrequest, "urlopen", _stub_urlopen):
        from sme.adapters.rlm_adapter import RlmAdapter
        a = RlmAdapter(api_url="http://test:8085", api_key="k", backend="openai")
        out = a.query("x")

    assert out.error is None  # query() didn't crash
    # The failure is visible in the answer (RLM saw the error dict and stringified it).
    assert "saw 1 candidates" in out.answer  # one capture entry, the error one
    # No entities captured (the failure dict has no drawer_id).
    assert out.retrieved_entities == []


def test_get_graph_snapshot_returns_empty():
    """RLM doesn't maintain a graph view — Cat 8 is N/A."""
    class _StubRLM:
        def __init__(self, *args, **kwargs): pass

    with patch("rlm.RLM", _StubRLM):
        from sme.adapters.rlm_adapter import RlmAdapter
        a = RlmAdapter(api_url="http://x", api_key="k")
        ents, edges = a.get_graph_snapshot()
        assert ents == []
        assert edges == []


def test_ingest_corpus_is_skipped():
    class _StubRLM:
        def __init__(self, *args, **kwargs): pass

    with patch("rlm.RLM", _StubRLM):
        from sme.adapters.rlm_adapter import RlmAdapter
        a = RlmAdapter(api_url="http://x", api_key="k")
        out = a.ingest_corpus([{"id": "ignored"}])
        assert out["skipped"] is True
        assert out["entities_created"] == 0
