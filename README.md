# multipass-structural-memory-eval

**A diagnostic framework for memory systems** — RAG, knowledge graphs,
personal knowledge bases, conversational memory — that tests what the
system knows about its own structure, not just whether it can retrieve
memories.

## Contents

[What this is](#what-this-is) · [Status](#status) ·
[In production](#in-production) · [Install](#install) ·
[Next steps](#next-steps) · [Adapters](#adapters)

## What this is

See the [nine-category menu](docs/ideas.md#who-should-run-which-categories)
for what each test measures and which to run for your setup.

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
(`flat`, `mempalace`, `mempalace-daemon`, `familiar`, `ladybugdb`,
`full-context`), nine CLI commands (`retrieve`, `analyze`, `cat8`,
`cat2c`, `cat4`, `cat5`, `check`, `cat9`, `compile-wiki`), Cat 4
and Cat 5 partially implemented, and a specification for the
remaining categories.
Diagnostic posture, not benchmark — the defensible findings are
before/after deltas under identical conditions and within-system
A/B/C ablations. See the [spec](docs/sme_spec_v8.md) and the
[onboarding guide](docs/ideas.md) for the full honest-limitations
discussion.

## In production

**Built with it, maintained by it.** SME started in the [MemPalace
issue thread](https://github.com/MemPalace/mempalace/issues/101) that
proposed it (hence *Multipass* — make multiple passes over a
memory system and compare), and it's the instrument the author **built
a live LadybugDB knowledge graph with**. That graph is a working
testbed for a **mix of ingestion methodologies** on unstructured data —
different extractors and enrichment passes, run as bake-offs to see
which leaves the structure healthier. SME is the measurement layer for
that experiment: not a post-hoc audit of a finished graph, but the
readout that shows, run after run, what each methodology costs
structurally and what still needs doing.

It runs **nightly via a systemd timer**, reading a snapshot copy so it
never fights the graph's writers. The before/after delta across dated
readings is the product, and the trend is the point:

| Reading | Entities | In largest component | Isolates |
|---|---|---|---|
| 2026-05-11 | 161,312 | 4.9% | 94.8% |
| 2026-05-16 | 176,854 | 5.6% | 94.2% |
| 2026-05-24 | 188,535 | 7.0% | 92.7% |
| 2026-05-28 | 206,330 | 11.6% | 87.4% |

Connectivity more than doubled and the isolate fraction fell ~7 points
**while the graph grew by more than a quarter** — structure improving
faster than the graph accretes, as the ingestion methodology gets tuned against
SME's readings. The absolute levels are still high: a graph mixing
extraction methods carries orphans until the methodology settles.
That's the honest state, and the trend is the signal.

Its job has shifted from construction toward upkeep — three roles,
every night:

- **Hold the pattern** — confirm the ontology and edge discipline
  haven't quietly regressed as new content and new extractors land.
- **Find knowledge gaps to fill** — Cat 5 surfaces candidate "missing
  rooms": pairs of populated regions that share a rare entity type but
  have no edge between them — a connection the graph *should* have and
  doesn't.
- **Prevent drift** — a metric moving the wrong way is an early warning,
  long before retrieval quality visibly degrades.

(One signal still being worked: ~50% canonical ID collisions —
duplicate IDs from un-normalized name hashing — newly instrumented this
week, so no trend line yet; the next methodology iteration targets it.)

These are structural signals that pure retrieval metrics (Recall@K)
can't see — and the kind a graph owner can act on.

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

**Quick start:** run your first diagnostic in 5 minutes with the
[onboarding guide](docs/ideas.md#quickstart-your-first-diagnostic-run).
Need the spec? Start at [docs/sme_spec_v8.md](docs/sme_spec_v8.md).

## Next steps

- **[`docs/ideas.md`](docs/ideas.md) — onboarding guide.** Start here
  if you want to run SME against your own memory system. Covers the
  nine-category menu, how to write an adapter for your backend, how
  to write a corpus from your own content, how to run the implemented
  categories, and how to read what comes out the other end. This is
  also where the methodology framing lives — why A/B/C isolation
  matters, why multi-corpus testing is load-bearing, and why "the
  delta is the product, the levels are decoration."

- **[`docs/sme_spec_v8.md`](docs/sme_spec_v8.md) — full specification.**
  Precise category-by-category definitions, metric formulas, adapter
  interface contract, topology layer details, and the Cat 9 (The
  Handshake) harness-integration spec. Reference material — read the
  onboarding guide first if you want to get a test run going.

- **[`docs/cross_validation_2026.md`](docs/cross_validation_2026.md) —
  current work.** Cross-validation of SME categories against
  LongMemEval / MemoryBench, Karpathy-condition D baselines (full-
  corpus-in-context), and first readings from the live benchmark
  harness. Active development; this is where near-term SME findings
  land.

- **[`docs/industry_standards_integration.md`](docs/industry_standards_integration.md)
  — integration audit.** Survey of where SME rolls its own vs. where
  battle-tested standards exist (SHACL, PROV-O, OpenLineage, B-Cubed,
  Ripser). Constitutional principle: SME stays lightweight and locally
  runnable — no server hosting required.

## Adapters

SME ships adapters for several memory systems. Each adapter teaches
the framework to speak the wire protocol of a specific system so the
same eval questions can run across multiple backends. Adapters live in
`sme/adapters/` and implement the `SMEAdapter` ABC.

### `mempalace-daemon` — by [jphein](https://github.com/jphein)

`sme/adapters/mempalace_daemon.py` talks to a running
[`palace-daemon`](https://github.com/jphein/palace-daemon) over HTTP —
by [`jphein`](https://github.com/jphein). No filesystem access, no
ChromaDB import, no shared-process constraint with the daemon. Use
this adapter when MemPalace is fronted by the daemon (the daemon is
the single writer to the palace) — the existing `mempalace` adapter
is still correct for single-process upstream installs without the
daemon.

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

### familiar — by [jphein](https://github.com/jphein)

[`familiar.realm.watch`](https://github.com/jphein/familiar.realm.watch)
is a retrieval pipeline that wraps palace-daemon with reranking,
temporal decay, extractive compression, and grounding directives.
`[jphein](https://github.com/jphein)` built it; `sme/adapters/familiar.py`
lets SME measure its full end-to-end contribution on top of the raw
daemon. The sibling `mempalace-daemon` adapter measures palace alone —
running both on the same corpus shows what the pipeline layer adds.

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

### `ladybugdb` — embedded graph databases

`sme/adapters/ladybugdb.py` reads any
[LadybugDB](https://github.com/LadybugDB) `.ldb` graph, and it's
**schema-agnostic** by design: point it at a graph and it introspects
the node and relationship tables (`SHOW_TABLES`, `TABLE_INFO`,
`SHOW_CONNECTION`) and builds the projection queries on the fly — no
per-graph configuration, whatever ontology the graph happens to use. It
auto-detects both edge-table styles seen in the wild:

- **Consolidated** — a few rel tables (e.g. `ENTITY_TO_ENTITY`) with an
  `edge_type` property discriminating the semantic type.
- **Per-type** — many rel tables, one per semantic type, where the
  table name *is* the edge type.

Two independent access paths: **file mode** (`--db path/to/graph.ldb`,
read-only, required for `get_graph_snapshot()` and the structural
probes) and **API mode** (`--api-url`, wires `query()` to a running
`/search` endpoint for systems with writer-lock contention on the file).
Because file mode takes a read-only open, point it at a **backup or
snapshot copy** when a live writer (a daemon, an enrich pass) holds the
graph — a direct open will otherwise block on the writer lock.

```bash
# Structural health check on a LadybugDB graph (entity↔entity slice)
sme-eval check --adapter ladybugdb \
    --db /path/to/graph.ldb \
    --edge-tables ENTITY_TO_ENTITY \
    --json reading.json
```

## About the name

![Multi Pass. Mem Palace. A mockup of Leeloo Dallas's MULTI PASS ID card from The Fifth Element, stamped MEM PALACE where the issuing authority would normally appear, with the caption FREE PASS UNLOCK YOUR CREATIVITY ELIMINATES THE NEED TO REMEMBER EVERYTHING YOU'VE EVER TYPED.](docs/assets/issue_101_multipass_header.png)

> *"Multipass!"* — Leeloo, *The Fifth Element*. The name is a nod to
> this projects roots in a MemPalace issue thread https://github.com/MemPalace/mempalace/issues/101 (much respect to https://github.com/milla-jovovich). The name also captures what the framework actually does: **multiple passes**
> over every memory system under test, across multiple corpus shapes
> and multiple retrieval conditions (A / B / C), so brittle default
> behaviours that hide on any single pass become visible when the
> readings are compared side by side.

## License

MIT. See [`LICENSE`](LICENSE).
