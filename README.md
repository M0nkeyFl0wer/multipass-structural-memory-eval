# multipass-structural-memory-eval

![Multi Pass. Mem Palace. A mockup of Leeloo Dallas's MULTI PASS ID card from The Fifth Element, stamped MEM PALACE where the issuing authority would normally appear, with the caption FREE PASS UNLOCK YOUR CREATIVITY ELIMINATES THE NEED TO REMEMBER EVERYTHING YOU'VE EVER TYPED.](docs/assets/issue_101_multipass_header.png)

**A diagnostic framework for memory systems** — RAG, knowledge graphs,
personal knowledge bases, conversational memory — that tests what the
system knows about its own structure, not just whether it can retrieve
memories.

> *"Multipass!"* — Leeloo, *The Fifth Element*. The name is a nod to a
> joke from an earlier MemPalace issue thread (visual reference above),
> and also to what the framework actually does: **multiple passes**
> over every memory system under test, across multiple corpus shapes
> and multiple retrieval conditions (A / B / C), so brittle default
> behaviours that hide on any single pass become visible when the
> readings are compared side by side.

## What this is

Standard memory benchmarks (LongMemEval, LoCoMo, MINE, GraphRAG-Bench,
BEAM) ask "can you find a memory?" That's necessary but not
sufficient. A filing cabinet can find a memory. The question is what
the **structure** of a memory system gives you beyond retrieval — and
whether your specific build, under your specific harness, with your
specific model, actually uses it.

SME defines a nine-category test menu. Categories 1–8 measure graph
structure and offline retrieval. Category 9 (The Handshake) measures
harness integration — whether the model actually reaches the memory
when it runs in production. Cats 1–8 are where every published
benchmark stops; Cat 9 is the gap every deployment engineer runs into.

Each category has a `Cat N` identifier (for code) and a descriptive
"palace-nod" name (The Lookup, The Stairway, The Blueprint, The
Handshake, and so on) so readable output doesn't require a lookup
table.

## Status

**Beta-level instrumentation, actively evolving.** Six adapters
(`flat-baseline`, `mempalace`, `mempalace-daemon`, `familiar`, `rlm`,
`ladybugdb`), two fully implemented categories, four CLI commands
(`retrieve`, `analyze`, `cat8`, `cat2c`), Cat 9b (call-through
success) scaffolding from upstream PR #1, and a specification for
the remaining seven. Diagnostic posture, not benchmark — the
defensible findings are before/after deltas under identical
conditions and within-system A/B/C ablations. Absolute recall
numbers inherit a substring-on-filename matcher with known biases.
See the [spec](docs/sme_spec_v8.md) and the [onboarding
guide](docs/ideas.md) for the full honest-limitations discussion.

## Install

```bash
pip install -e .
# Optional extras:
pip install -e ".[topology]"   # Ripser + python-louvain (for gap detection)
pip install -e ".[ladybugdb]"  # LadybugDB adapter
pip install -e ".[dev]"        # pytest, ruff
```

Installs as the Python package `sme-eval` with CLI entrypoint
`sme-eval`. The GitHub repo is `multipass-structural-memory-eval`;
the acronym **SME** (Structural Memory Evaluation) is used throughout
the documentation and code.

## Next steps

- **[`docs/ideas.md`](docs/ideas.md) — onboarding guide.** Start here
  if you want to run SME against your own memory system. Covers the
  nine-category menu, how to write an adapter for your backend, how
  to write a corpus from your own content, how to run the three
  implemented categories, and how to read what comes out the other
  end. This is also where the methodology framing lives — why A/B/C
  isolation matters, why multi-corpus testing is load-bearing, and
  why "the delta is the product, the levels are decoration."

- **[`docs/sme_spec_v8.md`](docs/sme_spec_v8.md) — full specification.**
  Precise category-by-category definitions, metric formulas, adapter
  interface contract, topology layer details, and the Cat 9 (The
  Handshake) harness-integration spec. Reference material — read the
  onboarding guide first if you want to get a test run going.

## Fork roadmap (jphein)

This is a fork; planned fork-specific work below. Upstream is
[M0nkeyFl0wer/multipass-structural-memory-eval](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval) — bug fixes and category contributions still target upstream.

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
  `POST /mcp`. The MCP fallback is slower (~30s on a 151K-drawer
  palace) but works against any palace-daemon version.

**Auth resolution:** explicit `--api-url` / `--api-key` flags →
`~/.config/palace-daemon/env` (`PALACE_DAEMON_URL`, `PALACE_API_KEY`)
→ process environment.

**Invocation:**

```bash
# With explicit daemon URL
sme-eval retrieve --adapter mempalace-daemon \
    --api-url http://your-daemon:8085 \
    --questions corpus.yaml \
    --kind content \
    --json out.json

# Or, if ~/.config/palace-daemon/env is populated, no flags needed
sme-eval retrieve --adapter mempalace-daemon --questions corpus.yaml
```

The same `--api-url` / `--api-key` / `--kind` flags work on the
`cat4`, `cat5`, and `check` subcommands.

