"""Tests for sme.adapters.mempalace_daemon — HTTP-mocked, no live daemon."""

from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path

import pytest

from sme.adapters.mempalace_daemon import MemPalaceDaemonAdapter


# --- Auth resolution -------------------------------------------------


def test_auth_explicit_kwargs_win(monkeypatch, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("PALACE_API_KEY=from-file\nPALACE_DAEMON_URL=http://from-file\n")
    monkeypatch.setenv("PALACE_API_KEY", "from-env")
    monkeypatch.setenv("PALACE_DAEMON_URL", "http://from-env")

    a = MemPalaceDaemonAdapter(
        api_url="http://explicit",
        api_key="explicit-key",
        env_file=env_file,
    )
    assert a.api_url == "http://explicit"
    assert a.api_key == "explicit-key"


def test_auth_env_file_used_when_no_kwargs(monkeypatch, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text(
        'PALACE_API_KEY="from-file"\nPALACE_DAEMON_URL=http://from-file:8085\n'
    )
    monkeypatch.delenv("PALACE_API_KEY", raising=False)
    monkeypatch.delenv("PALACE_DAEMON_URL", raising=False)

    a = MemPalaceDaemonAdapter(env_file=env_file)
    assert a.api_url == "http://from-file:8085"
    assert a.api_key == "from-file"


def test_auth_process_env_used_when_env_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PALACE_API_KEY", "from-env")
    monkeypatch.setenv("PALACE_DAEMON_URL", "http://from-env:8085")

    a = MemPalaceDaemonAdapter(env_file=tmp_path / "does-not-exist")
    assert a.api_url == "http://from-env:8085"
    assert a.api_key == "from-env"


def test_auth_raises_when_nothing_resolves(monkeypatch, tmp_path):
    monkeypatch.delenv("PALACE_API_KEY", raising=False)
    monkeypatch.delenv("PALACE_DAEMON_URL", raising=False)

    with pytest.raises(ValueError, match="api_url"):
        MemPalaceDaemonAdapter(env_file=tmp_path / "nope")


def test_auth_url_trailing_slash_is_stripped(monkeypatch, tmp_path):
    monkeypatch.delenv("PALACE_API_KEY", raising=False)
    monkeypatch.delenv("PALACE_DAEMON_URL", raising=False)
    a = MemPalaceDaemonAdapter(
        api_url="http://example/",
        api_key="k",
        env_file=tmp_path / "nope",
    )
    assert a.api_url == "http://example"


# --- query() ---------------------------------------------------------


_OK_ENVELOPE = {
    "query": "memory",
    "filters": {"wing": None, "room": None},
    "total_before_filter": 3,
    "available_in_scope": 150811,
    "warnings": [],
    "results": [
        {
            "text": "first chunk text",
            "metadata": {
                "wing": "memorypalace",
                "room": "architecture",
                "source_file": "/path/to/notes.md",
            },
            "score": 0.91,
        },
        {
            "text": "second chunk",
            "metadata": {
                "wing": "memorypalace",
                "room": "diary",
                "source_file": "/path/to/diary.md",
            },
            "score": 0.84,
        },
    ],
}


def _adapter(monkeypatch, tmp_path, **kwargs):
    monkeypatch.delenv("PALACE_API_KEY", raising=False)
    monkeypatch.delenv("PALACE_DAEMON_URL", raising=False)
    defaults = dict(
        api_url="http://daemon",
        api_key="key",
        env_file=tmp_path / "no-env",
    )
    defaults.update(kwargs)
    return MemPalaceDaemonAdapter(**defaults)


def test_query_success_builds_context_string(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": _OK_ENVELOPE,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    assert result.error is None
    assert "[1] [memorypalace/architecture]" in result.context_string
    assert "first chunk text" in result.context_string
    assert "[2] [memorypalace/diary]" in result.context_string
    assert "second chunk" in result.context_string
    # Source filename basenames, not full paths
    assert "notes.md" in result.context_string
    assert "/path/to/notes.md" not in result.context_string


def test_query_retrieved_entities_have_wing_room_score(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": _OK_ENVELOPE,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    assert len(result.retrieved_entities) == 2
    e0 = result.retrieved_entities[0]
    assert e0.entity_type == "drawer:architecture"
    assert e0.properties["wing"] == "memorypalace"
    assert e0.properties["room"] == "architecture"
    assert e0.properties["score"] == 0.91


def test_query_retrieval_path_includes_kind_and_counts(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": _OK_ENVELOPE,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    path_str = "; ".join(result.retrieval_path)
    assert "kind=content" in path_str
    assert "available_in_scope=150811" in path_str
    assert "total_before_filter=3" in path_str


def test_query_kind_kwarg_overrides_default(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=all": _OK_ENVELOPE,
    })
    a = _adapter(monkeypatch, tmp_path)  # kind defaults to "content"
    result = a.query("memory", kind="all")
    assert "kind=all" in "; ".join(result.retrieval_path)


def test_query_n_results_threads_through_to_limit(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=12&kind=content": _OK_ENVELOPE,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory", n_results=12)
    assert result.error is None  # would AssertionError in fake_urlopen otherwise


def test_query_question_is_url_quoted(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        # spaces and ampersands must be quoted in the URL
        "GET http://daemon/search?q=hello+world+%26+more&limit=5&kind=content": _OK_ENVELOPE,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("hello world & more")
    assert result.error is None


# --- query() error paths --------------------------------------------


def test_query_warnings_emit_soft_error_with_results(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    envelope = {
        **_OK_ENVELOPE,
        "warnings": ["vector search unavailable: Error finding id"],
    }
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": envelope,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    # Soft signal: error set, but context_string still populated
    assert result.error is not None
    assert result.error.startswith("WARN:")
    assert "vector search unavailable" in result.error
    assert "first chunk text" in result.context_string


def test_query_warnings_with_empty_results(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    envelope = {
        "query": "memory",
        "filters": {"wing": None, "room": None},
        "total_before_filter": 0,
        "available_in_scope": 150811,
        "warnings": ["vector search unavailable: Error finding id"],
        "results": [],
    }
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": envelope,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    assert result.error.startswith("WARN:")
    assert result.context_string == ""


def test_query_no_results_returns_no_results(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    envelope = {**_OK_ENVELOPE, "results": [], "warnings": []}
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": envelope,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    assert result.error == "NO_RESULTS"


def test_query_auth_error_returns_AUTH(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    err = urllib.error.HTTPError(
        "http://daemon/search", 401, "Unauthorized", {}, None
    )
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": err,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    assert result.error.startswith("AUTH:")
    assert "401" in result.error


def test_query_5xx_returns_HTTP_error(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    err = urllib.error.HTTPError(
        "http://daemon/search", 500, "Server Error", {}, None
    )
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": err,
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    assert result.error.startswith("HTTP 500")


def test_query_connection_refused_returns_CONNECTION(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": (
            urllib.error.URLError("Connection refused")
        ),
    })
    a = _adapter(monkeypatch, tmp_path)
    result = a.query("memory")
    assert result.error.startswith("CONNECTION:")


def test_query_sends_x_api_key_header(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    captured = {}

    def capture(req):
        captured["headers"] = dict(req.header_items())
        captured["url"] = req.full_url
        return _OK_ENVELOPE  # factory will wrap into a _FakeResponse

    fake_urlopen_factory({
        "GET http://daemon/search?q=memory&limit=5&kind=content": capture,
    })
    a = _adapter(monkeypatch, tmp_path, api_key="my-secret")
    a.query("memory")
    # urllib normalises header names; check both casings
    api_key_value = (
        captured["headers"].get("X-api-key")
        or captured["headers"].get("X-Api-Key")
    )
    assert api_key_value == "my-secret"


# --- get_graph_snapshot — /graph fast path --------------------------


_GRAPH_RESPONSE = {
    "wings": {
        "memorypalace": 427,
        "projects": 106183,
        "umbra": 82,
    },
    "rooms": [
        {"wing": "memorypalace", "rooms": {"architecture": 17, "diary": 235}},
        {"wing": "projects", "rooms": {"architecture": 9, "general": 100}},
        {"wing": "umbra", "rooms": {"diary": 12}},
    ],
    "tunnels": [
        {"room": "architecture", "wings": ["memorypalace", "projects"]},
        {"room": "diary", "wings": ["memorypalace", "umbra"]},
    ],
    "kg_entities": [
        {"id": "e1", "name": "Multipass", "type": "concept", "properties": {}}
    ],
    "kg_triples": [
        {
            "subject": "e1",
            "predicate": "described_by",
            "object": "e1",
            "valid_from": "2026-04-25",
            "valid_to": None,
            "confidence": 1.0,
            "source_file": "README.md",
        }
    ],
    "kg_stats": {"entities": 1, "triples": 1},
}


def test_snapshot_graph_endpoint_creates_wing_entities(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/graph": _GRAPH_RESPONSE,
    })
    a = _adapter(monkeypatch, tmp_path)
    entities, edges = a.get_graph_snapshot()

    wing_entities = [e for e in entities if e.entity_type == "wing"]
    assert {e.name for e in wing_entities} == {"memorypalace", "projects", "umbra"}


def test_snapshot_graph_endpoint_creates_room_entities_with_wings(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/graph": _GRAPH_RESPONSE,
    })
    a = _adapter(monkeypatch, tmp_path)
    entities, _ = a.get_graph_snapshot()

    rooms_by_name = {e.name: e for e in entities if e.id.startswith("room:")}
    assert "architecture" in rooms_by_name
    assert sorted(rooms_by_name["architecture"].properties["wings"]) == [
        "memorypalace",
        "projects",
    ]
    # 'general' is a catch-all and should be skipped, mirroring the
    # existing direct adapter's filter.
    assert "general" not in rooms_by_name


def test_snapshot_graph_endpoint_member_of_edges(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/graph": _GRAPH_RESPONSE,
    })
    a = _adapter(monkeypatch, tmp_path)
    _, edges = a.get_graph_snapshot()

    member_of = [e for e in edges if e.edge_type == "member_of"]
    pairs = {(e.source_id, e.target_id) for e in member_of}
    assert ("room:architecture", "wing:memorypalace") in pairs
    assert ("room:architecture", "wing:projects") in pairs
    assert ("room:diary", "wing:memorypalace") in pairs


def test_snapshot_graph_endpoint_tunnel_edges(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/graph": _GRAPH_RESPONSE,
    })
    a = _adapter(monkeypatch, tmp_path)
    _, edges = a.get_graph_snapshot()
    tunnels = [e for e in edges if e.edge_type == "tunnel"]
    pairs = {
        tuple(sorted([e.source_id, e.target_id]))
        for e in tunnels
    }
    # architecture connects memorypalace<->projects
    assert ("wing:memorypalace", "wing:projects") in pairs
    # diary connects memorypalace<->umbra
    assert ("wing:memorypalace", "wing:umbra") in pairs


def test_snapshot_graph_endpoint_kg_entities_and_triples(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/graph": _GRAPH_RESPONSE,
    })
    a = _adapter(monkeypatch, tmp_path)
    entities, edges = a.get_graph_snapshot()
    kg_ents = [e for e in entities if e.id.startswith("kg:")]
    assert len(kg_ents) == 1
    assert kg_ents[0].name == "Multipass"

    kg_edges = [e for e in edges if e.source_id.startswith("kg:")]
    assert len(kg_edges) == 1
    assert kg_edges[0].edge_type == "described_by"


# --- get_graph_snapshot — MCP fallback ------------------------------


def _mcp_envelope(payload) -> dict:
    """Build an MCP tools/call response envelope wrapping a JSON payload."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }


def _mcp_request_router(routes_by_tool: dict):
    """Returns a callable that fake_urlopen_factory can hand back as the
    response for ``POST http://daemon/mcp``.

    Inspects the request body to dispatch on (tool_name, arguments) and
    returns the matching MCP envelope. Unknown tools raise AssertionError.
    """
    def _route(req, *, _routes=routes_by_tool):
        body = req.data
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        rpc = json.loads(body)
        params = rpc.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        # Per-wing list_rooms: key on tool:wing
        if name == "mempalace_list_rooms":
            key = f"mempalace_list_rooms:{args.get('wing')}"
        else:
            key = name
        if key not in _routes:
            raise AssertionError(f"unrouted MCP call: {key}")
        result = _routes[key]
        if isinstance(result, Exception):
            raise result
        return _mcp_envelope(result)
    return _route


def test_snapshot_falls_back_to_mcp_on_404(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "GET http://daemon/graph": (
            urllib.error.HTTPError(
                "http://daemon/graph", 404, "Not Found", {}, None
            )
        ),
        "POST http://daemon/mcp": _mcp_request_router({
            "mempalace_list_wings": {
                "wings": {"memorypalace": 427, "umbra": 82}
            },
            "mempalace_list_tunnels": [
                {"room": "diary", "wings": ["memorypalace", "umbra"]}
            ],
            "mempalace_list_rooms:memorypalace": {
                "wing": "memorypalace",
                "rooms": {"diary": 235, "architecture": 17},
            },
            "mempalace_list_rooms:umbra": {
                "wing": "umbra",
                "rooms": {"diary": 12},
            },
        }),
    })
    a = _adapter(monkeypatch, tmp_path)
    entities, edges = a.get_graph_snapshot()
    wing_names = {e.name for e in entities if e.entity_type == "wing"}
    assert wing_names == {"memorypalace", "umbra"}
    tunnels = [e for e in edges if e.edge_type == "tunnel"]
    assert len(tunnels) == 1
    pair = tuple(sorted([tunnels[0].source_id, tunnels[0].target_id]))
    assert pair == ("wing:memorypalace", "wing:umbra")


def test_snapshot_force_mcp_with_prefer_graph_false(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    fake_urlopen_factory({
        "POST http://daemon/mcp": _mcp_request_router({
            "mempalace_list_wings": {"wings": {"only": 1}},
            "mempalace_list_tunnels": [],
            "mempalace_list_rooms:only": {"wing": "only", "rooms": {}},
        }),
    })
    a = _adapter(
        monkeypatch, tmp_path, prefer_graph_endpoint=False
    )
    entities, _ = a.get_graph_snapshot()
    # Should NOT have hit /graph at all (no route registered for it)
    wing_names = {e.name for e in entities if e.entity_type == "wing"}
    assert wing_names == {"only"}


def test_snapshot_partial_on_list_rooms_failure(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    """If list_rooms fails for one wing, the snapshot still returns
    every other wing's data."""
    fake_urlopen_factory({
        "GET http://daemon/graph": urllib.error.HTTPError(
            "http://daemon/graph", 404, "Not Found", {}, None
        ),
        "POST http://daemon/mcp": _mcp_request_router({
            "mempalace_list_wings": {"wings": {"good": 1, "bad": 1}},
            "mempalace_list_tunnels": [],
            "mempalace_list_rooms:good": {"wing": "good", "rooms": {"r1": 5}},
            # 'bad' wing's list_rooms raises
            "mempalace_list_rooms:bad": urllib.error.HTTPError(
                "http://daemon/mcp", 500, "tool error", {}, None
            ),
        }),
    })
    a = _adapter(monkeypatch, tmp_path)
    entities, _ = a.get_graph_snapshot()
    room_names = {e.name for e in entities if e.id.startswith("room:")}
    assert "r1" in room_names  # the good wing's room is present
