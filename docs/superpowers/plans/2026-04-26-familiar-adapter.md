# FamiliarAdapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fifth `SMEAdapter` to multipass — `FamiliarAdapter` — that talks to a running familiar.realm.watch v0.2.0+ instance via HTTP, so SME can score the v0.2 retrieval pipeline (rerank/decay/compress/grounding) against curated test corpora.

**Architecture:** HTTP wrapper around `POST /api/familiar/eval` (which already returns SME-shape) and `GET /api/familiar/graph` (which proxies palace-daemon's `/graph`). Defaults to `mock=true` for Cat 1 determinism. Graph-snapshot mapping is shared with `MemPalaceDaemonAdapter` via a small extracted helper module.

**Tech Stack:** Python 3.12+, stdlib `urllib.request` for HTTP (matches `MemPalaceDaemonAdapter` convention — no httpx), pytest, pytest's `monkeypatch` + the existing `fake_urlopen_factory` fixture in `tests/conftest.py`.

---

## File Structure

| Action | Path | Purpose |
|---|---|---|
| Create | `sme/adapters/_graph_mapping.py` | Shared `/graph` JSON to `(Entity, Edge)` mapping helpers, extracted from `mempalace_daemon.py` |
| Create | `sme/adapters/familiar.py` | The `FamiliarAdapter` class (~400 lines) |
| Create | `tests/test_familiar_adapter.py` | Unit tests with mocked HTTP via `fake_urlopen_factory` |
| Create | `tests/test_familiar_live.py` | Gated live smoke test (skipped unless `FAMILIAR_BASE_URL` env set) |
| Modify | `sme/adapters/mempalace_daemon.py` | Replace inlined `_project_graph` with shared module import |
| Modify | `sme/cli.py` | Wire `--adapter familiar` plus `--mock`/`--no-mock` flags |
| Modify | `README.md` | Adapter table row + Quickstart subsection for familiar |
| Modify | `docs/ideas.md` | Note that familiar's per-question records prepare for future Cat 9 |

---

## Task 1: Extract `/graph` mapping into shared module

**Files:**
- Create: `sme/adapters/_graph_mapping.py`
- Modify: `sme/adapters/mempalace_daemon.py:244-364` (replace `_project_graph`)
- Test: `tests/test_mempalace_daemon_adapter.py` (re-run unchanged, must still pass)

- [ ] **Step 1: Read the existing `_project_graph` to understand the contract**

Run: `sed -n '244,364p' sme/adapters/mempalace_daemon.py`
Expected: a method that takes a dict (the `/graph` body) and returns `tuple[list[Entity], list[Edge]]`.

- [ ] **Step 2: Create the shared module**

Create `sme/adapters/_graph_mapping.py`:

```python
"""Shared /graph payload to (Entity, Edge) mapping.

palace-daemon's GET /graph returns a single payload shape (wings,
rooms, tunnels, kg_entities, kg_triples, kg_stats). Both
MemPalaceDaemonAdapter and FamiliarAdapter consume this shape.
Familiar's GET /api/familiar/graph proxies the daemon's response
unchanged (with a 5-minute cache), so both can use the same mapping.

Extracted from MemPalaceDaemonAdapter._project_graph 2026-04-26.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sme.adapters.base import Edge, Entity


def project_graph(body: dict[str, Any]) -> tuple[list[Entity], list[Edge]]:
    """Map a /graph JSON body to lists of Entity and Edge.

    Mirrors what MemPalaceAdapter.get_graph_snapshot produces from
    direct ChromaDB access, at the coarser-than-drawer granularity
    the daemon's /graph endpoint exposes.
    """
    wings: dict[str, int] = body.get("wings") or {}
    rooms_per_wing: list[dict] = body.get("rooms") or []
    tunnels: list[dict] = body.get("tunnels") or []
    kg_ents: list[dict] = body.get("kg_entities") or []
    kg_triples: list[dict] = body.get("kg_triples") or []

    entities: list[Entity] = []
    edges: list[Edge] = []

    # Wings
    for wing in sorted(wings):
        entities.append(
            Entity(
                id=f"wing:{wing}",
                name=wing,
                entity_type="wing",
                properties={"_table": "wing", "drawer_count": wings[wing]},
            )
        )

    # Rooms — collect wings-per-room across the per-wing lists
    room_wings: dict[str, set[str]] = defaultdict(set)
    for entry in rooms_per_wing:
        wing = entry.get("wing")
        if not wing:
            continue
        for room in (entry.get("rooms") or {}):
            room_wings[room].add(wing)
    for room in sorted(room_wings):
        wings_list = sorted(room_wings[room])
        entities.append(
            Entity(
                id=f"room:{room}",
                name=room,
                entity_type="room",
                properties={
                    "_table": "room",
                    "wings": wings_list,
                },
            )
        )
        for wing in wings_list:
            edges.append(
                Edge(
                    source_id=f"wing:{wing}",
                    target_id=f"room:{room}",
                    edge_type="contains_room",
                )
            )

    # Tunnels — cross-wing topic edges
    for tunnel in tunnels:
        room = tunnel.get("room")
        wings_in = tunnel.get("wings") or []
        if not room or len(wings_in) < 2:
            continue
        # tunnel is a clique among the wings via the shared room
        for i, wa in enumerate(wings_in):
            for wb in wings_in[i + 1:]:
                edges.append(
                    Edge(
                        source_id=f"wing:{wa}",
                        target_id=f"wing:{wb}",
                        edge_type="topic_tunnel",
                        properties={"shared_room": room},
                    )
                )

    # KG entities
    for ent in kg_ents:
        eid = ent.get("id")
        if not eid:
            continue
        entities.append(
            Entity(
                id=f"kg:{eid}",
                name=ent.get("name") or eid,
                entity_type=ent.get("type") or "kg_entity",
                properties={
                    "_table": "kg_entity",
                    **(ent.get("properties") or {}),
                },
            )
        )

    # KG triples
    for triple in kg_triples:
        s = triple.get("subject")
        o = triple.get("object")
        p = triple.get("predicate")
        if not (s and o and p):
            continue
        props: dict[str, Any] = {}
        for key in ("valid_from", "valid_to", "confidence", "source_file"):
            if triple.get(key) is not None:
                props[key] = triple[key]
        edges.append(
            Edge(
                source_id=f"kg:{s}",
                target_id=f"kg:{o}",
                edge_type=p,
                properties=props,
            )
        )

    return entities, edges
```

- [ ] **Step 3: Update `mempalace_daemon.py` to use the shared module**

In `sme/adapters/mempalace_daemon.py`:
- Add import at the top: `from sme.adapters._graph_mapping import project_graph`
- Replace the body of `_project_graph(self, body: dict)` with:

```python
def _project_graph(self, body: dict) -> tuple[list[Entity], list[Edge]]:
    """Map /graph payload to (Entity, Edge). Delegates to shared module."""
    return project_graph(body)
```

- [ ] **Step 4: Run mempalace_daemon tests to confirm refactor is non-breaking**

Run: `pytest tests/test_mempalace_daemon_adapter.py -v`
Expected: all pre-existing tests pass unchanged.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/_graph_mapping.py sme/adapters/mempalace_daemon.py
git commit -m "refactor(adapters): extract /graph payload mapping into shared module

Both MemPalaceDaemonAdapter and the upcoming FamiliarAdapter consume
the same /graph payload shape (familiar's /api/familiar/graph is a
verbatim proxy of palace-daemon's /graph). Extract project_graph into
sme/adapters/_graph_mapping.py so both adapters share the implementation
and stay in lock-step if the upstream shape evolves.

Existing mempalace_daemon tests pass unchanged."
```

---

## Task 2: Scaffold `FamiliarAdapter` class skeleton

**Files:**
- Create: `sme/adapters/familiar.py`
- Test: `tests/test_familiar_adapter.py`

- [ ] **Step 1: Write failing test for instantiation defaults**

Create `tests/test_familiar_adapter.py`:

```python
"""Unit tests for FamiliarAdapter."""

from __future__ import annotations

import json
import pytest

from sme.adapters.familiar import FamiliarAdapter


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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_familiar_adapter.py::test_default_construction -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sme.adapters.familiar'`.

- [ ] **Step 3: Create the adapter skeleton**

Create `sme/adapters/familiar.py`:

```python
"""FamiliarAdapter — SME adapter for familiar.realm.watch v0.2.0+.

Familiar wraps palace-daemon with a v0.2 retrieval pipeline (rerank,
temporal decay, extractive compression, grounding directives). This
adapter measures familiar's full pipeline; the sibling
MemPalaceDaemonAdapter measures palace alone. Comparing their SME
scores quantifies what familiar's v0.2 contributes.

POST /api/familiar/eval already returns SME-QueryResult shape natively
(familiar's chunk-C of v0.2 was designed against this contract), so the
adapter is mostly deserialization with error/warning translation rules.
GET /api/familiar/graph proxies palace-daemon's /graph; reuse the
shared mapping module.

Defaults to mock_inference=True so Cat 1 substring scoring stays
deterministic — no LLM in the loop. Inference-mode runs are reserved
for a future Cat 9 pass.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter


DEFAULT_BASE_URL = "http://familiar:8080"
DEFAULT_TIMEOUT_S = 30.0


class FamiliarAdapter(SMEAdapter):
    """Adapter for a running familiar.realm.watch v0.2.0+ instance."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        mock_inference: bool = True,
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.mock_inference = mock_inference
        # `opener` is injected by tests via fake_urlopen_factory; production
        # code uses urllib.request.urlopen directly.
        self._opener = opener

    # --- Required SMEAdapter methods (filled in by later tasks) ---

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError("Task 3")

    def query(self, question: str) -> QueryResult:
        raise NotImplementedError("Task 4-7")

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        raise NotImplementedError("Task 8")
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_familiar_adapter.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/familiar.py tests/test_familiar_adapter.py
git commit -m "feat(adapters): scaffold FamiliarAdapter skeleton

Class structure + constructor + base URL trim. Methods stub out to
NotImplementedError; subsequent tasks fill them in. Mirrors the
MemPalaceDaemonAdapter constructor shape (base_url, timeout_s, opener
for test injection)."
```

---

## Task 3: Implement `ingest_corpus` as no-op stub

**Files:**
- Modify: `sme/adapters/familiar.py`
- Test: `tests/test_familiar_adapter.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_familiar_adapter.py`:

```python
def test_ingest_corpus_is_noop():
    adapter = FamiliarAdapter()
    result = adapter.ingest_corpus([{"id": "doc-1", "text": "anything"}])
    assert result["entities_created"] == 0
    assert result["edges_created"] == 0
    assert result["errors"] == []
    assert any("diagnostic-only" in w.lower() or "no-op" in w.lower()
               for w in result["warnings"])
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_familiar_adapter.py::test_ingest_corpus_is_noop -v`
Expected: FAIL with `NotImplementedError: Task 3`.

- [ ] **Step 3: Implement the stub**

In `sme/adapters/familiar.py`, replace the `ingest_corpus` body:

```python
def ingest_corpus(self, corpus: list[dict]) -> dict:
    """No-op stub. Familiar reads palace data it didn't author;
    ingestion happens upstream via `mempalace mine`."""
    return {
        "entities_created": 0,
        "edges_created": 0,
        "errors": [],
        "warnings": [
            "FamiliarAdapter is diagnostic-only (Mode B). Familiar reads "
            "palace data it didn't author; ingestion happens upstream via "
            "`mempalace mine`. ingest_corpus is a no-op."
        ],
    }
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_familiar_adapter.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/familiar.py tests/test_familiar_adapter.py
git commit -m "feat(adapters): FamiliarAdapter.ingest_corpus no-op stub

Mode B (diagnostic-only) — same pattern as MemPalaceDaemonAdapter."
```

---

## Task 4: Implement `query()` happy path (mock=true success)

**Files:**
- Modify: `sme/adapters/familiar.py` (add `_post_json` helper + `query`)
- Test: `tests/test_familiar_adapter.py`

- [ ] **Step 1: Write failing test using `fake_urlopen_factory`**

Append to `tests/test_familiar_adapter.py`:

```python
def test_query_happy_path(fake_urlopen_factory):
    """Mocked POST /api/familiar/eval returns SME-shape JSON.
    Adapter deserializes into a QueryResult with all fields populated."""
    response_body = {
        "answer": "(mock=true: inference skipped)",
        "context_string": "── Palace context (1 drawer) ──\n[drawer_abc · wing=projects · room=technical]\nUser enjoys hiking.",
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
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval": (200, response_body),
    })
    adapter = FamiliarAdapter(opener=fake)

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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_familiar_adapter.py::test_query_happy_path -v`
Expected: FAIL with `NotImplementedError: Task 4-7`.

- [ ] **Step 3: Implement `query()` and `_post_json` helper**

In `sme/adapters/familiar.py`, add at the top:

```python
import json
import urllib.error
import urllib.request
```

Add a private HTTP helper inside the class:

```python
def _post_json(self, path: str, body: dict) -> tuple[int, Any]:
    """POST JSON, return (status, parsed_body). Raises only on
    network/JSON failure; HTTP non-2xx is returned as a status tuple
    for the caller to translate into an SME error."""
    url = f"{self.base_url}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    opener = self._opener or urllib.request.urlopen
    try:
        with opener(req, timeout=self.timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status if hasattr(resp, "status") else resp.getcode()
            return status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        # Non-2xx with a body — return status + best-effort body.
        try:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"_raw": raw[:200]}
        except Exception:
            return e.code, {"_raw": ""}
```

Replace `query` body:

```python
def query(self, question: str) -> QueryResult:
    """POST /api/familiar/eval and deserialize the SME-shape response."""
    body = {
        "query": question[:250],
        "limit": 5,
        "kind": "content",
        "mock": self.mock_inference,
    }
    status, payload = self._post_json("/api/familiar/eval", body)
    if status != 200:
        snippet = json.dumps(payload)[:200] if isinstance(payload, dict) else str(payload)[:200]
        return QueryResult(
            answer="",
            context_string="",
            retrieved_entities=[],
            retrieved_edges=[],
            error=f"familiar endpoint {status}: {snippet}",
        )
    return self._deserialize_query(payload)


def _deserialize_query(self, payload: dict) -> QueryResult:
    """Map familiar's JSON response onto SME QueryResult."""
    answer = payload.get("answer") or ""
    context_string = payload.get("context_string") or ""
    raw_entities = payload.get("retrieved_entities") or []
    raw_edges = payload.get("retrieved_edges") or []
    server_error = payload.get("error")
    warnings = payload.get("warnings") or []

    entities = [self._entity_from_payload(e) for e in raw_entities]
    edges = [self._edge_from_payload(e) for e in raw_edges]

    error = server_error
    # warnings translation rules land in Task 7

    return QueryResult(
        answer=answer,
        context_string=context_string,
        retrieved_entities=entities,
        retrieved_edges=edges,
        error=error,
    )


@staticmethod
def _entity_from_payload(p: dict) -> Entity:
    """Map a familiar SmeEntity dict to an SME Entity dataclass."""
    eid = p.get("id") or ""
    return Entity(
        id=eid,
        name=eid,
        entity_type=p.get("type") or "drawer",
        properties={
            k: v
            for k, v in p.items()
            if k not in ("id", "type") and v is not None
        },
    )


@staticmethod
def _edge_from_payload(p: dict) -> Edge:
    return Edge(
        source_id=p.get("subject") or "",
        target_id=p.get("object") or "",
        edge_type=p.get("predicate") or "",
    )
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_familiar_adapter.py::test_query_happy_path -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/familiar.py tests/test_familiar_adapter.py
git commit -m "feat(adapters): FamiliarAdapter.query happy path

POSTs to /api/familiar/eval, deserializes the SME-shape response into
QueryResult. mock_inference=True forwarded as 'mock' field so Cat 1
scoring stays deterministic. _post_json helper handles HTTPError into
status-tuple translation for non-throwing error contract."
```

---

## Task 5: HTTP error contract (4xx, 5xx, network, JSON-malformed)

**Files:**
- Modify: `sme/adapters/familiar.py` (extend `_post_json`)
- Test: `tests/test_familiar_adapter.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_familiar_adapter.py`:

```python
import socket
import urllib.error


def test_query_http_500(fake_urlopen_factory):
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval": (500, {"error": "internal"}),
    })
    adapter = FamiliarAdapter(opener=fake)
    result = adapter.query("anything")
    assert result.error is not None
    assert "500" in result.error
    assert result.retrieved_entities == []


def test_query_http_400(fake_urlopen_factory):
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval": (400, {"error": "bad json"}),
    })
    adapter = FamiliarAdapter(opener=fake)
    result = adapter.query("anything")
    assert "400" in (result.error or "")


def test_query_timeout(monkeypatch):
    def raising_opener(*a, **kw):
        raise socket.timeout("boom")
    adapter = FamiliarAdapter(opener=raising_opener, timeout_s=2.0)
    result = adapter.query("anything")
    assert result.error is not None
    assert "timeout" in result.error.lower() or "boom" in result.error


def test_query_connection_refused(monkeypatch):
    def raising_opener(*a, **kw):
        raise urllib.error.URLError("Connection refused")
    adapter = FamiliarAdapter(opener=raising_opener)
    result = adapter.query("anything")
    assert result.error is not None
    assert "connection" in result.error.lower() or "refused" in result.error.lower()


def test_query_invalid_json(fake_urlopen_factory):
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval": (200, "not json at all"),
    })
    adapter = FamiliarAdapter(opener=fake)
    result = adapter.query("anything")
    assert result.error is not None
    assert "json" in result.error.lower()
```

- [ ] **Step 2: Run, observe failures (timeout/connection/JSON propagate raw)**

Run: `pytest tests/test_familiar_adapter.py -v -k "http_500 or http_400 or timeout or connection or invalid_json"`
Expected: 3-4 failures (the 4xx/5xx cases pass already from Task 4; timeout/connection/json propagate as exceptions).

- [ ] **Step 3: Extend `_post_json` to catch network + JSON errors**

In `sme/adapters/familiar.py`, replace `_post_json` body's `try`/`except` chain:

```python
def _post_json(self, path: str, body: dict) -> tuple[int, Any]:
    """POST JSON, return (status, parsed_body). Translates network and
    JSON-decode failures into a sentinel (-1 status, error-bearing dict)
    so the adapter's error contract stays no-raise."""
    url = f"{self.base_url}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    opener = self._opener or urllib.request.urlopen
    try:
        with opener(req, timeout=self.timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status if hasattr(resp, "status") else resp.getcode()
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError as e:
                return -1, {"_network_error": f"invalid JSON response: {e}"}
            return status, parsed
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"_raw": raw[:200]}
        except Exception:
            return e.code, {"_raw": ""}
    except (socket.timeout, TimeoutError) as e:
        return -1, {"_network_error": f"timeout after {self.timeout_s}s ({e})"}
    except urllib.error.URLError as e:
        return -1, {"_network_error": f"connection failed: {e.reason}"}
    except Exception as e:
        return -1, {"_network_error": f"unexpected: {type(e).__name__}: {e}"}
```

Add at the top of the file with the other imports:
```python
import socket
```

Then update `query()` to handle the `-1` sentinel:

```python
def query(self, question: str) -> QueryResult:
    body = {
        "query": question[:250],
        "limit": 5,
        "kind": "content",
        "mock": self.mock_inference,
    }
    status, payload = self._post_json("/api/familiar/eval", body)
    if status == -1:
        # Network/JSON failure — payload carries the message
        msg = payload.get("_network_error", "unknown network error")
        return QueryResult(
            answer="",
            context_string="",
            retrieved_entities=[],
            retrieved_edges=[],
            error=f"familiar {msg}",
        )
    if status != 200:
        snippet = json.dumps(payload)[:200] if isinstance(payload, dict) else str(payload)[:200]
        return QueryResult(
            answer="",
            context_string="",
            retrieved_entities=[],
            retrieved_edges=[],
            error=f"familiar endpoint {status}: {snippet}",
        )
    return self._deserialize_query(payload)
```

- [ ] **Step 4: Run all error tests, verify pass**

Run: `pytest tests/test_familiar_adapter.py -v`
Expected: 9 passed (3 from Task 1, 1 from Task 3, 1 from Task 4, 5 new error tests).

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/familiar.py tests/test_familiar_adapter.py
git commit -m "feat(adapters): FamiliarAdapter HTTP/network error contract

Returns QueryResult with error string for HTTPError, socket.timeout,
URLError, and JSONDecodeError. Never raises; matches the SMEAdapter
no-throw contract used by cmd_retrieve to distinguish 'errored' from
'answered wrong' in the per-question scorecard."
```

---

## Task 6: Warnings translation (soft + hard signals)

**Files:**
- Modify: `sme/adapters/familiar.py:_deserialize_query`
- Test: `tests/test_familiar_adapter.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_familiar_adapter.py`:

```python
def _ok_response_with_warnings(warnings):
    return {
        "answer": "x",
        "context_string": "x",
        "retrieved_entities": [
            {
                "id": "drawer_x",
                "type": "drawer",
                "wing": "w",
                "room": "r",
                "content_snippet": "x",
            }
        ],
        "retrieved_edges": [],
        "error": None,
        "warnings": warnings,
    }


def test_query_soft_warnings_become_warn_prefix(fake_urlopen_factory):
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval":
            (200, _ok_response_with_warnings(["low_confidence", "filtered_null_text_1"])),
    })
    adapter = FamiliarAdapter(opener=fake)
    result = adapter.query("x")
    # Soft warnings: error gets a WARN prefix but data still flows
    assert result.error is not None
    assert "WARN" in result.error
    assert "low_confidence" in result.error
    assert "filtered_null_text_1" in result.error
    assert len(result.retrieved_entities) == 1  # not zeroed out


