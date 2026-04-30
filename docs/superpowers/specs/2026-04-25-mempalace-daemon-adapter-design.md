# `mempalace-daemon` adapter — design

Date: 2026-04-25
Status: design (pre-implementation)
Spec author: Claude (with JP)

## Goal

Add a fork-specific `MemPalaceDaemonAdapter` that talks to a running
[`palace-daemon`](https://github.com/jphein/palace-daemon) over HTTP, so SME can
run Cat 4/5/8/9 against a live MemPalace install without violating the daemon's
single-writer invariant. The shipped `MemPalaceAdapter` opens ChromaDB directly
via `chromadb.PersistentClient`; that's incompatible with the daemon-strict
architecture (two `PersistentClient` instances against the same palace = the
multi-writer corruption case the daemon was built to prevent).

## Non-goals

- Replace the existing `MemPalaceAdapter`. It stays. New adapter is additive,
  for users who run the daemon. Documented in README.
- Bench against a seeded corpus. Daemon adapter is diagnostic-only (Mode B), same
  as the existing `MemPalaceAdapter`. `ingest_corpus` raises `NotImplementedError`.
- Replicate every projection the direct adapter offers. Drawer-level entities
  and per-source-file sibling edges are unreachable through the daemon API
  surface; the spec accepts a coarser snapshot for the daemon path.

## Why now

Verified on 2026-04-25 against the live 151K-drawer palace at
`disks.jphe.in:8085`:

- `/search?kind=content` already implements the README-roadmapped filter that
  excludes Stop-hook auto-save checkpoints. Default since 2026-04-25 in
  `palace-daemon` 1.5.1.
- `/search` with `q=memory&kind=content` produced `vector search unavailable:
  Error executing plan: Internal error: Error finding id` while `q=hello&kind=all`
  on the same daemon returned normal results. That's exactly the
  integration-under-production-model gap (engram-2 critique) Cat 9 is designed
  to catch — and an SME adapter is the right tool to characterise it.
- The four MCP tools the README's roadmap planned to use (`list_wings`,
  `list_rooms`, `list_tunnels`, `mempalace_kg_query`) work but are slow over
  HTTP — `list_wings` took ~30s on the 151K-drawer palace. `list_tunnels`
  returned `[]` while `/stats.tunnel_rooms` reported 9, indicating a real
  daemon-side inconsistency we should fix in passing.
- Adding a `/graph` REST endpoint on the daemon is a 30-40 line follow-on:
  parallel-gather of the four tools server-side plus a direct read of
  `~/.mempalace/knowledge_graph.sqlite3`, mirroring the existing `/stats`
  pattern at `palace-daemon/main.py:452-461`.

## Architecture

Three components, each independently understandable.

### Component A — `MemPalaceDaemonAdapter` (new file `sme/adapters/mempalace_daemon.py`)

Implements `SMEAdapter`. Single class, ~200-300 lines.

Constructor signature:

```python
class MemPalaceDaemonAdapter(SMEAdapter):
    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        env_file: Optional[str | Path] = None,    # default: ~/.config/palace-daemon/env
        kind: str = "content",                     # default kind for query()
        api_timeout: float = 180.0,
        prefer_graph_endpoint: bool = True,        # try GET /graph before MCP fallback
        # accepted for CLI parity, ignored:
        read_only: bool = True,
        db_path: Optional[str] = None,
    ): ...
```

Resolution rules for URL/key:

1. Explicit `api_url` / `api_key` kwargs win.
2. Else, parse `env_file` (default `~/.config/palace-daemon/env`) for
   `PALACE_DAEMON_URL` and `PALACE_API_KEY`. Trust mode 600 set by the daemon
   installer; do not warn on permissive modes (the daemon does that itself).
3. Else, read process env (`PALACE_DAEMON_URL`, `PALACE_API_KEY`).
4. If still missing, `ValueError` at construction with a message naming both
   `--api-url`/`--api-key` flags and `~/.config/palace-daemon/env`.

