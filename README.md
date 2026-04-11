# multipass-structural-memory-eval

**A diagnostic framework for memory systems** — RAG, knowledge graphs,
personal knowledge bases, conversational memory — that tests what the
system knows about its own structure, not just whether it can retrieve
memories.

> *"Multipass!"* — Leeloo, *The Fifth Element*. The name is a nod to a
> joke from an earlier MemPalace issue thread, and also to what the
> framework actually does: **multiple passes** over every memory
> system under test, across multiple corpus shapes and multiple
> retrieval conditions (A / B / C), so brittle default behaviours that
> hide on any single pass become visible when the readings are
> compared side by side.

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

## License

MIT. See [`LICENSE`](LICENSE).