def test_query_palace_unreachable_is_hard_warning(fake_urlopen_factory):
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval":
            (200, _ok_response_with_warnings(["palace_unreachable", "low_confidence"])),
    })
    adapter = FamiliarAdapter(opener=fake)
    result = adapter.query("x")
    assert result.error is not None
    assert "palace_unreachable" in result.error
    assert "WARN" in result.error


def test_query_no_warnings_no_error(fake_urlopen_factory):
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval":
            (200, _ok_response_with_warnings([])),
    })
    adapter = FamiliarAdapter(opener=fake)
    result = adapter.query("x")
    assert result.error is None


def test_query_server_error_takes_precedence(fake_urlopen_factory):
    payload = _ok_response_with_warnings(["low_confidence"])
    payload["error"] = "explicit server error"
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval": (200, payload),
    })
    adapter = FamiliarAdapter(opener=fake)
    result = adapter.query("x")
    # When server says error, that's authoritative — warnings appended
    assert "explicit server error" in (result.error or "")
```

- [ ] **Step 2: Run, observe failures**

Run: `pytest tests/test_familiar_adapter.py -v -k "warning or unreachable or no_warnings or server_error"`
Expected: 4 failures (Task 4's `_deserialize_query` doesn't yet translate warnings).

- [ ] **Step 3: Implement warnings translation**

In `sme/adapters/familiar.py`, update `_deserialize_query`:

```python
# Hard warnings — adapter-level error even though HTTP was 200.
HARD_WARNING_TOKENS = ("palace_unreachable",)