#### `query(question, *, n_results=5, kind=None, route=False)`

```
GET  {api_url}/search?q=<question>&limit=<n_results>&kind=<kind or self.kind>
hdr  X-API-Key: <api_key>
```

Daemon response envelope:

```json
{
  "query": "...",
  "filters": {"wing": null, "room": null},
  "total_before_filter": <int>,
  "available_in_scope": <int>,
  "warnings": ["..."],
  "results": [
    {"text": "...", "metadata": {"wing": "...", "room": "...", "source_file": "..."}, "score": ...}
  ]
}
```

Mapping to `QueryResult`:

- `context_string`: `[i] [wing/room] source_basename\ntext` per result. Format
  matches the existing `MemPalaceAdapter` so tiktoken counts (Cat 7 metric) are
  comparable across the two adapters and the flat baseline.
- `retrieved_entities`: one Entity per result, `id=f"drawer_hit:{i}"`,
  `entity_type=f"drawer:{room}"`, properties carry wing/room/score/source_file.
- `retrieval_path`: `[f"kind={chosen_kind}", f"available_in_scope={n}",
  f"total_before_filter={n}"]`.
- `warnings` from envelope: appended into `error` as `f"WARN: {'; '.join(warnings)}"`.
  Soft signal — does **not** zero out the result. This is the critical decision
  for Cat 9: a working-but-flagged response is different from a hard failure,
  and SME's scorecard already distinguishes "errored" from "answered wrong" in
  the per-question output (`sme/cli.py:782-832`).
- `error="NO_RESULTS"` if `results` is empty *and* warnings is empty.
- `route` kwarg: accepted for CLI signature parity with the existing
  `MemPalaceAdapter`. Ignored — the daemon does its own routing. Documented in
  the docstring.

Per-call timeout: `api_timeout` (default 180s). Connection/HTTP errors return
`QueryResult(error=...)`, never raise. Match the LadybugDB adapter's pattern
at `sme/adapters/ladybugdb.py:259-280`.

#### `get_graph_snapshot()`

Two-phase strategy:

1. **Fast path: `GET /graph`** (Component B below). If the daemon supports it
   (200 OK), parse the response and project to `(Entity, Edge)`. Done.
2. **Fallback path:** if `/graph` 404s (older daemons, upstream forks), call
   `mempalace_list_wings` once + `mempalace_list_rooms(wing=W)` per wing in
   sequence + `mempalace_list_tunnels` once via `POST /mcp`. KG entities/triples
   skipped in fallback (the MCP `kg_query` tool requires arguments we can't
   enumerate from outside).

Projection (matches the existing direct adapter's wing/room/tunnel layer at
`sme/adapters/mempalace.py:368-437`):

- `Entity(id=f"wing:{name}", entity_type="wing", ...)` per wing
- `Entity(id=f"room:{name}", entity_type=f"room:{primary_hall_or_untyped}",
  properties={wings: [...], drawer_count: n}, ...)` per room
- `Edge(member_of)` per (room, wing) pair
- `Edge(tunnel)` between every wing-pair sharing a room (matches `palace_graph`
  semantics)

When KG data is present (fast path only):

- `Entity(id=f"kg:{id}", entity_type=f"kg:{type}", ...)` per KG entity
- `Edge(source_id=f"kg:{subj}", target_id=f"kg:{obj}", edge_type=predicate, ...)`
  per triple, with confidence/source/valid_from in properties

The daemon path's snapshot is structurally **coarser** than the direct
adapter's: no per-drawer entities, no `same_file` sibling edges, no `filed_in`
edges. This is by design — `mempalace_list_drawers` exists, but iterating it
over HTTP for 151K drawers is impractical, and a per-drawer bulk endpoint is
out of scope for this work. Documented in the adapter docstring and surfaced
via `log.warning` on snapshot. If a future daemon ships a streaming
`/drawers` endpoint, the adapter can pick it up with no contract change.

