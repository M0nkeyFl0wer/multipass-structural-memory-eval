# `familiar` adapter — design

Date: 2026-04-26
Status: design (pre-implementation)
Spec author: Claude (with JP)

## Goal

Add `FamiliarAdapter` to multipass — a fifth `SMEAdapter` implementation that
talks to a running [`familiar.realm.watch`](https://github.com/jphein/familiar.realm.watch)
v0.2.0+ instance over HTTP. Familiar is a TS+Bun chat surface that wraps
palace-daemon with a v0.2 retrieval pipeline (rerank + decay + compress +
grounding directives). The adapter measures **familiar's full pipeline**, not
just the underlying palace.

The adapter is sibling to `MemPalaceDaemonAdapter` (shipped 2026-04-25). Both
target the same palace; the difference is the layer above it. Comparing their
SME scores measures what familiar's v0.2 pipeline is worth.

## Non-goals

- **Cat 9 implementation.** Familiar's v0.2 already emits the full
  `HandshakeTrace`-shaped data per turn (verified: chunk D's `Trace`
  abstraction + `?trace=1` SSE event includes `query`, `retrieved`,
  `context_string`, `answer`, `citations`, `warnings`, `duration_ms`).
  The `cmd_retrieve` JSON output records all of this per-question. A future
  `sme/categories/handshake.py` scorer can compute 9a-9d from the existing
  per-question records. **Out of scope here:** building that scorer.
  In scope: making sure the adapter emits enough data that the future
  scorer doesn't need to revisit the adapter API.
- **Replace `MemPalaceDaemonAdapter`.** It stays. The two adapters answer
  different questions (palace alone vs palace + v0.2 pipeline). Both are
  diagnostic; neither replaces the other.
- **Bench against a seeded corpus** (Mode A). Familiar reads palace data
  it didn't author. Like the daemon adapter, this is Mode B (diagnostic
  on a live install). `ingest_corpus` returns a stub.
- **Inference-mode runs.** Cat 1's substring scoring is deterministic only
  when the LLM doesn't write the answer. Adapter defaults to `mock=true`
  so retrieval scoring is reproducible. Inference-mode runs are reserved
  for a future Cat 9 pass that scores answer text against expected
  drawer hits via the same multipass LLM-judge pipeline (Cats 1, 7).

## Why now

Verified 2026-04-26 against `https://familiar.jphe.in/`:

- `POST /api/familiar/eval` returns the full SME-`QueryResult` shape
  natively. Familiar's v0.2 was designed around this contract (Phase 5
  of its v0.2 plan, written 2026-04-24). No translation layer needed —
  the adapter is mostly deserialization.
- `GET /api/familiar/graph` proxies the daemon's `/graph` with a 5-min
  cache. Reuse `MemPalaceDaemonAdapter`'s graph-snapshot mapping helpers
  verbatim (the underlying `/graph` payload shape is identical because
  familiar passes it through unchanged).
- Familiar's v0.2 pipeline is now live in production with real palace
  recall (post-rebuild 2026-04-25). The retrieval-quality delta vs.
  `MemPalaceDaemonAdapter` is the single most operationally useful number
  we don't have yet — without it we cannot say whether v0.2's
  rerank/decay/compress chain is actually worth its complexity.
- Familiar v0.2 also surfaces the warnings array directly from search
  through to the eval response. The `low_confidence`,
  `filtered_null_text_N`, `palace_unreachable`, `stuck_loop` warnings
  characterise *operational degradations* of the chat surface — exactly
  the production-integration gaps Cat 9 will eventually surface.
  Capturing them per-question now prepares for that.

## Adapter positioning

```
+-----------------------+----------------------------------------------------+
| SME adapter family                                                         |
+-----------------------+----------------------------------------------------+
| flat_baseline.py      | no structure, no graph                             |
| ladybugdb.py          | alt graph DB, baseline                             |
| mempalace.py          | palace as a Python library (multi-writer risk)     |
| mempalace_daemon.py   | palace via the daemon's HTTP API (single-writer    |
|                       |   safe; what runs against live disks)              |
| familiar.py NEW       | palace via daemon + v0.2 pipeline                  |
+-----------------------+----------------------------------------------------+
```

`mempalace_daemon` answers *"how good is the palace's recall on this corpus?"*
`familiar` answers *"how good is the palace's recall **after familiar's
pipeline acts on it**?"* Both target the same backing data.

## Components

### 1. `sme/adapters/familiar.py` — the adapter (~400 lines)