def _deserialize_query(self, payload: dict) -> QueryResult:
    """Map familiar's JSON response onto SME QueryResult."""
    answer = payload.get("answer") or ""
    context_string = payload.get("context_string") or ""
    raw_entities = payload.get("retrieved_entities") or []
    raw_edges = payload.get("retrieved_edges") or []
    server_error = payload.get("error")
    warnings = payload.get("warnings") or []

    entities = [self._entity_from_payload(e) for e in raw_entities]
    edges = [self._edge_from_payload(e) for e in raw_edges]

    parts: list[str] = []
    if server_error:
        parts.append(str(server_error))
    if warnings:
        parts.append("WARN: " + "; ".join(warnings))
    error = " | ".join(parts) if parts else None

    return QueryResult(
        answer=answer,
        context_string=context_string,
        retrieved_entities=entities,
        retrieved_edges=edges,
        error=error,
    )
```

The `HARD_WARNING_TOKENS` constant is currently informational; the
distinction between soft and hard is recorded in `error` text which
SME-side scoring already keys on for "errored" vs. "answered wrong".
Future work can use `HARD_WARNING_TOKENS` to short-circuit data
fields when the server explicitly says retrieval failed.

- [ ] **Step 4: Run all tests, verify pass**

Run: `pytest tests/test_familiar_adapter.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/familiar.py tests/test_familiar_adapter.py
git commit -m "feat(adapters): FamiliarAdapter warnings translation