#### `get_ontology_source()`

Returns the same `readme`-typed dict the existing `MemPalaceAdapter` returns at
`sme/adapters/mempalace.py:594-624`, so Cat 8 results are comparable across
the two adapters. The schema *as documented* doesn't change just because the
backend access path does.

#### `close()`

Releases nothing (no persistent connection). Safe to call multiple times.

### Component B — `GET /graph` on `palace-daemon`

> **Coordination note (2026-04-25):** JP is actively working on the
> `palace-daemon` repo. This spec describes the endpoint shape we want; the
> actual daemon-side change should be picked up by JP's current pass (or
> queued as a follow-up) rather than landed by SME-side work in parallel.
> The SME adapter ships and works without `/graph` (MCP fallback path),
> so the SME side does not block on the daemon side.

New endpoint, mirrors `/stats` (`palace-daemon/main.py:452-461`).

```python
@app.get("/graph")
async def graph(x_api_key: str | None = Header(default=None)):
    _check_auth(x_api_key)
    # Phase 1: parallel-gather the once-per-palace tools
    def call(tool, args):
        return _call({"jsonrpc": "2.0", "id": 1,
                      "method": "tools/call",
                      "params": {"name": tool, "arguments": args}})
    wings_resp, tunnels_resp, kg_stats_resp = await asyncio.gather(
        call("mempalace_list_wings", {}),
        call("mempalace_list_tunnels", {}),
        call("mempalace_kg_stats", {}),
    )
    wings = _unwrap(wings_resp).get("wings", {})
    # Phase 2: parallel list_rooms per wing
    room_responses = await asyncio.gather(*[
        call("mempalace_list_rooms", {"wing": w}) for w in wings
    ])
    rooms = [
        {"wing": w, "rooms": _unwrap(r).get("rooms", {})}
        for w, r in zip(wings, room_responses)
    ]
    # Phase 3: KG entities + triples via direct sqlite read
    kg_entities, kg_triples = _read_kg_direct()
    return {
        "wings": wings,
        "rooms": rooms,
        "tunnels": _unwrap(tunnels_resp),
        "kg_entities": kg_entities,
        "kg_triples": kg_triples,
        "kg_stats": _unwrap(kg_stats_resp),
    }
```

`_read_kg_direct()` opens `~/.mempalace/knowledge_graph.sqlite3` read-only from
inside the daemon process. Daemon already owns the palace SQLite — adding a
parallel KG read does not violate the single-writer invariant (KG is a separate
DB file from the ChromaDB persistent client; the daemon was the only thing
holding the file open already in code paths that touch it).

Bumps daemon `VERSION` from 1.5.1 → 1.6.0 (minor: additive endpoint).

#### Bonus fix (small, in scope): `list_tunnels` inconsistency

`/stats.tunnel_rooms` reports 9 for the live palace; `mempalace_list_tunnels`
returns `[]`. Investigate and fix as part of the same PR. Likely a stale-cache
or schema-shift bug in the MCP tool's implementation. The /graph endpoint
should not propagate that inconsistency.

### Component C — CLI plumbing

Touched files: `sme/cli.py`. No new files.

1. Extend `_load_adapter` to accept `mempalace-daemon` (and the alias
   `mempalace_daemon`):

   ```python
   if name in ("mempalace-daemon", "mempalace_daemon"):
       from sme.adapters.mempalace_daemon import MemPalaceDaemonAdapter
       for k in (
           "include_node_tables", "include_edge_tables", "auto_discover",
           "kg_path", "collection_name", "default_query_mode",
           "db_path",  # daemon adapter doesn't take a file path
       ):
           kwargs.pop(k, None)
       return MemPalaceDaemonAdapter(**kwargs)
   ```

2. Extend `_load_adapter_from_args` (`cli.py:437-456`) to thread `--api-url`,
   `--api-key`, and `--kind` (already done for `api_url`).

