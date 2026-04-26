"""Unit tests for FamiliarAdapter."""

from __future__ import annotations

import socket
import urllib.error

import pytest

from sme.adapters.familiar import FamiliarAdapter


EVAL_ROUTE = "POST http://familiar:8080/api/familiar/eval"
GRAPH_ROUTE = "GET http://familiar:8080/api/familiar/graph"


# --- Task 2: instantiation ---

def test_default_construction():
    adapter = FamiliarAdapter()
    assert adapter.base_url == "http://familiar:8080"
    assert adapter.timeout_s == 30.0
    assert adapter.mock_inference is True


def test_explicit_construction():
    adapter = FamiliarAdapter(
        base_url="https://familiar.jphe.in",
        timeout_s=10.0,
        mock_inference=False,
    )
    assert adapter.base_url == "https://familiar.jphe.in"
    assert adapter.timeout_s == 10.0
    assert adapter.mock_inference is False


def test_base_url_trailing_slash_stripped():
    adapter = FamiliarAdapter(base_url="https://familiar.jphe.in/")
    assert adapter.base_url == "https://familiar.jphe.in"


# --- Task 3: ingest_corpus stub ---

def test_ingest_corpus_is_noop():
    adapter = FamiliarAdapter()
    result = adapter.ingest_corpus([{"id": "doc-1", "text": "anything"}])
    assert result["entities_created"] == 0
    assert result["edges_created"] == 0
    assert result["errors"] == []
    assert any("diagnostic-only" in w.lower() or "no-op" in w.lower()
               for w in result["warnings"])


# --- Task 4: query happy path ---

def test_query_happy_path(fake_urlopen_factory):
    """Mocked POST returns SME-shape JSON; adapter deserializes."""
    response_body = {
        "answer": "(mock=true: inference skipped)",
        "context_string": "── Palace context (1 drawer) ──\nUser enjoys hiking.",
        "retrieved_entities": [
            {
                "id": "drawer_abc",
                "type": "drawer",
                "wing": "projects",
                "room": "technical",
                "topic": "hobbies",
                "content_snippet": "User enjoys hiking.",
                "cosine": 0.81,
                "bm25": 0.42,
                "matched_via": "drawer",
                "provenance": {"kind": "observed"},
            }
        ],
        "retrieved_edges": [],
        "error": None,
        "warnings": [],
        "available_in_scope": 151478,
    }
    fake_urlopen_factory({EVAL_ROUTE: response_body})
    adapter = FamiliarAdapter()

    result = adapter.query("What are my hobbies?")

    assert result.error is None
    assert result.answer.startswith("(mock=true")
    assert "User enjoys hiking" in result.context_string
    assert len(result.retrieved_entities) == 1
    e = result.retrieved_entities[0]
    assert e.id == "drawer_abc"
    assert e.entity_type == "drawer"
    assert e.properties["wing"] == "projects"
    assert e.properties["cosine"] == 0.81
    assert result.retrieved_edges == []


def test_query_default_mock_inference_is_true(fake_urlopen_factory, monkeypatch):
    """Cat 1 determinism guarantee: default mock=true."""
    captured = {}

    def capture(routes):
        original = routes
        # Wrap default fake — capture the body before responding
        return None  # not used; we do this inline below

    # Use a custom opener to capture the request body
    import json as _json

    def custom_opener(req, timeout=None):
        captured["body"] = _json.loads(req.data.decode())
        class FakeResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return _json.dumps({
                "answer": "x", "context_string": "x",
                "retrieved_entities": [], "retrieved_edges": [],
                "error": None, "warnings": [],
            }).encode()
            def getcode(self): return 200
        return FakeResp()

    adapter = FamiliarAdapter(opener=custom_opener)
    adapter.query("anything")
    assert captured["body"]["mock"] is True
    assert captured["body"]["kind"] == "content"


def test_query_explicit_mock_false_passes_through(fake_urlopen_factory):
    captured = {}
    import json as _json

    def custom_opener(req, timeout=None):
        captured["body"] = _json.loads(req.data.decode())
        class FakeResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b'{"answer":"","context_string":"","retrieved_entities":[],"retrieved_edges":[],"error":null,"warnings":[]}'
            def getcode(self): return 200
        return FakeResp()

    adapter = FamiliarAdapter(opener=custom_opener, mock_inference=False)
    adapter.query("anything")
    assert captured["body"]["mock"] is False


# --- Task 5: HTTP / network error contract ---

def test_query_http_500(fake_urlopen_factory):
    fake_urlopen_factory({EVAL_ROUTE: (500, {"error": "internal"})})
    result = FamiliarAdapter().query("anything")
    assert result.error is not None
    assert "500" in result.error
    assert result.retrieved_entities == []


def test_query_http_400(fake_urlopen_factory):
    fake_urlopen_factory({EVAL_ROUTE: (400, {"error": "bad json"})})
    result = FamiliarAdapter().query("anything")
    assert "400" in (result.error or "")


def test_query_timeout():
    def raising(*a, **kw):
        raise socket.timeout("boom")
    result = FamiliarAdapter(opener=raising, timeout_s=2.0).query("anything")
    assert result.error is not None
    assert "timeout" in result.error.lower() or "boom" in result.error


def test_query_connection_refused():
    def raising(*a, **kw):
        raise urllib.error.URLError("Connection refused")
    result = FamiliarAdapter(opener=raising).query("anything")
    assert result.error is not None
    assert "connection" in result.error.lower() or "refused" in result.error.lower()


def test_query_invalid_json():
    class BadJsonResp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b"not json at all"
        def getcode(self): return 200
    def opener(*a, **kw):
        return BadJsonResp()
    result = FamiliarAdapter(opener=opener).query("anything")
    assert result.error is not None
    assert "json" in result.error.lower()


# --- Task 6: warnings translation ---

def _ok_response_with_warnings(warnings):
    return {
        "answer": "x",
        "context_string": "x",
        "retrieved_entities": [
            {"id": "drawer_x", "type": "drawer", "wing": "w",
             "room": "r", "content_snippet": "x"}
        ],
        "retrieved_edges": [],
        "error": None,
        "warnings": warnings,
    }


def test_query_soft_warnings_become_warn_prefix(fake_urlopen_factory):
    fake_urlopen_factory({
        EVAL_ROUTE: _ok_response_with_warnings(["low_confidence", "filtered_null_text_1"])
    })
    result = FamiliarAdapter().query("x")
    assert result.error is not None
    assert "WARN" in result.error
    assert "low_confidence" in result.error
    assert "filtered_null_text_1" in result.error
    assert len(result.retrieved_entities) == 1  # data still flows


def test_query_palace_unreachable_in_warnings(fake_urlopen_factory):
    fake_urlopen_factory({
        EVAL_ROUTE: _ok_response_with_warnings(["palace_unreachable", "low_confidence"])
    })
    result = FamiliarAdapter().query("x")
    assert "palace_unreachable" in (result.error or "")
    assert "WARN" in (result.error or "")


def test_query_no_warnings_no_error(fake_urlopen_factory):
    fake_urlopen_factory({EVAL_ROUTE: _ok_response_with_warnings([])})
    result = FamiliarAdapter().query("x")
    assert result.error is None


def test_query_server_error_takes_precedence(fake_urlopen_factory):
    payload = _ok_response_with_warnings(["low_confidence"])
    payload["error"] = "explicit server error"
    fake_urlopen_factory({EVAL_ROUTE: payload})
    result = FamiliarAdapter().query("x")
    assert "explicit server error" in (result.error or "")
    assert "low_confidence" in (result.error or "")