Soft warnings (low_confidence, filtered_null_text_*, stuck_loop) and
hard warnings (palace_unreachable) both surface in QueryResult.error
with a WARN: prefix; entities/edges still flow so SME's per-question
scoring distinguishes 'warned but answered' from 'errored'. Server-side
'error' field takes precedence; warnings appended after the | separator."
```

---

## Task 7: `get_graph_snapshot()` via shared mapping module

**Files:**
- Modify: `sme/adapters/familiar.py`
- Test: `tests/test_familiar_adapter.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_familiar_adapter.py`:

```python
def test_get_graph_snapshot_happy_path(fake_urlopen_factory):
    body = {
        "wings": {"realmwatch": 12, "personal": 7},
        "rooms": [
            {"wing": "realmwatch", "rooms": {"gatekeeper": 5}},
            {"wing": "personal", "rooms": {"hobbies": 4}},
        ],
        "tunnels": [{"room": "tools", "wings": ["realmwatch", "personal"]}],
        "kg_entities": [
            {"id": "ent_1", "name": "JP", "type": "person", "properties": {}}
        ],
        "kg_triples": [
            {"subject": "ent_1", "predicate": "owns", "object": "ent_repo"}
        ],
        "kg_stats": {"entities": 1, "triples": 1},
    }
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/graph": (200, body),
    })
    adapter = FamiliarAdapter(opener=fake)
    entities, edges = adapter.get_graph_snapshot()

    # Each wing is an entity
    wing_ids = [e.id for e in entities if e.entity_type == "wing"]
    assert "wing:realmwatch" in wing_ids
    assert "wing:personal" in wing_ids

    # Each KG entity prefixed kg:
    kg_ids = [e.id for e in entities if e.entity_type == "person"]
    assert "kg:ent_1" in kg_ids

    # Tunnel produces a topic_tunnel edge between the two wings
    tunnel_edges = [e for e in edges if e.edge_type == "topic_tunnel"]
    assert any(
        {edge.source_id, edge.target_id} == {"wing:realmwatch", "wing:personal"}
        for edge in tunnel_edges
    )