3. Add `--api-key` and `--kind` to `_add_db_or_api_args` (`cli.py:464-479`):

   ```python
   parser.add_argument("--api-key", default=None, metavar="KEY",
       help="API key for the daemon's X-API-Key header. Defaults to "
            "PALACE_API_KEY from ~/.config/palace-daemon/env when present.")
   parser.add_argument("--kind", default=None, metavar="KIND",
       help="(mempalace-daemon) /search kind filter. Defaults to "
            "'content'. Use 'all' to disable, 'checkpoint' to query "
            "auto-save snapshots only.")
   ```

4. Add the same flags to `cmd_retrieve`'s subparser (`cli.py:993-1056`).

5. Make `--db` optional for the `retrieve` and `analyze` subparsers so the
   daemon adapter doesn't have to pass a meaningless path. Already optional
   in `_add_db_or_api_args` for cat4/cat5/check.

## Data flow (one diagram)

```
sme-eval retrieve --adapter mempalace-daemon \
    --api-url http://disks.jphe.in:8085 --questions corpus.yaml --kind content
       │
       ▼
   cmd_retrieve  ─────────►  _load_adapter("mempalace-daemon", api_url=..., api_key=..., kind="content")
                                   │
                                   ▼
                             MemPalaceDaemonAdapter.__init__
                                   │  resolves api_url, api_key from env file if needed
                                   ▼
                             query(question)  ──► GET /search?q=...&kind=content
                                                       │
                                                       ▼ X-API-Key header
                                                  palace-daemon FastAPI
                                                       │
                                                       ▼
                                                  mempalace_search MCP tool
                                                       │
                                                       ▼
                                                  ChromaDB (kind filter applied
                                                  pre-vector by daemon code)
                                                       │
                                                       ▼ envelope w/ warnings
                                              QueryResult{context_string, error="WARN:..."}
                                                       │
                                                       ▼
                                              cmd_retrieve scoring loop
                                                       │
                                                       ▼
                                              JSON output (--json) for cat2c
```

## Error handling

| Failure | Adapter response |
|---|---|
| No `api_url` (no flag, no env file, no env var) | `ValueError` at construction |
| Connection refused / DNS fail | `QueryResult(error="CONNECTION: ...")` |
| HTTP 401/403 | `QueryResult(error="AUTH: invalid X-API-Key")` |
| HTTP 5xx | `QueryResult(error=f"HTTP {code}: {body[:200]}")` |
| Daemon `warnings` non-empty | `QueryResult(error="WARN: ...")` — soft signal |
| Empty `results` and empty `warnings` | `QueryResult(error="NO_RESULTS")` |
| `/graph` returns 404 | log warning, fall back to MCP tool path |
| MCP timeout (>180s) on `list_wings` | log warning, return partial snapshot (whatever wings/rooms succeeded) |
| `list_rooms` for one wing fails | skip that wing's rooms, continue |
| Env file unreadable | log warning, fall through to env vars |

The "WARN: ..." in `error` for present-but-flagged responses is the load-bearing
choice. The existing `cmd_retrieve` flow at `cli.py:782-829` records the error
field in the JSON output but still uses `recall` from the substring match —
which means SME can score Cat 9 even when the daemon reports "vector search
unavailable", and the report distinguishes warning-tagged hits from clean ones.
Cat 9's whole point is to surface integration-under-production-model gaps; the
warnings ARE that signal.

## Testing

### Unit tests

New file `tests/test_mempalace_daemon_adapter.py`:

- `test_resolve_from_env_file_when_no_kwargs`: temp env file with the two vars,
  no kwargs → adapter resolves both
- `test_explicit_kwargs_win_over_env_file`
- `test_query_success`: mock urlopen returns canned envelope, assert
  `context_string` format and `retrieval_path`
- `test_query_warnings_emit_soft_error`: envelope with non-empty warnings
  produces `error.startswith("WARN:")` *and* keeps `context_string` populated