**Why this matters:** the engram-2 critique ("0.984 R@5 but 17% E2E
QA accuracy") is about the integration-under-production-model slice
that Cat 9 measures. Running SME's `retrieve` through the daemon
surfaces exactly the kind of gap that critique describes — the
adapter's WARN-soft-error treatment means the framework records
"retrieval ran but the daemon flagged it as degraded" as a first-
class signal, not as a hard failure that hides the issue.

#### Why the existing adapter still has a use

For users running upstream MemPalace without palace-daemon (the
default install pattern), the existing `mempalace` adapter is
correct — single process, no daemon, direct ChromaDB access is
fine. The daemon adapter is *additive*, for users who've adopted
palace-daemon's single-writer architecture.

### Shipped: `familiar` adapter

`sme/adapters/familiar.py` talks to a running
[`familiar.realm.watch`](https://github.com/jphein/familiar.realm.watch)
v0.2.0+ instance over HTTP. Familiar wraps palace-daemon with a v0.2
retrieval pipeline (rerank, temporal decay, extractive compression,
grounding directives). This adapter measures familiar's full pipeline;
the sibling `mempalace-daemon` adapter measures palace alone.
**Comparing their SME scores quantifies what familiar's v0.2
pipeline contributes** to retrieval quality on top of the underlying
daemon.

**Wired endpoints:**

- `query()` → `POST /api/familiar/eval` with body
  `{query, limit, kind, mock}`. Familiar's eval endpoint already
  returns SME-shape `{answer, context_string, retrieved_entities,
  retrieved_edges, error, warnings, available_in_scope}` natively
  (it was designed against the SME contract), so the adapter is
  mostly deserialization with the same WARN: error-prefix
  translation as `mempalace-daemon`.
- `get_graph_snapshot()` → `GET /api/familiar/graph`. Familiar
  proxies palace-daemon's `/graph` with a 5-minute server-side cache;
  payload mapping reuses `sme/adapters/_graph_mapping.py` shared with
  `mempalace-daemon`.
- `get_harness_manifest()` → forward-compat for Cat 9. Returns
  `[ToolCall, MCPResource]` once `sme.harness` ships; `[]` until then.

**Determinism:** `--mock` (default) skips LLM inference so Cat 1
substring scoring is reproducible across runs. Use `--no-mock` to
include the model output in the per-question record (intended for
future Cat 9 work).

**Invocation:**

```bash
# Default: --mock for Cat 1 determinism
sme-eval retrieve --adapter familiar     --api-url https://familiar.jphe.in     --questions corpus.yaml     --json familiar.json

# Compare against the same palace via the daemon adapter
sme-eval retrieve --adapter mempalace-daemon     --api-url http://your-daemon:8085     --questions corpus.yaml     --json daemon.json

# The score delta = what familiar's v0.2 pipeline is worth
```

The `--api-url`, `--mock`/`--no-mock`, and `--familiar-timeout` flags
work on `cat4`, `cat5`, `check`, and `retrieve` subcommands.

### Shipped: `rlm` adapter

`sme/adapters/rlm_adapter.py` treats [RLM](https://github.com/jphein/rlm)
(a fork of [alexzhang13/rlm](https://github.com/alexzhang13/rlm)) as
the **read-side orchestrator** rather than a deterministic retrieval
pipeline. The LLM itself decides when to call `mempalace_search`,
with what queries, and how to compose results. `familiar`'s pipeline
is the *baseline* this adapter is benchmarked against, not the thing
it replaces.

**Design:** RLM gets `mempalace_search` registered as a `custom_tools`
callable. The adapter wraps that callable to capture every search
result into a per-query buffer; after `rlm.completion()` returns, the
buffer's contents become `context_string` (in tool-call order) and
`retrieved_entities` (one Entity per drawer). Same scoring contract
as every other adapter.

**Endpoint override:** `RLM_BASE_URL` / `RLM_MODEL` / `RLM_API_KEY`
env vars point the openai backend at any compatible endpoint —
local llama.cpp, hosted Llama 3.3 70B, anything OpenAI-shaped —
without touching the cloud-chat-assistant config-file fallback path.

**First two live readings on `jp-realm-v0.1` (30 questions):**

| Run | Mean recall | Tool-call distribution |
|---|---|---|
| rlm + Qwen 2.5 7B Q5_K_M | 46.67% | 25/30 zero-call, 2/30 used tool |
| rlm + Llama 3.3 70B | 46.67% | 22/30 zero-call, 8/30 used tool |
| familiar v0.3.9 (deterministic) | 78.33% | n/a |

Both RLM runs land at the same aggregate recall despite a 4×
difference in tool-invocation rate — they ceiling at the
orchestrator's willingness to invoke the tool, not at retrieval
quality. This is the data behind the [9a invocation-rate
issue](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval/issues/3)
filed upstream. See the [onboarding
guide](docs/ideas.md#rlmadapter--research-scaffold-2026-04-26) for
the full discussion and the per-question deltas.

**Invocation:**

```bash
RLM_BASE_URL=https://your-endpoint RLM_MODEL=llama-3.3-70b RLM_API_KEY=...     PALACE_DAEMON_URL=http://your-daemon:8085 PALACE_API_KEY=...     sme-eval retrieve --adapter rlm     --questions sme/corpora/jp_realm_v0_1/questions.yaml     --json baselines/rlm_$(date +%Y%m%d).json
```

## License

MIT. See [`LICENSE`](LICENSE).