```python
class FamiliarAdapter(SMEAdapter):
    DEFAULT_BASE_URL = "http://familiar:8080"
    DEFAULT_TIMEOUT_S = 30.0

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        mock_inference: bool = True,
        opener: Callable | None = None,  # for fake_urlopen_factory tests
    ): ...
```

Three required methods + two optional + one Cat-9 forward-compat optional.

#### `ingest_corpus(corpus)` — no-op stub

Return:

```python
{
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

Same idiom as `MemPalaceDaemonAdapter`. Multipass's CLI tolerates this
(checked in `cmd_ingest` of `cli.py`).

#### `query(question)` returns `QueryResult`

`POST /api/familiar/eval` with body:

```json
{
  "query":  "<question, sliced to 250 chars>",
  "limit":  5,
  "kind":   "content",
  "mock":   true
}
```

Response shape (per familiar v0.2's `SmeQueryResponse`):

```json
{
  "answer":             "(stub when mock=true)",
  "context_string":     "<verbatim system prompt familiar would send>",
  "retrieved_entities": [SmeEntity, ...],
  "retrieved_edges":    [],
  "error":              null,
  "warnings":           ["low_confidence", "filtered_null_text_1", ...],
  "available_in_scope": 151478
}
```

Adapter deserialization rules:

| field on the wire | maps to `QueryResult` field | rules |
|---|---|---|
| `answer` | `answer` | verbatim |
| `context_string` | `context_string` | verbatim — multipass tiktoken-counts this for Cat 7 |
| `retrieved_entities` | `retrieved_entities` (list[Entity]) | each `SmeEntity` becomes `Entity(id, name=id, entity_type="drawer", properties={wing, room, topic, content_snippet, cosine, bm25, matched_via, provenance})` |
| `retrieved_edges` | `retrieved_edges` | empty in v0.2; map directly |
| `error` | `error` | verbatim — `None` when null |
| `warnings` non-fatal | append to `error` | format: `error or "" + " WARN: " + "; ".join(warnings)` so non-fatal signals reach the per-question record without zeroing out the result |
| `warnings` containing `palace_unreachable` | `error = "WARN: palace_unreachable"` | hard signal — palace was down for this turn |
| HTTP non-2xx | `error = f"familiar endpoint {status}: {body[:200]}"` | no exception propagation |
| network/timeout | `error = f"familiar timeout after {timeout_s}s"` | no retries |

Setting `error` instead of raising is the SMEAdapter contract — `cmd_retrieve`
distinguishes "errored" from "answered wrong" in the per-question scorecard.

#### `get_graph_snapshot()` returns `(list[Entity], list[Edge])`

`GET /api/familiar/graph`. Familiar proxies the palace-daemon `/graph`
endpoint with a 5-min cache. The payload shape is identical to what
`MemPalaceDaemonAdapter` already maps:

```json
{
  "wings":       {"<wing_name>": <drawer_count>, ...},
  "rooms":       [{"wing": "...", "rooms": {"<room>": <count>}}, ...],
  "tunnels":     [{"room": "...", "wings": [...]}, ...],
  "kg_entities": [{"id", "name", "type", "properties": {...}}, ...],
  "kg_triples":  [{"subject", "predicate", "object", ...}, ...],
  "kg_stats":    {"entities": int, "triples": int}
}
```

**Implementation:** extract the `MemPalaceDaemonAdapter`'s mapping helpers
into a shared module (`sme/adapters/_mempalace_graph.py`) and reuse them
verbatim. Don't fork the mapping; if the upstream `/graph` shape evolves,
both adapters should follow.

On HTTP failure or 5xx: return `([], [])` and log a warning. Cat 5/8 score
0 for that run, which is the expected SME behavior for a missing snapshot.

#### `get_flat_retrieval(question, k)` (optional)

`POST /api/familiar/eval` with `mock=true`, `limit=k`. Return only
`retrieved_entities` (no answer, no context_string). Used by SME's
flat-baseline comparison passes (Cat 7 token-budget analysis).

#### `get_ontology_source()` (optional)

Returns `"declared"`. Familiar reads palace taxonomy via
`mempalace_get_taxonomy` MCP tool — wings/rooms are author-declared, not
inferred. Same semantics as `MemPalaceDaemonAdapter`.

#### `get_harness_manifest()` (optional, Cat 9 forward-compat)

```python
def get_harness_manifest(self) -> list[HarnessDescriptor]:
    """Familiar exposes two invocation surfaces — describe both for
    future Cat 9 cross-harness comparison."""
    return [
        ToolCall(
            name="familiar_query",
            json_schema=...,
            backend_endpoint=f"{self.base_url}/api/familiar/eval",
        ),
        MCPResource(
            server_url=f"{self.base_url}/mcp",
            resource_uri_pattern="familiar_recall|familiar_reflect|familiar_chat",
        ),
    ]
