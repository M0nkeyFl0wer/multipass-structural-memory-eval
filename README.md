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

**Beta-level instrumentation, actively evolving.** Three adapters,
two fully implemented categories, four CLI commands (`retrieve`,
`analyze`, `cat8`, `cat2c`), and a specification for the remaining
seven. Diagnostic posture, not benchmark — the defensible findings
are before/after deltas under identical conditions and within-system
A/B/C ablations. Absolute recall numbers inherit a substring-on-
filename matcher with known biases. See the [spec](docs/sme_spec_v8.md)
and the [onboarding guide](docs/ideas.md) for the full honest-
limitations discussion.

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

## License

MIT. See [`LICENSE`](LICENSE).