def test_get_graph_snapshot_failure_returns_empty(fake_urlopen_factory):
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/graph": (502, {"error": "daemon down"}),
    })
    adapter = FamiliarAdapter(opener=fake)
    entities, edges = adapter.get_graph_snapshot()
    assert entities == []
    assert edges == []
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest tests/test_familiar_adapter.py::test_get_graph_snapshot_happy_path -v`
Expected: FAIL with `NotImplementedError: Task 8`.

- [ ] **Step 3: Implement `get_graph_snapshot` + `_get_json` GET helper**

In `sme/adapters/familiar.py`, add the import:
```python
from sme.adapters._graph_mapping import project_graph
```

Add a GET helper to the class:

```python
def _get_json(self, path: str) -> tuple[int, Any]:
    """GET JSON, mirror _post_json's no-raise contract."""
    url = f"{self.base_url}{path}"
    req = urllib.request.Request(url, method="GET")
    opener = self._opener or urllib.request.urlopen
    try:
        with opener(req, timeout=self.timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status if hasattr(resp, "status") else resp.getcode()
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError as e:
                return -1, {"_network_error": f"invalid JSON: {e}"}
            return status, parsed
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"_raw": raw[:200]}
        except Exception:
            return e.code, {"_raw": ""}
    except (socket.timeout, TimeoutError) as e:
        return -1, {"_network_error": f"timeout after {self.timeout_s}s ({e})"}
    except urllib.error.URLError as e:
        return -1, {"_network_error": f"connection failed: {e.reason}"}
    except Exception as e:
        return -1, {"_network_error": f"unexpected: {type(e).__name__}: {e}"}
```

Replace `get_graph_snapshot`:

```python
def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
    """GET /api/familiar/graph (familiar's proxy of palace-daemon /graph)
    and project to (entities, edges) via the shared mapping module."""
    status, body = self._get_json("/api/familiar/graph")
    if status != 200 or not isinstance(body, dict) or "wings" not in body:
        return [], []
    return project_graph(body)
```

- [ ] **Step 4: Run all tests, verify pass**

Run: `pytest tests/test_familiar_adapter.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/familiar.py tests/test_familiar_adapter.py
git commit -m "feat(adapters): FamiliarAdapter.get_graph_snapshot via shared module