```

Returns `[]` if `HarnessDescriptor` isn't importable (older multipass).
This is the only forward-looking method in the adapter — when Cat 9
ships, this manifest tells multipass which harnesses to exercise.

### 2. CLI wiring — `sme/cli.py`

Mirror `--adapter mempalace-daemon` flag:

```bash
sme-eval retrieve \
    --adapter familiar \
    --base-url https://familiar.jphe.in \
    --questions corpora/<your-corpus>.yaml \
    --json scores.json \
    [--mock | --no-mock]   # default --mock for Cat 1 determinism
    [--timeout 30.0]
```

`--adapter familiar` instantiates `FamiliarAdapter(base_url=..., timeout_s=...,
mock_inference=...)`. Default base URL is `http://familiar:8080` to support
LAN runs from disks/katana without needing TLS.

### 3. README + docs

- Add familiar to the README adapter table (matching the row format used
  for mempalace-daemon).
- Add a "Running familiar adapter" subsection to README's Quickstart,
  parallel to the existing daemon-adapter section.
- Update `docs/ideas.md` to reflect that familiar supplies the adapter
  layer of the eventual Cat 9 implementation; the per-question JSON
  output already captures the data the future scorer will consume.

## Data flow (per `query()`)

```
multipass cli              FamiliarAdapter           familiar-api          palace-daemon
sme-eval retrieve              query()                eval endpoint         /search /graph
                                  |                        |                     |
   |-- question ---------------> |                        |                     |
   |                              |-- POST  ------------> |                     |
   |                              |   {query,             |-- /search?kind=...->|
   |                              |    mock=True,         |<-- results ---------|
   |                              |    limit=5}           |  rerank+decay+      |
   |                              |                        |  compress+grounding|
   |                              |<-- {answer (stub),  --|                     |
   |                              |      context_string,                        |
   |                              |      retrieved_entities,                    |
   |                              |      retrieved_edges,                       |
   |                              |      warnings, error}                       |
   |                              |  deserialize+map                             |
   |<-- QueryResult ------------- |                                              |
   |                                                                              |
   |-- question N ------------>  ... (no batching; one HTTP call per question)
```

`mock=true` is the default. Cat 1 scoring is deterministic under it because
no LLM runs. The retrieval pipeline (rerank, decay, compress) is fully
deterministic given the same palace state.

## Error handling matrix

| condition | adapter behavior |
|---|---|
| HTTP 4xx/5xx from familiar-api | `QueryResult(error=f"familiar endpoint {status}: {body[:200]}", context_string="", retrieved_entities=[], retrieved_edges=[])` |
| Network timeout (`timeout_s`) | `QueryResult(error=f"familiar timeout after {timeout_s}s", ...)` |
| Connection refused / DNS | `QueryResult(error=f"familiar connection failed: {e}", ...)` |
| Response body not valid JSON | `QueryResult(error="familiar: invalid JSON response", ...)` |
| `error` field non-null in response | Pass through verbatim |
| `warnings` array contains `palace_unreachable` | Treat as adapter-level error; set `error = "WARN: palace_unreachable; ..."` |
| `warnings` array contains `low_confidence` / `filtered_null_text_*` / `stuck_loop` | Append `WARN: <list>` to `error` (warnings AND data — not fatal) |
| `get_graph_snapshot()` HTTP failure | Return `([], [])` + log warning |
| Auth failure (palace key wrong/expired upstream) | Familiar returns 502 + structured error; pass through |
| Adapter init: invalid `base_url` | `ValueError` at construction time, not at first query |

**No retries.** SME runs are reproducible only when each query is one shot.
If reproducibility wants retry, multipass core adds it — adapters don't.

## Testing

Mirror `tests/adapters/test_mempalace_daemon_adapter.py` structure:

### `tests/adapters/test_familiar_adapter.py` — unit (mocked HTTP)

- `test_query_happy_path` — `fake_urlopen_factory` returns SME-shape JSON;
  verify deserialize result has all fields populated correctly.
- `test_query_propagates_warnings` — warnings array becomes `error` field with
  `WARN:` prefix; `retrieved_entities` still populated (warning is soft).