- `test_query_no_results_returns_no_results_error`
- `test_query_auth_error`: mocked HTTPError 401 → `error.startswith("AUTH:")`
- `test_query_connection_error`: URLError → `error.startswith("CONNECTION:")`
- `test_get_graph_snapshot_via_graph_endpoint`: mock /graph response
- `test_get_graph_snapshot_falls_back_to_mcp_on_404`
- `test_get_graph_snapshot_partial_on_mcp_timeout`

Mock pattern: monkeypatch `urllib.request.urlopen` with a callable returning a
context-manager-shaped object. Same pattern the existing test suite would use
if it had any (it doesn't yet — the LadybugDB API path isn't unit-tested either,
which is itself a gap, but out of scope here).

### Integration smoke (gated)

`tests/test_mempalace_daemon_integration.py`, gated on:

```python
@pytest.mark.skipif(
    not os.environ.get("PALACE_DAEMON_URL"),
    reason="needs a running palace-daemon",
)
```

- `test_query_returns_query_result`: `query("hello")` returns a `QueryResult`
- `test_get_graph_snapshot_returns_at_least_one_wing`
- `test_kind_content_default_is_applied`: same query under `kind="all"` and
  `kind="content"` produces different `total_before_filter` counts (validates
  the README's filter claim)

### Daemon-side test (palace-daemon repo)

A unit test for the new `/graph` endpoint following the existing test-style
in palace-daemon's tests directory. Out of scope for the SME repo's CI but
tracked as an explicit deliverable in the implementation plan.

### CLI smoke

```bash
sme-eval retrieve --adapter mempalace-daemon \
    --questions tests/fixtures/tiny_corpus.yaml --json /tmp/out.json
```

Should produce a JSON output with one record per question, no exceptions
raised even when the daemon emits warnings. Tested against a small
local-mock-server fixture (existing test infrastructure has none — we add a
minimal fixture as part of this work).

## Build sequence (sketch — full plan in writing-plans output)

1. Add `MemPalaceDaemonAdapter` with MCP-fallback graph path (no `/graph`
   dependency yet). All unit tests pass.
2. Wire CLI: `_load_adapter` branch + `--api-key` + `--kind` flags. Smoke-test
   `retrieve` against the live daemon; capture before-state baseline JSON.
3. Update README: replace the "planned" roadmap section with a "shipped"
   section pointing at the adapter, the `--kind` flag, and example invocations.
   Note that `/graph` fast path is pending the daemon side.
4. **(Daemon-side, JP-driven, separate session/PR)** Add `/graph` endpoint to
   palace-daemon, plus `list_tunnels` consistency fix. Bump daemon to 1.6.0.
   Deploy.
5. **(SME-side follow-up)** Adapter `prefer_graph_endpoint=True` becomes the
   default fast path once 1.6.0 is live; MCP fallback retained. Re-run smoke;
   capture after-state baseline.

Steps 1-3 are the SME-fork-only deliverable for this spec. They ship the
adapter against the existing daemon (`palace-daemon` 1.5.1) using the MCP
fallback path — slower for cat4/5/check but functionally complete.
Steps 4-5 are coordinated work tied to JP's current daemon changes.

## Open questions

None blocking. Three minor points the implementation will resolve in passing:

- Exact response shape for `mempalace_list_tunnels` once the inconsistency is
  fixed (the empty-list response we get today is wrong, but we don't yet know
  what right looks like — clarified during step 3).
- Whether `kg_query` requires a subject filter or supports a "list all triples"
  mode. If not, the daemon-side direct sqlite read path is the only way.
  The /graph endpoint takes that path regardless, so this doesn't block the
  adapter.
- Whether to add an `sme-eval cat9` subcommand as part of this work. Spec v8's
  Cat 9 is the harness-integration test that motivates this whole adapter.
  Out of scope for this design; the `retrieve` subcommand already runs the
  measurements that Cat 9's scoring would consume. Cat 9 itself is a separate
  spec.