GETs /api/familiar/graph (familiar's verbatim proxy of palace-daemon's
/graph with a 5-min cache layer) and runs the response through the
shared _graph_mapping.project_graph helper. Failure returns ([], []) to
keep Cat 5/8 from raising; per the SME contract a missing snapshot just
zeroes out structural-category scores for that run."
```

---

## Task 8: Optional methods — `get_flat_retrieval`, `get_ontology_source`, `get_harness_manifest`

**Files:**
- Modify: `sme/adapters/familiar.py`
- Test: `tests/test_familiar_adapter.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_familiar_adapter.py`:

```python
def test_get_flat_retrieval_returns_entities_only(fake_urlopen_factory):
    body = _ok_response_with_warnings([])
    body["retrieved_entities"] = [
        {"id": f"d{i}", "type": "drawer", "wing": "w", "room": "r"}
        for i in range(3)
    ]
    fake = fake_urlopen_factory({
        "http://familiar:8080/api/familiar/eval": (200, body),
    })
    adapter = FamiliarAdapter(opener=fake)
    entities = adapter.get_flat_retrieval("test", k=3)
    assert len(entities) == 3
    assert all(isinstance(e, type(entities[0])) for e in entities)


def test_get_ontology_source_returns_declared():
    adapter = FamiliarAdapter()
    assert adapter.get_ontology_source() == "declared"


def test_get_harness_manifest_returns_two_descriptors():
    adapter = FamiliarAdapter(base_url="https://familiar.jphe.in")
    manifest = adapter.get_harness_manifest()
    # Forward-compat: returns [] if HarnessDescriptor types not importable;
    # otherwise returns 2 descriptors. Either is acceptable.
    assert isinstance(manifest, list)
    assert len(manifest) in (0, 2)
```

- [ ] **Step 2: Run, verify they fail**

Run: `pytest tests/test_familiar_adapter.py -v -k "get_flat_retrieval or get_ontology_source or get_harness"`
Expected: 3 failures (methods don't exist yet).

- [ ] **Step 3: Implement the three optional methods**

In `sme/adapters/familiar.py`, add at the end of the class:

```python
def get_flat_retrieval(self, question: str, k: int = 5) -> list[Entity]:
    """Optional: same path as query() but returns only the entities,
    used by Cat 7 token-budget analysis where the answer text is
    irrelevant and only retrieval changes."""
    body = {
        "query": question[:250],
        "limit": k,
        "kind": "content",
        "mock": self.mock_inference,
    }
    status, payload = self._post_json("/api/familiar/eval", body)
    if status != 200:
        return []
    raw_entities = payload.get("retrieved_entities") or []
    return [self._entity_from_payload(e) for e in raw_entities]


def get_ontology_source(self) -> str:
    """Wings/rooms taxonomy is author-declared (mempalace_get_taxonomy
    MCP tool), not inferred from data. Same semantics as
    MemPalaceDaemonAdapter."""
    return "declared"


def get_harness_manifest(self) -> list:
    """Forward-compat for SME Cat 9 (Handshake). Returns descriptors of
    familiar's invocation surfaces — HTTP tool-call + MCP. Falls back to
    [] when the multipass-side descriptor types aren't yet importable
    (Cat 9 not implemented yet on this multipass version)."""
    try:
        from sme.harness import ToolCall, MCPResource  # type: ignore
    except ImportError:
        return []
    return [
        ToolCall(
            name="familiar_query",
            json_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            backend_endpoint=f"{self.base_url}/api/familiar/eval",
        ),
        MCPResource(
            server_url=f"{self.base_url}/mcp",
            resource_uri_pattern="familiar_(recall|reflect|chat)",
        ),
    ]
```

- [ ] **Step 4: Run all tests, verify pass**

Run: `pytest tests/test_familiar_adapter.py -v`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/familiar.py tests/test_familiar_adapter.py
git commit -m "feat(adapters): FamiliarAdapter optional methods

- get_flat_retrieval: same eval endpoint, entities only (Cat 7).
- get_ontology_source: 'declared' — wings/rooms are author-defined.
- get_harness_manifest: forward-compat Cat 9 — returns HTTP-tool +
  MCP descriptors when sme.harness is importable, else [] for
  graceful behavior on multipass versions before Cat 9 ships."
```

---

## Task 9: CLI wiring — `--adapter familiar` + `--mock`/`--no-mock`

**Files:**
- Modify: `sme/cli.py:_load_adapter` + relevant argparse blocks
- Test: `tests/test_familiar_adapter.py` (small CLI integration test)

- [ ] **Step 1: Read the existing `_load_adapter` to see the dispatch shape**

Run: `sed -n '20,80p' sme/cli.py`
Expected: see the `if name == "ladybugdb"` and `if name in ("mempalace-daemon", ...)` branches that instantiate the right adapter and drop incompatible kwargs.

- [ ] **Step 2: Add the familiar branch in `_load_adapter`**

In `sme/cli.py`, in `_load_adapter`, add after the existing `mempalace-daemon` branch:

```python
if name == "familiar":
    from sme.adapters.familiar import FamiliarAdapter

    # Drop kwargs the familiar adapter doesn't understand
    for k in (
        "include_node_tables",
        "include_edge_tables",
        "auto_discover",
        "kg_path",
        "collection_name",
        "default_query_mode",
        "db_path",
        "buffer_pool_size",
        "api_key",      # familiar reads palace-daemon key from .env, not CLI
        "kind",         # familiar always uses kind=content
    ):
        kwargs.pop(k, None)
    return FamiliarAdapter(**kwargs)
```

- [ ] **Step 3: Add `--mock`/`--no-mock` flag handling**

In `sme/cli.py`, locate the helper that builds adapter kwargs from args (search for `adapter_kwargs` definitions — there are several around `cmd_retrieve`, `cmd_check`, etc.). For each subcommand that accepts `--adapter`, add a mutually-exclusive `--mock`/`--no-mock` flag:

