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

### Planned: `mempalace-daemon` adapter

The shipped `sme/adapters/mempalace.py` opens ChromaDB directly via
`chromadb.PersistentClient`. That works for upstream MemPalace
single-process installs but **violates the daemon-strict invariant**
of the [palace-daemon](https://github.com/jphein/palace-daemon) /
[jphein/mempalace](https://github.com/jphein/mempalace) architecture
where the daemon is the only process allowed to open the palace
SQLite. Two `PersistentClient` instances against the same palace =
the multi-writer corruption scenario the daemon was built to
prevent. Even for SME's read-only adapter calls, holding ChromaDB
file handles parallel to the daemon's writers is the wrong shape.

The fork-side adapter would talk only HTTP/MCP:

- `get_graph_snapshot()` → POST `/mcp` with `mempalace_list_wings`,
  `mempalace_list_rooms`, `mempalace_list_tunnels`,
  `mempalace_kg_query`. Each tool returns structured data; the
  adapter assembles the `(Entity, Edge)` graph from those calls.
- `query()` → GET `/search?q=...&kind=...&limit=...` (via the
  palace-daemon HTTP REST surface). Default `kind="content"` keeps
  Stop-hook auto-save checkpoints out of the result set —
  validated end-to-end against the canonical 151K-drawer palace on
  2026-04-25, filter excludes ~637 / ~0.4% of corpus by count but
  ~80%+ of search results before the filter.
- No filesystem access, no ChromaDB import, no shared-process
  constraint with the daemon.

CLI invocation pattern:

    sme-eval cat9 --adapter mempalace-daemon \
      --api-url http://your-daemon:8085 --subtest 9b

The existing `--api-url` flag pattern (used by the LadybugDB
adapter) is the right shape; the new adapter just wires it through
to palace-daemon endpoints instead of LadybugDB ones.

**Why this matters:** the engram-2 critique ("0.984 R@5 but 17% E2E
QA accuracy") is about exactly the integration-under-production-model
slice that Cat 9 measures. The fork's `kind="content"` filter is a
candidate fix for one specific shape of that gap. Running SME Cat 9
through the daemon — both before and after applying the kind=
filter at the adapter layer — would let the framework's verdict
replace our hand-rolled A/B and would generate publishable data on
whether the fix moves the needle. **Multi-hour adapter build** —
not yet started; documented here as the next concrete step in the
SME-on-MemPalace integration story.

### Why the existing adapter still has a use

For users running upstream MemPalace without palace-daemon (the
default install pattern), the existing `mempalace` adapter is
correct — single process, no daemon, direct ChromaDB access is
fine. The fork adapter is *additive*, for users who've adopted
palace-daemon's single-writer architecture.

## License

MIT. See [`LICENSE`](LICENSE).
