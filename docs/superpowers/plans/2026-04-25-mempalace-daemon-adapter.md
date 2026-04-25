# `mempalace-daemon` adapter implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new SME adapter `MemPalaceDaemonAdapter` that talks to a running `palace-daemon` over HTTP, with `query()` driving `/search` and `get_graph_snapshot()` driving `/graph` (with MCP fallback). Ship the SME side independently of the daemon side; the existing direct-ChromaDB `MemPalaceAdapter` is left untouched.

**Architecture:** New file `sme/adapters/mempalace_daemon.py` implementing `SMEAdapter`. Auth and URL resolved from kwargs → `~/.config/palace-daemon/env` → process env. CLI gains `--api-key` and `--kind` flags wired through `_load_adapter` and `_load_adapter_from_args`. Tests mock `urllib.request.urlopen`; an integration suite is gated on `PALACE_DAEMON_URL` so CI does not require a live daemon.

**Tech Stack:** Python 3.10+, `urllib` (stdlib, no new deps), pytest 8, FastAPI (only for understanding the daemon — we don't import it).

**Reference spec:** `docs/superpowers/specs/2026-04-25-mempalace-daemon-adapter-design.md`

---

## File structure

| Path | Action | Responsibility |
|---|---|---|
| `sme/adapters/mempalace_daemon.py` | Create | `MemPalaceDaemonAdapter` class — HTTP client, snapshot projection, ontology reporter |
| `tests/conftest.py` | Modify | Add `fake_urlopen_factory` fixture for mocking HTTP responses without per-test boilerplate |
| `tests/test_mempalace_daemon_adapter.py` | Create | Unit tests, all mocked |
| `tests/test_mempalace_daemon_integration.py` | Create | Live-daemon smoke tests, gated on `PALACE_DAEMON_URL` |
| `tests/fixtures/tiny_questions.yaml` | Create | 2-question YAML for end-to-end CLI smoke |
| `sme/cli.py` | Modify | New `_load_adapter` branch (~line 60); new `--api-key`/`--kind` flags in `_add_db_or_api_args` (~line 464) and in `cmd_retrieve`'s subparser (~line 1056); thread `api_key`/`kind`/`api_url` through `_load_adapter_from_args` (~line 437) and `cmd_retrieve` adapter construction (~line 746) |
| `README.md` | Modify | Replace "Planned: `mempalace-daemon` adapter" subsection with shipped status + invocation example |

The adapter is one file because the class is cohesive and not large enough to justify splitting (estimated ~300 lines including docstrings). Test file is one file for the same reason.

---

## Conventions used in every task

- **Working directory:** `/home/jp/Projects/multipass-structural-memory-eval` (the repo root). All paths in this plan are relative to the repo root unless absolute.
- **Test runner:** `pytest` (already installed via `pip install -e ".[dev]"`).
- **Commit style:** Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`). Each task ends with a single commit unless the task explicitly says otherwise.
- **No `git add -A`.** Stage by exact path.
- **Trailer:** every commit ends with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` per CLAUDE.md.

---

## Task 1: Test scaffolding — fake-urlopen fixture

**Why first:** Every adapter test will need to mock `urllib.request.urlopen`. Build the helper once, reuse everywhere. Eliminates per-test boilerplate.

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Read the existing conftest.py to confirm its current shape**

Run: `cat tests/conftest.py`

Expected: file exports `gap_graph` and `duplicates_graph` fixtures. Don't modify those — append.

- [ ] **Step 2: Append the fake-urlopen fixture and helpers**

Add to the end of `tests/conftest.py`:

```python
import io
import json
import urllib.error


class _FakeResponse:
    """Minimal stand-in for urlopen()'s return value.

    Mocks the context-manager + .read() shape that the adapter uses.
    """

    def __init__(self, body, status=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._buf = io.BytesIO(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._buf.read()


@pytest.fixture
def fake_urlopen_factory(monkeypatch):
    """Build a fake urlopen that returns canned responses per URL.

    Usage::

        fake_urlopen_factory({
            "GET http://daemon/search?q=hi&limit=5&kind=content": {"results": [...]},
            "POST http://daemon/mcp": {"result": {"content": [...]}},
        })

    The key is ``"<METHOD> <full URL up to but not including any extra query>"``.
    Match is by exact prefix on the URL — query strings are compared in full
    when present in the key, otherwise the prefix wins.

    A response value can be:
    * dict/list — JSON-encoded as 200 OK
    * str/bytes — sent as-is, 200 OK
    * tuple ``(status, body)`` — explicit status
    * Exception — raised when the URL is hit
    """

    def factory(routes):
        def fake_urlopen(req, timeout=None):
            method = req.get_method()
            url = req.full_url
            key_full = f"{method} {url}"
            # Try exact match, then prefix match without query
            if key_full in routes:
                resp = routes[key_full]
            else:
                base = url.split("?", 1)[0]
                key_base = f"{method} {base}"
                if key_base in routes:
                    resp = routes[key_base]
                else:
                    raise AssertionError(f"unexpected request: {key_full}")
            if isinstance(resp, Exception):
                raise resp
            if isinstance(resp, tuple):
                status, body = resp
                return _FakeResponse(body, status=status)
            return _FakeResponse(resp)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        return fake_urlopen

    return factory
```

- [ ] **Step 3: Sanity-check that the fixture imports cleanly**

Run: `pytest tests/ --collect-only -q 2>&1 | head -20`

Expected: collection succeeds, no ImportError.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "$(cat <<'EOF'
test: add fake_urlopen_factory fixture for HTTP-mocking adapter tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Adapter file skeleton + auth resolution

**Why:** Get the import path and constructor working before any HTTP code. Auth resolution has three sources and is the most likely place for a config bug.

**Files:**
- Create: `sme/adapters/mempalace_daemon.py`
- Create: `tests/test_mempalace_daemon_adapter.py`

- [ ] **Step 1: Write failing tests for auth resolution**

Create `tests/test_mempalace_daemon_adapter.py`:

```python
"""Tests for sme.adapters.mempalace_daemon — HTTP-mocked, no live daemon."""

from __future__ import annotations

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
```

- [ ] **Step 2: Run the tests; verify all fail with ImportError**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x 2>&1 | tail -20`

Expected: collection fails with `ModuleNotFoundError: No module named 'sme.adapters.mempalace_daemon'`.

- [ ] **Step 3: Create the adapter file with skeleton + auth resolution**

Create `sme/adapters/mempalace_daemon.py`:

```python
"""MemPalace daemon HTTP adapter for SME.

Talks to a running palace-daemon (https://github.com/jphein/palace-daemon)
over HTTP. Unlike sme.adapters.mempalace.MemPalaceAdapter (which opens
ChromaDB directly), this adapter does NO filesystem access and holds NO
parallel handles to the palace SQLite — it only makes HTTP requests.

Use this adapter when:
* you run palace-daemon (the daemon is the single writer to the palace),
* OR you want SME's structural readings to flow through the same
  retrieval path your production agents use.

For single-process MemPalace installs without the daemon, the existing
MemPalaceAdapter is correct — direct ChromaDB access is fine when there
is no concurrent writer to fight with.

See ``docs/superpowers/specs/2026-04-25-mempalace-daemon-adapter-design.md``
for the full design.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


DEFAULT_ENV_FILE = "~/.config/palace-daemon/env"
DEFAULT_KIND = "content"
DEFAULT_TIMEOUT = 180.0  # seconds — list_wings on a 151K-drawer palace ~30s


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser. Strips surrounding double-quotes.

    Ignores blank lines and ``# ...`` comments. Does NOT do shell expansion;
    the daemon's env file is a flat key/value list, not a shell script.
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if val and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        out[key] = val
    return out


class MemPalaceDaemonAdapter(SMEAdapter):
    """SMEAdapter against a running palace-daemon HTTP API.

    Construction does not connect — auth is resolved eagerly but the first
    network call happens in ``query()`` or ``get_graph_snapshot()``.

    Args:
        api_url: Daemon base URL (e.g. ``http://disks.jphe.in:8085``).
            Trailing slash stripped.
        api_key: Sent as ``X-API-Key`` header on every request.
        env_file: Path to an env file with ``PALACE_DAEMON_URL`` /
            ``PALACE_API_KEY``. Defaults to ``~/.config/palace-daemon/env``.
        kind: Default ``kind`` filter for ``/search``. ``"content"``
            (default) excludes Stop-hook auto-save checkpoints; pass
            ``"all"`` to disable, ``"checkpoint"`` for snapshot-only.
        api_timeout: Per-request HTTP timeout in seconds.
        prefer_graph_endpoint: If True (default), ``get_graph_snapshot``
            tries ``GET /graph`` first; on 404 it falls back to walking
            the four MCP tools. Set False to force the MCP path.
        read_only: Accepted for CLI parity. Ignored — this adapter only
            reads via HTTP.
        db_path: Accepted for CLI parity. Ignored — daemon owns the file.
    """

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        env_file: Optional[str | Path] = None,
        kind: str = DEFAULT_KIND,
        api_timeout: float = DEFAULT_TIMEOUT,
        prefer_graph_endpoint: bool = True,
        read_only: bool = True,
        db_path: Optional[str] = None,
    ) -> None:
        self.kind = kind
        self.api_timeout = api_timeout
        self.prefer_graph_endpoint = prefer_graph_endpoint

        env_path = Path(os.path.expanduser(str(env_file or DEFAULT_ENV_FILE)))
        env_vars = _parse_env_file(env_path)

        resolved_url = (
            api_url
            or env_vars.get("PALACE_DAEMON_URL")
            or os.environ.get("PALACE_DAEMON_URL")
        )
        resolved_key = (
            api_key
            or env_vars.get("PALACE_API_KEY")
            or os.environ.get("PALACE_API_KEY")
        )

        if not resolved_url:
            raise ValueError(
                "MemPalaceDaemonAdapter needs api_url. Pass it explicitly, "
                f"set PALACE_DAEMON_URL in {env_path}, or export it in the "
                "environment."
            )
        if not resolved_key:
            raise ValueError(
                "MemPalaceDaemonAdapter needs api_key. Pass it explicitly, "
                f"set PALACE_API_KEY in {env_path}, or export it in the "
                "environment."
            )

        self.api_url = resolved_url.rstrip("/")
        self.api_key = resolved_key

    # --- SMEAdapter required methods ---------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "MemPalaceDaemonAdapter is diagnostic-only (Mode B). To seed a "
            "test palace, use the daemon's /memory POST endpoint or the "
            "mempalace CLI directly."
        )

    def query(self, question: str, **_kwargs: Any) -> QueryResult:
        raise NotImplementedError("Implemented in a later task")

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        raise NotImplementedError("Implemented in a later task")

    def close(self) -> None:
        pass
```

- [ ] **Step 4: Re-run the auth tests; verify they pass**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v 2>&1 | tail -20`

Expected: all 5 auth tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/mempalace_daemon.py tests/test_mempalace_daemon_adapter.py
git commit -m "$(cat <<'EOF'
feat(adapters): scaffold MemPalaceDaemonAdapter with auth resolution

Three-source auth resolution: kwargs > env file > process env. Raises
ValueError at construction if nothing resolves. query() and
get_graph_snapshot() raise NotImplementedError pending follow-on tasks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `query()` happy path

**Files:**
- Modify: `sme/adapters/mempalace_daemon.py`
- Modify: `tests/test_mempalace_daemon_adapter.py`

- [ ] **Step 1: Write failing tests for query() success cases**

Append to `tests/test_mempalace_daemon_adapter.py`:

```python
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
```

- [ ] **Step 2: Run the new tests; verify they fail with NotImplementedError**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v 2>&1 | tail -20`

Expected: 6 new tests fail at the `NotImplementedError("Implemented in a later task")` line. Earlier auth tests still pass.

- [ ] **Step 3: Implement `query()` happy path in the adapter**

Replace the body of `query` in `sme/adapters/mempalace_daemon.py` with:

```python
    def query(
        self,
        question: str,
        *,
        n_results: int = 5,
        kind: Optional[str] = None,
        route: bool = False,  # accepted for CLI parity; daemon does its own
        wing: Optional[str] = None,  # ignored; reserved for future expansion
        room: Optional[str] = None,  # ignored; reserved for future expansion
    ) -> QueryResult:
        chosen_kind = kind or self.kind
        params = urllib.parse.urlencode(
            {"q": question, "limit": n_results, "kind": chosen_kind}
        )
        url = f"{self.api_url}/search?{params}"
        body = self._http_get(url)
        # body is a parsed dict here; errors are returned as QueryResult
        if isinstance(body, QueryResult):
            return body

        results = body.get("results") or []
        warnings = body.get("warnings") or []
        total = body.get("total_before_filter")
        available = body.get("available_in_scope")
        retrieval_path = [
            f"kind={chosen_kind}",
            f"available_in_scope={available}",
            f"total_before_filter={total}",
        ]

        if not results:
            err = (
                f"WARN: {'; '.join(warnings)}"
                if warnings
                else "NO_RESULTS"
            )
            return QueryResult(
                answer="",
                context_string="",
                error=err,
                retrieval_path=retrieval_path,
            )

        context_parts: list[str] = []
        retrieved: list[Entity] = []
        for i, hit in enumerate(results):
            meta = hit.get("metadata") or {}
            wing_name = meta.get("wing", "?")
            room_name = meta.get("room", "?")
            source_file = meta.get("source_file") or f"hit{i}"
            source_label = Path(source_file).name or source_file
            text = hit.get("text", "") or ""
            context_parts.append(
                f"[{i + 1}] [{wing_name}/{room_name}] {source_label}\n{text}"
            )
            retrieved.append(
                Entity(
                    id=f"drawer_hit:{i}",
                    name=source_label,
                    entity_type=f"drawer:{room_name}",
                    properties={
                        "_table": "mempalace_daemon_hit",
                        "wing": wing_name,
                        "room": room_name,
                        "score": hit.get("score"),
                        "source_file": source_file,
                    },
                )
            )

        context_string = "\n\n".join(context_parts)
        warn_err = f"WARN: {'; '.join(warnings)}" if warnings else None
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved,
            retrieval_path=retrieval_path,
            error=warn_err,
        )

    # --- HTTP plumbing ------------------------------------------------

    def _http_get(self, url: str) -> Any:
        """GET ``url`` with X-API-Key, return parsed JSON or a QueryResult
        wrapping the error. Used by both query() and snapshot calls.
        """
        req = urllib.request.Request(
            url, method="GET", headers={"X-API-Key": self.api_key}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                detail = str(e)
            if e.code in (401, 403):
                err = f"AUTH: invalid X-API-Key ({e.code})"
            else:
                err = f"HTTP {e.code}: {detail}"
            return QueryResult(answer="", context_string="", error=err)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return QueryResult(
                answer="", context_string="", error=f"CONNECTION: {e}"
            )
        except Exception as e:  # pragma: no cover
            return QueryResult(
                answer="", context_string="", error=f"INTERNAL: {e}"
            )
```

- [ ] **Step 4: Re-run; verify the 6 new tests pass and earlier ones still pass**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v 2>&1 | tail -25`

Expected: 11 PASSED.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/mempalace_daemon.py tests/test_mempalace_daemon_adapter.py
git commit -m "$(cat <<'EOF'
feat(adapters): MemPalaceDaemonAdapter.query happy path

GET /search builds context_string in the same format as the existing
MemPalaceAdapter so tiktoken counts stay comparable across adapters.
retrieval_path captures kind + scope counts for downstream scoring.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `query()` error and warning paths

**Files:**
- Modify: `tests/test_mempalace_daemon_adapter.py`

- [ ] **Step 1: Write failing tests for the error/warning paths**

Append to `tests/test_mempalace_daemon_adapter.py`:

```python
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
```

- [ ] **Step 2: Run; verify the 7 new tests fail or pass appropriately**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v 2>&1 | tail -30`

Expected: depending on what was implemented in Task 3, some pass already (Task 3's `_http_get` already handles HTTPError/URLError). The header-capture and warnings-soft-error tests should pass too. **If anything is RED, fix the adapter or test until all 18 PASS.** No new code is expected here — Task 3's implementation should cover this — but write the tests anyway to lock in the contract.

- [ ] **Step 3: Run again, confirm all green**

Run: `pytest tests/test_mempalace_daemon_adapter.py -v 2>&1 | tail -20`

Expected: 18 PASSED.

- [ ] **Step 4: Commit**

```bash
git add tests/test_mempalace_daemon_adapter.py
git commit -m "$(cat <<'EOF'
test(adapters): lock MemPalaceDaemonAdapter query error/warning contract

Covers WARN-with-results soft signal, NO_RESULTS, AUTH, HTTP 5xx,
connection failures, and X-API-Key header propagation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `get_graph_snapshot()` — `/graph` fast path

**Why:** Implement the fast path first so the projection logic is exercised. The MCP fallback (Task 6) is a different code path producing the same projection.

**Files:**
- Modify: `sme/adapters/mempalace_daemon.py`
- Modify: `tests/test_mempalace_daemon_adapter.py`

- [ ] **Step 1: Write failing tests for the /graph fast path**

Append to `tests/test_mempalace_daemon_adapter.py`:

```python
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
```

- [ ] **Step 2: Run; verify the 5 snapshot tests fail with NotImplementedError**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v -k snapshot 2>&1 | tail -15`

Expected: 5 FAILS at the `NotImplementedError("Implemented in a later task")` line.

- [ ] **Step 3: Implement the `/graph` fast path + projection**

In `sme/adapters/mempalace_daemon.py`, replace the body of `get_graph_snapshot` and add the projection helper:

```python
    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        if self.prefer_graph_endpoint:
            body = self._http_get(f"{self.api_url}/graph")
            # _http_get returns QueryResult on error; treat 404 specifically
            if isinstance(body, QueryResult):
                if body.error and body.error.startswith("HTTP 404"):
                    log.info(
                        "/graph endpoint not present (404); falling back to MCP"
                    )
                else:
                    log.warning(
                        "/graph fetch failed: %s; falling back to MCP",
                        body.error,
                    )
                return self._snapshot_via_mcp()
            return self._project_graph(body)
        return self._snapshot_via_mcp()

    def _project_graph(self, body: dict) -> tuple[list[Entity], list[Edge]]:
        """Turn the daemon's /graph response into (entities, edges).

        Mirrors the wing/room/tunnel projection in
        ``sme.adapters.mempalace.MemPalaceAdapter.get_graph_snapshot``,
        minus drawer-level surface (impractical at 151K-drawer scale
        through the HTTP API).
        """
        wings: dict[str, int] = body.get("wings") or {}
        rooms_by_wing: list[dict] = body.get("rooms") or []
        tunnels: list[dict] = body.get("tunnels") or []
        kg_ents: list[dict] = body.get("kg_entities") or []
        kg_trips: list[dict] = body.get("kg_triples") or []

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
        room_count: dict[str, int] = defaultdict(int)
        for entry in rooms_by_wing:
            wing = entry.get("wing", "")
            for room, n in (entry.get("rooms") or {}).items():
                if not room or room == "general":
                    continue
                room_wings[room].add(wing)
                room_count[room] += int(n or 0)

        for room in sorted(room_wings):
            wings_list = sorted(room_wings[room])
            entities.append(
                Entity(
                    id=f"room:{room}",
                    name=room,
                    entity_type="room:untyped",
                    properties={
                        "_table": "room",
                        "wings": wings_list,
                        "drawer_count": room_count[room],
                    },
                )
            )
            for wing in wings_list:
                edges.append(
                    Edge(
                        source_id=f"room:{room}",
                        target_id=f"wing:{wing}",
                        edge_type="member_of",
                        properties={
                            "_table": "structural",
                            "drawer_count": room_count[room],
                        },
                    )
                )

        # Tunnels — wing<->wing for each shared room
        for t in tunnels:
            room = t.get("room", "")
            t_wings = sorted(t.get("wings") or [])
            for i, wa in enumerate(t_wings):
                for wb in t_wings[i + 1:]:
                    edges.append(
                        Edge(
                            source_id=f"wing:{wa}",
                            target_id=f"wing:{wb}",
                            edge_type="tunnel",
                            properties={
                                "_table": "structural",
                                "via_room": room,
                            },
                        )
                    )

        # KG layer
        for ke in kg_ents:
            ent_id = ke.get("id")
            if not ent_id:
                continue
            props = dict(ke.get("properties") or {})
            props["_table"] = "kg_entity"
            entities.append(
                Entity(
                    id=f"kg:{ent_id}",
                    name=ke.get("name") or ent_id,
                    entity_type=f"kg:{ke.get('type') or 'unknown'}",
                    properties=props,
                )
            )
        for tr in kg_trips:
            subj, obj = tr.get("subject"), tr.get("object")
            if not subj or not obj:
                continue
            edges.append(
                Edge(
                    source_id=f"kg:{subj}",
                    target_id=f"kg:{obj}",
                    edge_type=tr.get("predicate") or "kg_related",
                    properties={
                        "_table": "kg_triple",
                        "_created_at": tr.get("valid_from"),
                        "valid_to": tr.get("valid_to"),
                        "confidence": tr.get("confidence"),
                        "source_file": tr.get("source_file"),
                    },
                )
            )

        return entities, edges

    def _snapshot_via_mcp(self) -> tuple[list[Entity], list[Edge]]:
        """Stub — implemented in the next task."""
        log.warning("MCP fallback path not yet implemented; returning empty")
        return [], []
```

- [ ] **Step 4: Re-run; verify the 5 snapshot tests pass**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v -k snapshot 2>&1 | tail -20`

Expected: 5 PASSED.

- [ ] **Step 5: Run the full file; everything green**

Run: `pytest tests/test_mempalace_daemon_adapter.py -v 2>&1 | tail -25`

Expected: 23 PASSED.

- [ ] **Step 6: Commit**

```bash
git add sme/adapters/mempalace_daemon.py tests/test_mempalace_daemon_adapter.py
git commit -m "$(cat <<'EOF'
feat(adapters): MemPalaceDaemonAdapter /graph fast-path snapshot

GET /graph in one call; projects to wings, rooms, member_of, tunnel,
and KG layers. Mirrors the existing direct adapter's projection minus
drawer-level surface (impractical to fetch at scale over HTTP).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `get_graph_snapshot()` — MCP fallback path

**Why:** Older daemons (pre-1.6.0) won't have `/graph`. The fallback walks `mempalace_list_wings` → `mempalace_list_rooms` per wing → `mempalace_list_tunnels`. This is the path that runs against the live daemon today (1.5.1).

**Files:**
- Modify: `sme/adapters/mempalace_daemon.py`
- Modify: `tests/test_mempalace_daemon_adapter.py`

- [ ] **Step 1: Write failing tests for MCP fallback**

Append to `tests/test_mempalace_daemon_adapter.py`:

```python
# --- get_graph_snapshot — MCP fallback ------------------------------


def _mcp_envelope(payload: dict) -> dict:
    """Build an MCP tools/call response envelope wrapping a JSON payload."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }


def test_snapshot_falls_back_to_mcp_on_404(
    monkeypatch, tmp_path, fake_urlopen_factory
):
    import json as _json
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
```

Then **also add the MCP request router helper** to the same test file (above
the new tests is fine):

```python
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
        return result
    return _route
```

The factory in `tests/conftest.py` only handles plain values, not callables.
Extend it now to support callables — update `tests/conftest.py`'s
`fake_urlopen` body inside the `factory()` closure:

```python
        def fake_urlopen(req, timeout=None):
            method = req.get_method()
            url = req.full_url
            key_full = f"{method} {url}"
            if key_full in routes:
                resp = routes[key_full]
            else:
                base = url.split("?", 1)[0]
                key_base = f"{method} {base}"
                if key_base in routes:
                    resp = routes[key_base]
                else:
                    raise AssertionError(f"unexpected request: {key_full}")
            # If the registered response is a callable, invoke it with the
            # request — used for body-dispatching mocks (e.g. JSON-RPC).
            if callable(resp) and not isinstance(resp, Exception):
                resp = resp(req)
            if isinstance(resp, Exception):
                raise resp
            if isinstance(resp, tuple):
                status, body = resp
                return _FakeResponse(body, status=status)
            return _FakeResponse(resp)
```

- [ ] **Step 2: Run; verify the 3 new tests fail and the conftest still loads**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v -k mcp 2>&1 | tail -15`

Expected: 3 FAILS — currently `_snapshot_via_mcp` returns empty.

- [ ] **Step 3: Implement `_snapshot_via_mcp` + helpers**

In `sme/adapters/mempalace_daemon.py`, replace the stub `_snapshot_via_mcp` with:

```python
    def _snapshot_via_mcp(self) -> tuple[list[Entity], list[Edge]]:
        """Walk the four MCP read tools and project to (entities, edges).

        Used when /graph is absent (older daemons) or when
        ``prefer_graph_endpoint=False``.
        """
        wings_payload = self._mcp_call("mempalace_list_wings", {})
        if wings_payload is None:
            log.warning("list_wings failed; returning empty snapshot")
            return [], []
        wings: dict[str, int] = wings_payload.get("wings") or {}

        # Per-wing list_rooms — sequential to match daemon-side rate limits;
        # the daemon's MCP server runs each tool in its own asyncio task.
        rooms_by_wing: list[dict] = []
        for wing in sorted(wings):
            rooms_payload = self._mcp_call(
                "mempalace_list_rooms", {"wing": wing}
            )
            if rooms_payload is None:
                log.warning("list_rooms(wing=%s) failed; skipping", wing)
                continue
            rooms_by_wing.append(rooms_payload)

        tunnels_payload = self._mcp_call("mempalace_list_tunnels", {})
        if tunnels_payload is None:
            log.warning("list_tunnels failed; tunnels omitted from snapshot")
            tunnels_payload = []
        # The MCP tool returns a list directly — coerce to the /graph schema
        # so _project_graph can consume it.
        tunnels = (
            tunnels_payload
            if isinstance(tunnels_payload, list)
            else tunnels_payload.get("tunnels", [])
        )

        synthesised = {
            "wings": wings,
            "rooms": rooms_by_wing,
            "tunnels": tunnels,
            "kg_entities": [],   # not reachable via MCP without arguments
            "kg_triples": [],
        }
        return self._project_graph(synthesised)

    def _mcp_call(self, tool: str, arguments: dict) -> Any:
        """POST /mcp with a tools/call envelope. Returns the parsed
        ``content[0].text`` JSON payload, or None on failure (logged).
        """
        rpc_body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.api_url}/mcp",
            data=rpc_body,
            method="POST",
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                envelope = json.loads(resp.read().decode("utf-8"))
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
        ) as e:
            log.warning("MCP %s failed: %s", tool, e)
            return None
        result = envelope.get("result") or {}
        content = result.get("content") or []
        if not content:
            err = envelope.get("error")
            if err:
                log.warning("MCP %s returned error: %s", tool, err)
            return None
        text = content[0].get("text", "")
        try:
            return json.loads(text)
        except Exception as e:  # pragma: no cover
            log.warning("MCP %s returned non-JSON: %s (%s)", tool, text[:80], e)
            return None
```

- [ ] **Step 4: Re-run; verify all 3 MCP tests pass**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v -k mcp 2>&1 | tail -15`

Expected: 3 PASSED.

- [ ] **Step 5: Run full test file**

Run: `pytest tests/test_mempalace_daemon_adapter.py -v 2>&1 | tail -30`

Expected: 26 PASSED.

- [ ] **Step 6: Commit**

```bash
git add sme/adapters/mempalace_daemon.py tests/test_mempalace_daemon_adapter.py tests/conftest.py
git commit -m "$(cat <<'EOF'
feat(adapters): MCP fallback path for MemPalaceDaemonAdapter snapshot

When /graph is unavailable (older daemons or prefer_graph_endpoint=False),
walk mempalace_list_wings, mempalace_list_rooms per wing, and
mempalace_list_tunnels via POST /mcp. Per-wing failures degrade to a
partial snapshot rather than aborting.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Ontology source + ingest_corpus error message

**Why:** Cat 8 calls `get_ontology_source`. The daemon adapter should report the same readme-derived ontology as the existing direct adapter so cat8 results are comparable across the two.

**Files:**
- Modify: `sme/adapters/mempalace_daemon.py`
- Modify: `tests/test_mempalace_daemon_adapter.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mempalace_daemon_adapter.py`:

```python
# --- ontology + ingest -----------------------------------------------


def test_get_ontology_source_matches_existing_adapter(monkeypatch, tmp_path):
    a = _adapter(monkeypatch, tmp_path)
    ont = a.get_ontology_source()
    assert ont["type"] == "readme"
    declared = {entry["kind"] for entry in ont["schema"]}
    assert "structural" in declared
    assert "hall_vocabulary" in declared


def test_ingest_corpus_raises_with_helpful_message(monkeypatch, tmp_path):
    a = _adapter(monkeypatch, tmp_path)
    with pytest.raises(NotImplementedError, match="diagnostic-only"):
        a.ingest_corpus([])
```

- [ ] **Step 2: Run; verify failures (the ontology test should fail because the default returns the base class's empty dict)**

Run: `pytest tests/test_mempalace_daemon_adapter.py -x -v -k "ontology or ingest" 2>&1 | tail -10`

Expected: 1 FAIL (ontology), 1 PASS (ingest).

- [ ] **Step 3: Implement `get_ontology_source`**

Add to `sme/adapters/mempalace_daemon.py` (just before the `close` method):

```python
    def get_ontology_source(self) -> dict:
        """Return the same MemPalace readme-derived ontology as the
        direct ChromaDB adapter, so Cat 8 results are comparable across
        the two access paths. The schema *as documented* doesn't change
        because the backend access path does."""
        return {
            "type": "readme",
            "schema": [
                {
                    "kind": "structural",
                    "entities": [
                        "wing", "room", "hall", "tunnel", "closet", "drawer"
                    ],
                },
                {
                    "kind": "hall_vocabulary",
                    "values": [
                        "facts", "events", "discoveries",
                        "preferences", "advice",
                    ],
                },
            ],
            "documentation": (
                "MemPalace organizes memories into Wings, Rooms, Halls, "
                "Tunnels, Closets, and Drawers. See the existing "
                "MemPalaceAdapter docstring for the full vocabulary. "
                "This adapter accesses the palace via palace-daemon's "
                "HTTP API rather than direct ChromaDB; the documented "
                "ontology is unchanged."
            ),
        }
```

- [ ] **Step 4: Re-run**

Run: `pytest tests/test_mempalace_daemon_adapter.py -v 2>&1 | tail -15`

Expected: 28 PASSED.

- [ ] **Step 5: Commit**

```bash
git add sme/adapters/mempalace_daemon.py tests/test_mempalace_daemon_adapter.py
git commit -m "$(cat <<'EOF'
feat(adapters): MemPalaceDaemonAdapter ontology + ingest error message

Returns the same readme-typed ontology as the existing MemPalaceAdapter so
Cat 8 readings are comparable across the direct-ChromaDB and HTTP paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: CLI plumbing — `_load_adapter` branch + flags

**Why:** Without CLI exposure, the adapter is unreachable via `sme-eval`. This task wires it into the existing `_load_adapter`, the shared arg helpers, and the `retrieve` subcommand specifically.

**Files:**
- Modify: `sme/cli.py`

- [ ] **Step 1: Read the relevant CLI sections to confirm line numbers haven't drifted**

Run: `grep -n "_load_adapter\|_add_db_or_api_args\|cmd_retrieve" sme/cli.py`

Expected output should include:
- `def _load_adapter(name: str, **kwargs)` near line 25
- `def _add_db_or_api_args(parser` near line 464
- `def cmd_retrieve(args` near line 721

If these have drifted, update the offsets in the steps below to match.

- [ ] **Step 2: Add the `mempalace-daemon` branch to `_load_adapter`**

In `sme/cli.py`, find the block that handles `mempalace`:

```python
    if name == "mempalace":
        from sme.adapters.mempalace import MemPalaceAdapter
        ...
        return MemPalaceAdapter(**kwargs)
```

**Insert immediately before that block:**

```python
    if name in ("mempalace-daemon", "mempalace_daemon"):
        from sme.adapters.mempalace_daemon import MemPalaceDaemonAdapter

        # Drop kwargs the daemon adapter doesn't understand
        for k in (
            "include_node_tables",
            "include_edge_tables",
            "auto_discover",
            "kg_path",
            "collection_name",
            "default_query_mode",
            "db_path",
            "buffer_pool_size",
        ):
            kwargs.pop(k, None)
        return MemPalaceDaemonAdapter(**kwargs)
```

- [ ] **Step 3: Add `--api-key` and `--kind` to `_add_db_or_api_args`**

In `sme/cli.py`, find `_add_db_or_api_args` (~line 464). Append at the end of the function:

```python
    parser.add_argument(
        "--api-key",
        default=None,
        metavar="KEY",
        help="(mempalace-daemon) X-API-Key for the palace-daemon. "
        "Defaults to PALACE_API_KEY in ~/.config/palace-daemon/env, "
        "then to the process env var of the same name.",
    )
    parser.add_argument(
        "--kind",
        default=None,
        metavar="KIND",
        help="(mempalace-daemon) /search kind filter. Defaults to "
        "'content' (excludes Stop-hook auto-save checkpoints). Use "
        "'all' to disable, or 'checkpoint' for snapshot-only lookups.",
    )
```

- [ ] **Step 4: Thread `--api-key` and `--kind` through `_load_adapter_from_args`**

In `sme/cli.py`, find `_load_adapter_from_args` (~line 437). Update the for-loop that maps argparse attrs to adapter kwargs:

```python
    for attr, key in (
        ("auto_discover", "auto_discover"),
        ("node_tables", "include_node_tables"),
        ("edge_tables", "include_edge_tables"),
        ("kg_path", "kg_path"),
        ("collection_name", "collection_name"),
        ("api_key", "api_key"),    # NEW
        ("kind", "kind"),          # NEW
    ):
        val = getattr(args, attr, None)
        if val:
            adapter_kwargs[key] = val
```

- [ ] **Step 5: Add `--api-url`, `--api-key`, `--kind` to the `retrieve` subparser**

In `sme/cli.py`, find the `retrieve` subparser block (~line 995). Locate this snippet:

```python
    ret.add_argument(
        "--api-url",
        metavar="URL",
        help="(ladybugdb) HTTP base URL for API-mode queries (e.g. "
        ...
    )
```

It already exists — but mention of mempalace-daemon is missing. **Replace** the
help text:

```python
    ret.add_argument(
        "--api-url",
        metavar="URL",
        help="(ladybugdb, mempalace-daemon) HTTP base URL for API-mode "
        "queries (e.g. http://disks.jphe.in:8085).",
    )
```

Then **add immediately after** that block:

```python
    ret.add_argument(
        "--api-key",
        metavar="KEY",
        help="(mempalace-daemon) X-API-Key. Defaults to PALACE_API_KEY in "
        "~/.config/palace-daemon/env, then process env.",
    )
    ret.add_argument(
        "--kind",
        metavar="KIND",
        help="(mempalace-daemon) /search kind filter. Default 'content'.",
    )
```

- [ ] **Step 6: Thread the new flags through `cmd_retrieve`'s adapter construction**

In `sme/cli.py`, find `cmd_retrieve` (~line 721). Locate the kwargs-packing block (~line 746):

```python
    adapter_kwargs: dict[str, Any] = {
        "db_path": args.db,
        "read_only": True,
    }
    if args.collection_name:
        adapter_kwargs["collection_name"] = args.collection_name
    if getattr(args, "api_url", None):
        adapter_kwargs["api_url"] = args.api_url
    if getattr(args, "query_mode", None):
        adapter_kwargs["default_query_mode"] = args.query_mode
```

**Append before the `adapter = _load_adapter(...)` line:**

```python
    if getattr(args, "api_key", None):
        adapter_kwargs["api_key"] = args.api_key
    if getattr(args, "kind", None):
        adapter_kwargs["kind"] = args.kind
```

- [ ] **Step 7: Run a CLI smoke import sanity check**

Run: `python3 -c "from sme.cli import main; print('ok')"`

Expected: `ok`. (No SyntaxError, no ImportError.)

- [ ] **Step 8: Run a `--help` smoke**

Run: `python3 -m sme.cli retrieve --help 2>&1 | grep -E "api-url|api-key|kind"`

Expected: lines for `--api-url`, `--api-key`, `--kind` all present.

- [ ] **Step 9: Run the full unit test suite to confirm nothing regressed**

Run: `pytest tests/ -v 2>&1 | tail -10`

Expected: all green; the new adapter tests + the existing Cat 4 / Cat 5 / gap tests all pass.

- [ ] **Step 10: Commit**

```bash
git add sme/cli.py
git commit -m "$(cat <<'EOF'
feat(cli): wire mempalace-daemon adapter, --api-key, --kind

Adds the mempalace-daemon branch to _load_adapter and threads
--api-key / --kind through _load_adapter_from_args and the retrieve
subparser.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Live-daemon integration smoke test (gated)

**Files:**
- Create: `tests/test_mempalace_daemon_integration.py`

- [ ] **Step 1: Write the gated integration test**

Create `tests/test_mempalace_daemon_integration.py`:

```python
"""Live-daemon smoke tests for MemPalaceDaemonAdapter.

Skipped automatically when PALACE_DAEMON_URL is not set in the
environment, so CI without a daemon stays green. Run locally with:

    PALACE_DAEMON_URL=http://disks.jphe.in:8085 \
    PALACE_API_KEY=$(grep ^PALACE_API_KEY ~/.config/palace-daemon/env | cut -d= -f2) \
    pytest tests/test_mempalace_daemon_integration.py -v

The tests are read-only: query() and get_graph_snapshot() only.
"""

from __future__ import annotations

import os

import pytest

from sme.adapters.base import QueryResult
from sme.adapters.mempalace_daemon import MemPalaceDaemonAdapter


pytestmark = pytest.mark.skipif(
    not os.environ.get("PALACE_DAEMON_URL"),
    reason="needs a running palace-daemon; set PALACE_DAEMON_URL to enable",
)


@pytest.fixture
def adapter():
    a = MemPalaceDaemonAdapter()
    yield a
    a.close()


def test_query_returns_query_result(adapter):
    r = adapter.query("hello", n_results=2)
    assert isinstance(r, QueryResult)
    # Either we got results, or we got a soft-warn / NO_RESULTS — never an
    # uncaught exception.


def test_snapshot_returns_at_least_one_wing(adapter):
    entities, _ = adapter.get_graph_snapshot()
    wing_names = {e.name for e in entities if e.entity_type == "wing"}
    # Live palace has 30+ wings on JP's install; even a fresh palace has >=1.
    assert len(wing_names) >= 1


def test_kind_default_excludes_more_than_kind_all(adapter):
    """Cross-check the README's claim: kind='content' filters strictly
    less than kind='all'. If the live palace has any auto-save
    checkpoints, this assertion holds; on a fresh palace it might be
    equal — assert >= rather than > to avoid flakes."""
    r_all = adapter.query("the", n_results=5, kind="all")
    r_content = adapter.query("the", n_results=5, kind="content")
    # We can't compare result counts directly because limit caps both;
    # use total_before_filter from retrieval_path.
    def total_before(rp):
        for s in rp:
            if s.startswith("total_before_filter="):
                return int(s.split("=", 1)[1])
        return -1
    assert total_before(r_all.retrieval_path) >= total_before(
        r_content.retrieval_path
    )
```

- [ ] **Step 2: Confirm the gate works (test SKIPS without the env var)**

Run: `pytest tests/test_mempalace_daemon_integration.py -v 2>&1 | tail -10`

Expected: tests SKIPPED (the SKIPIF triggers because `PALACE_DAEMON_URL` isn't set in the test process by default).

- [ ] **Step 3: Run with the live daemon**

Run:

```bash
set -a; source ~/.config/palace-daemon/env; set +a
pytest tests/test_mempalace_daemon_integration.py -v
```

Expected: 3 PASSED. If `query("hello")` lands on the buggy `kind=content` vector path, `r.error` may start with `WARN:` — that's a pass for the contract test (we're checking we get a `QueryResult`, not asserting clean retrieval).

- [ ] **Step 4: Commit**

```bash
git add tests/test_mempalace_daemon_integration.py
git commit -m "$(cat <<'EOF'
test(adapters): live-daemon smoke for MemPalaceDaemonAdapter (gated)

Skipped when PALACE_DAEMON_URL is unset so CI without a daemon stays
green. Asserts query() returns a QueryResult, snapshot returns >=1
wing, and kind=all >= kind=content for total_before_filter (validates
the README's filter claim).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: End-to-end CLI smoke against the live daemon

**Why:** Unit tests cover the adapter; integration tests cover the live HTTP. This task catches CLI-wiring bugs that only show up when `sme-eval retrieve` actually invokes everything together.

**Files:**
- Create: `tests/fixtures/tiny_questions.yaml`

- [ ] **Step 1: Create a tiny corpus YAML for the smoke**

Create `tests/fixtures/tiny_questions.yaml`:

```yaml
version: "smoke-2026-04-25"
questions:
  - id: q1
    text: "what is the structural memory evaluation framework"
    expected_sources: []
    min_hops: 0
  - id: q2
    text: "how does mempalace organize memories"
    expected_sources: []
    min_hops: 0
```

- [ ] **Step 2: Run the smoke against the live daemon**

Run:

```bash
set -a; source ~/.config/palace-daemon/env; set +a
sme-eval retrieve \
    --adapter mempalace-daemon \
    --questions tests/fixtures/tiny_questions.yaml \
    --n-results 3 \
    --json /tmp/mempalace-daemon-smoke.json
```

Expected:
- Two question results printed.
- No Python tracebacks.
- A JSON file written to `/tmp/mempalace-daemon-smoke.json`.
- `cat /tmp/mempalace-daemon-smoke.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['adapter'], len(d['questions']), d['summary']['mean_recall'])"` prints `mempalace-daemon 2 <some_float>`.

If this surfaces `WARN:` errors for some questions, that's expected on the
current daemon (the `kind=content` vector-path bug). The smoke is checking
that the CLI plumbing works end-to-end, not that retrieval is clean.

- [ ] **Step 3: Commit the fixture**

```bash
git add tests/fixtures/tiny_questions.yaml
git commit -m "$(cat <<'EOF'
test(fixtures): tiny corpus for mempalace-daemon CLI smoke

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: README — update the fork-roadmap section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Locate the section to replace**

Run: `grep -n "Planned: \`mempalace-daemon\` adapter\|Why the existing adapter still has a use" README.md`

Expected: two line numbers — these bracket the section to rewrite.

- [ ] **Step 2: Replace the "Planned" subsection with shipped status**

In `README.md`, find the heading `### Planned: \`mempalace-daemon\` adapter` and replace **everything from that heading up to and including the closing of "Why the existing adapter still has a use"** with:

```markdown
### Shipped: `mempalace-daemon` adapter

`sme/adapters/mempalace_daemon.py` talks to a running
[`palace-daemon`](https://github.com/jphein/palace-daemon) over HTTP.
No filesystem access, no ChromaDB import, no shared-process constraint
with the daemon. Use this adapter when MemPalace is fronted by the
daemon (the daemon is the single writer to the palace) — the existing
`mempalace` adapter is still correct for single-process upstream
installs without the daemon.

**Wired endpoints:**

- `query()` → `GET /search?q=…&kind=…&limit=…` with `X-API-Key`. Default
  `kind="content"` excludes Stop-hook auto-save checkpoints; pass
  `--kind all` to disable. Daemon-side `warnings` (e.g. broken HNSW
  index) are surfaced into `QueryResult.error` as `WARN: …` so Cat 9
  scoring can distinguish flagged retrieval from clean retrieval.
- `get_graph_snapshot()` → tries `GET /graph` first (palace-daemon
  ≥1.6.0); on 404, falls back to walking `mempalace_list_wings`,
  `mempalace_list_rooms` per wing, and `mempalace_list_tunnels` via
  `POST /mcp`.

**Auth resolution:** explicit `--api-url` / `--api-key` flags →
`~/.config/palace-daemon/env` (`PALACE_DAEMON_URL`, `PALACE_API_KEY`)
→ process environment.

**Invocation:**

```bash
sme-eval retrieve --adapter mempalace-daemon \
    --api-url http://your-daemon:8085 \
    --questions corpus.yaml \
    --kind content \
    --json out.json
```

If `--api-url` is omitted, the env file is read automatically.

#### Why the existing adapter still has a use

For users running upstream MemPalace without palace-daemon (the default
install pattern), the existing `mempalace` adapter is correct — single
process, no daemon, direct ChromaDB access is fine. The daemon adapter
is *additive*, for users who've adopted palace-daemon's single-writer
architecture.
```

- [ ] **Step 3: Sanity-check the README still renders cleanly**

Run: `python3 -c "import pathlib; print('len ok' if len(pathlib.Path('README.md').read_text()) > 1000 else 'EMPTY')"`

Expected: `len ok`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(readme): mempalace-daemon adapter — planned → shipped

Replaces the fork-roadmap planning subsection with the wired-endpoint
description, auth resolution rules, and invocation example.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Final sweep

- [ ] **Step 1: Full test suite**

Run: `pytest tests/ -v 2>&1 | tail -15`

Expected: every test green; integration tests SKIPPED unless the env var is set.

- [ ] **Step 2: Lint pass**

Run: `ruff check sme/adapters/mempalace_daemon.py tests/test_mempalace_daemon_adapter.py`

Expected: clean. Fix any issues inline; if there are any, recommit:

```bash
git add sme/adapters/mempalace_daemon.py tests/test_mempalace_daemon_adapter.py
git commit -m "$(cat <<'EOF'
chore: ruff fixes for mempalace_daemon adapter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Confirm git state is clean**

Run: `git status && git log --oneline -15`

Expected: working tree clean; ~7-9 commits ahead of `7b3bf4a` (the spec commit).

- [ ] **Step 4: Speak completion**

Run:

```bash
notify-send "sme-eval" "mempalace-daemon adapter shipped"
```

(If `mcp__speech-to-cli__speak` is available in the executing context, prefer:
`speak "mempalace-daemon adapter shipped" --voice en-US-Davis:DragonHDLatestNeural --quality hd`)

---

## Coverage check (cross-reference against the spec)

| Spec section | Implemented in task |
|---|---|
| §A constructor signature | Task 2 |
| §A auth resolution rules | Task 2 |
| §A `query()` happy path | Task 3 |
| §A `query()` warnings → soft error | Task 4 |
| §A `query()` error envelope | Task 3 + Task 4 |
| §A `get_graph_snapshot` /graph fast path | Task 5 |
| §A `get_graph_snapshot` MCP fallback | Task 6 |
| §A `get_ontology_source` | Task 7 |
| §A `ingest_corpus` raises | Task 7 |
| §B `/graph` endpoint on daemon | **OUT OF SCOPE — JP's daemon work** |
| §C `_load_adapter` branch | Task 8 |
| §C `--api-key`, `--kind` flags | Task 8 |
| §C make `--db` optional for retrieve | Already optional in CLI; verified Task 8 step 8 |
| Error-handling table | Tasks 3, 4, 6 |
| Unit testing | Tasks 2, 3, 4, 5, 6, 7 |
| Integration smoke (gated) | Task 9 |
| CLI smoke | Task 10 |
| README update | Task 11 |