Find the function `_add_db_or_api_args(parser)` (search `def _add_db_or_api_args`) and add at the end:

```python
mock_group = parser.add_mutually_exclusive_group()
mock_group.add_argument(
    "--mock", dest="mock_inference", action="store_true",
    default=None,
    help="(familiar adapter) skip inference, score retrieval only "
         "(default: True for Cat 1 determinism)",
)
mock_group.add_argument(
    "--no-mock", dest="mock_inference", action="store_false",
    help="(familiar adapter) run inference; for future Cat 9 work",
)
```

Then in each `cmd_*` helper that calls `_load_adapter`, add `mock_inference=args.mock_inference` to the kwargs. The pattern from `cmd_retrieve` (around `cli.py:782`):

```python
adapter_kwargs = {
    "base_url": getattr(args, "base_url", None),
    "timeout_s": getattr(args, "timeout", None),
    "mock_inference": getattr(args, "mock_inference", None),
    # ... existing keys
}
```

- [ ] **Step 4: Add a small CLI integration test**

Append to `tests/test_familiar_adapter.py`:

```python
import subprocess
import sys


def test_cli_loads_familiar_adapter():
    """The CLI's --adapter familiar branch instantiates without error
    when given a base-url. Doesn't actually query — instantiation only."""
    # Use python -c to exercise the dispatch path without spinning a real CLI run
    result = subprocess.run(
        [
            sys.executable, "-c",
            "from sme.cli import _load_adapter; "
            "a = _load_adapter('familiar', base_url='http://nowhere:1', timeout_s=1.0); "
            "print(type(a).__name__)"
        ],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "FamiliarAdapter" in result.stdout
```

- [ ] **Step 5: Run all tests + commit**

Run: `pytest tests/test_familiar_adapter.py -v`
Expected: 19 passed.

```bash
git add sme/cli.py tests/test_familiar_adapter.py
git commit -m "feat(cli): wire --adapter familiar + --mock/--no-mock flags

Adds the familiar branch to _load_adapter (mirrors the mempalace-daemon
branch pattern, drops incompatible kwargs). Mutually-exclusive
--mock/--no-mock toggles FamiliarAdapter.mock_inference; default is
--mock for Cat 1 substring-scoring determinism. CLI integration test
exercises the dispatch path."
```

---

## Task 10: Live smoke test (gated by env)

**Files:**
- Create: `tests/test_familiar_live.py`

- [ ] **Step 1: Write the gated smoke test**

Create `tests/test_familiar_live.py`:

```python
"""Gated live-smoke test for FamiliarAdapter.

Skipped unless FAMILIAR_BASE_URL is set, e.g.:
    FAMILIAR_BASE_URL=http://familiar:8080 pytest tests/test_familiar_live.py

Mirrors tests/test_mempalace_daemon_integration.py's pattern.
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
    """At minimum, query() returns a QueryResult — no exceptions
    even if palace is rebuilding."""
    result = adapter.query("realm projects")
    # Don't assert non-empty results — palace HNSW may be rebuilding
    # right now. Just verify the contract holds.
    assert hasattr(result, "answer")
    assert hasattr(result, "context_string")
    assert hasattr(result, "retrieved_entities")
    assert hasattr(result, "retrieved_edges")
    if result.error:
        # Acceptable error shapes
        assert "WARN" in result.error or "endpoint" in result.error or "timeout" in result.error.lower()


def test_live_get_graph_snapshot_returns_lists(adapter: FamiliarAdapter):
    """Graph snapshot is cached server-side (5-min TTL) so this is fast
    after the first call."""
    entities, edges = adapter.get_graph_snapshot()
    assert isinstance(entities, list)
    assert isinstance(edges, list)
    if not entities:
        pytest.skip("graph endpoint returned empty — palace may be rebuilding")
```

- [ ] **Step 2: Verify test skips when env var is unset**

Run: `pytest tests/test_familiar_live.py -v`
Expected: 2 skipped.

- [ ] **Step 3: Verify test runs when env var is set (against staging URL)**

Run: `FAMILIAR_BASE_URL=https://familiar.jphe.in pytest tests/test_familiar_live.py -v`
Expected: 2 passed (or graceful skip on graph snapshot if palace is mid-rebuild).

- [ ] **Step 4: Commit**

```bash
git add tests/test_familiar_live.py
git commit -m "test(adapters): gated live smoke for FamiliarAdapter

Set FAMILIAR_BASE_URL to run; otherwise skipped. Asserts the
QueryResult contract holds and graph_snapshot returns lists. Tolerates
palace HNSW rebuild state via skip+warn handling, so the test is robust
against the operational degradation modes documented in
familiar.realm.watch's reference_palace_hnsw_rebuild memory."
```

---

## Task 11: README + docs/ideas.md updates

**Files:**
- Modify: `README.md`
- Modify: `docs/ideas.md`

- [ ] **Step 1: Add familiar to the adapter table in README.md**

Locate the existing adapter table in `README.md` (search for `mempalace-daemon`). Add a row matching the format:

```markdown
| `familiar`         | familiar.realm.watch v0.2 over HTTP — palace + rerank/decay/compress/grounding pipeline | Mode B (diagnostic) | `--adapter familiar --base-url <url>` |
```

- [ ] **Step 2: Add a "Running familiar adapter" subsection**

In README.md's Quickstart area, parallel to the mempalace-daemon section, add:

```markdown
### Running familiar adapter

`sme-eval` against a running familiar.realm.watch v0.2.0+ instance:

    sme-eval retrieve \
        --adapter familiar \
        --base-url http://familiar:8080 \
        --questions corpora/<your-corpus>.yaml \
        --json /tmp/familiar-run.json

Default `--mock` skips LLM inference for deterministic Cat 1 retrieval
scoring. Pair with `--adapter mempalace-daemon` runs against the same
palace to measure what familiar's v0.2 pipeline contributes on top of
the underlying daemon.
```