- `test_query_palace_unreachable_is_hard_error` — when `warnings` contains
  `palace_unreachable`, error reflects it; result is "errored", not
  "answered wrong".
- `test_query_http_4xx` — status code surfaced in error string.
- `test_query_http_5xx` — same.
- `test_query_timeout` — error string format.
- `test_query_invalid_json` — error contract.
- `test_query_default_mock_inference_is_true` — Cat 1 determinism guarantee.
- `test_query_explicit_mock_false_passes_through` — for future Cat 9 work.
- `test_get_graph_snapshot_maps_palace_graph` — JSON to Entity/Edge mapping;
  reuses the shared mapping helpers (test directly against the shared
  module rather than re-asserting in both adapters).
- `test_get_graph_snapshot_failure_returns_empty` — error contract.
- `test_ingest_corpus_is_noop` — returns expected stub.
- `test_get_harness_manifest_returns_two_descriptors` — gated by
  `HarnessDescriptor` importability.

### `tests/adapters/test_familiar_live.py` — gated live smoke

- `@pytest.mark.skipif(os.environ.get("FAMILIAR_BASE_URL") is None, ...)`
- One `query()` against the actual deployed instance with a known-recall
  question (e.g. "what realm projects exist"). Asserts non-empty
  `retrieved_entities` (or graceful skip if palace HNSW is rebuilding).
- One `get_graph_snapshot()`. Asserts non-empty entities + edges.

Same pattern as `MemPalaceDaemonAdapter`'s gated live test.

### Reuse `fake_urlopen_factory`

The fixture `tests/adapters/fake_urlopen_factory.py` was added with the
daemon adapter (commit `2376900`). Reuse it for familiar adapter mocking.

## Open questions

1. **Should the adapter expose `?trace=1` data in `QueryResult`?**
   `/v1/chat/completions?trace=1` returns a richer Trace including
   `inference_endpoint`, `duration_ms`, and `citations`. For Cat 1
   (`mock=true`, no chat path), this is unavailable. For future Cat 9
   inference-mode runs, the adapter could call `/v1/chat/completions?trace=1`
   instead of the eval endpoint to capture per-turn telemetry. **Decision
   for this spec:** out of scope. Cat 1 runs through the eval endpoint;
   when Cat 9 ships, an inference-mode flag on the adapter will switch to
   the chat path. Spec the seam, defer the implementation.
2. **Should the adapter expose familiar's `inference_endpoint` field
   (which provider served the response)?** Not in the v0.2 SmeEntity shape;
   would need a separate trace fetch. Skip for v1 of the adapter; revisit
   when Cat 9 needs per-model sensitivity (9e).
3. **Should `mock=true`/`mock=false` be an SME-CLI flag rather than a
   constructor arg?** Both. CLI flag overrides constructor default.
   Convention: `--mock` / `--no-mock`, default `--mock`.

## Acceptance criteria

- `from sme.adapters.familiar import FamiliarAdapter` succeeds.
- `pytest tests/adapters/test_familiar_adapter.py` — all green.
- `pytest tests/adapters/test_familiar_live.py` skips cleanly when
  `FAMILIAR_BASE_URL` is unset; passes when set against a healthy familiar.
- `sme-eval retrieve --adapter familiar --base-url http://familiar:8080
  --questions corpora/standard_v0_1/questions.yaml --json /tmp/run.json`
  produces a non-empty per-question JSON output.
- README adapter table includes familiar with the same row schema as
  mempalace-daemon.

## Implementation outline (for the plan)

1. Extract `MemPalaceDaemonAdapter`'s `/graph` mapping into
   `sme/adapters/_mempalace_graph.py`. Shared between daemon + familiar.
2. Scaffold `sme/adapters/familiar.py` with class skeleton + constructor
   + reuse of fake_urlopen_factory.
3. Implement `query()` with happy path; tests.
4. Implement error handling for 4xx/5xx/timeout/JSON-malformed; tests.
5. Implement `warnings` translation rules (hard vs soft signals); tests.
6. Implement `get_graph_snapshot()` via the shared module; tests.
7. Implement `get_flat_retrieval()`, `get_ontology_source()`,
   `get_harness_manifest()`; tests for each.
8. Wire `--adapter familiar` and `--mock`/`--no-mock` flags in `cli.py`.
9. Live smoke test (gated); README + ideas.md updates.
10. PR.

Plan will follow this in `docs/superpowers/plans/2026-04-26-familiar-adapter.md`.