- [ ] **Step 3: Update docs/ideas.md**

In `docs/ideas.md`, find the section that says "Cat 9 is not implemented yet". Add a paragraph below it:

```markdown
**Forward-compat in adapters (2026-04-26):** `FamiliarAdapter` (familiar.realm.watch
v0.2's adapter) emits per-question records that include the verbatim
`context_string` sent to inference plus structured `warnings`
(`palace_unreachable`, `low_confidence`, `filtered_null_text_*`,
`stuck_loop`). The `cmd_retrieve` JSON output captures all of this
per-question, so a future `sme/categories/handshake.py` scorer can
compute Cat 9 metrics (9a invocation rate, 9b call-through success,
9c result usage, 9d negative-control rate) from existing run
artifacts without revisiting the adapter API. `get_harness_manifest()`
is also implemented forward-compat — currently returns `[]` because
this multipass version doesn't import `sme.harness.HarnessDescriptor`,
but two descriptors (HTTP `ToolCall` + `MCPResource`) are emitted as
soon as the harness types ship.
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/ideas.md
git commit -m "docs: add familiar adapter to README + Cat-9 forward-compat note

Adapter table row + Quickstart subsection mirror the mempalace-daemon
entries. ideas.md notes that familiar's per-question records are
forward-compatible with the eventual sme/categories/handshake.py scorer."
```

---

## Task 12: Final integration verification + PR prep

**Files:** none (verification + PR)

- [ ] **Step 1: Full pytest run**

Run: `pytest -v --tb=short 2>&1 | tail -40`
Expected: all tests pass; familiar adapter contributes ~19 unit + 2 gated live tests.

- [ ] **Step 2: Lint**

Run: `ruff check sme/adapters/familiar.py sme/adapters/_graph_mapping.py tests/test_familiar_adapter.py tests/test_familiar_live.py`
Expected: no errors. Fix any warnings.

- [ ] **Step 3: CLI smoke against the live deployed instance**

Run:
```bash
sme-eval retrieve \
    --adapter familiar \
    --base-url https://familiar.jphe.in \
    --questions corpora/standard_v0_1/questions.yaml \
    --json /tmp/familiar-baseline.json \
    --mock
```

Expected: produces `/tmp/familiar-baseline.json` with per-question records.
Inspect a sample:
```bash
jq '.results[0]' /tmp/familiar-baseline.json
```
Expected: each result has `error` (possibly `WARN: ...` for soft warnings), `retrieved_entities`, `context_string`.

- [ ] **Step 4: Run the same corpus against `mempalace-daemon` adapter for delta comparison**

Run:
```bash
sme-eval retrieve \
    --adapter mempalace-daemon \
    --base-url http://disks:8085 \
    --questions corpora/standard_v0_1/questions.yaml \
    --json /tmp/daemon-baseline.json
```

Compare:
```bash
jq '[.results[] | select(.recall == 1)] | length' /tmp/familiar-baseline.json
jq '[.results[] | select(.recall == 1)] | length' /tmp/daemon-baseline.json
```
Expected: both numbers print. The delta tells you whether familiar's v0.2 pipeline helped retrieval recall on this corpus.

- [ ] **Step 5: Commit final state + open PR**

```bash
git status   # verify clean tree (all changes committed already)
gh pr create \
    --title "feat(adapters): FamiliarAdapter — SME adapter for familiar.realm.watch v0.2" \
    --body "$(cat <<'EOF'
## Summary

Adds `FamiliarAdapter` so SME can score familiar.realm.watch's v0.2
retrieval pipeline (rerank/decay/compress/grounding) on top of the
palace-daemon-backed palace. Sibling to `MemPalaceDaemonAdapter`;
delta between the two = what familiar's pipeline contributes.

Spec: `docs/superpowers/specs/2026-04-26-familiar-adapter-design.md`
Plan: `docs/superpowers/plans/2026-04-26-familiar-adapter.md`

## Changes

- New `sme/adapters/familiar.py` (~400 lines) with the four required
  + three optional `SMEAdapter` methods; mock_inference=True default
  for Cat 1 determinism.
- New `sme/adapters/_graph_mapping.py` shared module (extracted from
  `mempalace_daemon.py`'s `_project_graph`); both adapters now reuse it.
- `sme/cli.py` wires `--adapter familiar` + `--mock`/`--no-mock`.
- `tests/test_familiar_adapter.py` — 19 unit tests against mocked HTTP.
- `tests/test_familiar_live.py` — gated live smoke (FAMILIAR_BASE_URL).
- README adapter table + Quickstart subsection.
- docs/ideas.md note on Cat 9 forward-compat via FamiliarAdapter records.

## Test plan

- [ ] `pytest -v` all green
- [ ] `ruff check` clean
- [ ] CLI run against https://familiar.jphe.in produces non-empty
      per-question JSON
- [ ] Direct comparison run against mempalace-daemon on the same
      corpus emits a recall delta

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Summary

| Task | Tests added | Files touched |
|---|---|---|
| 1 — extract /graph mapping | 0 (existing tests stay green) | 2 |
| 2 — adapter scaffold | 3 | 2 |
| 3 — ingest_corpus stub | 1 | 2 |
| 4 — query happy path | 1 | 2 |
| 5 — HTTP error contract | 5 | 2 |
| 6 — warnings translation | 4 | 2 |
| 7 — get_graph_snapshot | 2 | 2 |
| 8 — optional methods | 3 | 2 |
| 9 — CLI wiring | 1 | 2 |
| 10 — live smoke (gated) | 2 (skipped by default) | 1 |
| 11 — README + ideas.md | 0 | 2 |
| 12 — verify + PR | 0 | 0 |
| **Total** | **19 unit + 2 gated live** | **2 created, 4 modified** |

Adheres to TDD throughout. Twelve commits map 1:1 to logical changes; each commit's tests pass before moving to the next task.
