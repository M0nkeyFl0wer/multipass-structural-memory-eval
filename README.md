# multipass-structural-memory-eval

**A diagnostic framework for memory systems** — RAG, knowledge graphs,
personal knowledge bases, conversational memory — that tests what the
system knows about its own structure, not just whether it can retrieve
memories.

> *"Multipass!"* — Leeloo, *The Fifth Element*. The name is a nod to
> the joke in the first MemPalace issue thread, and also to what the
> framework actually does: **multiple passes** over every memory
> system under test, across multiple corpus shapes and multiple
> retrieval conditions (A / B / C), so brittle default behaviours that
> hide on any single pass become visible when the readings are
> compared side by side.

> Installed as the Python package `sme-eval` (`pip install sme-eval`).
> The CLI entrypoint is `sme-eval`. The GitHub repo is
> `multipass-structural-memory-eval`. The acronym SME (Structural
> Memory Evaluation) is used throughout the documentation.

> What should a memory system know about its own structure, and how
> do you test whether it does?

Standard memory benchmarks (LongMemEval, LoCoMo, MINE, GraphRAG-Bench)
ask "can you find a memory?" That's necessary but not sufficient. A
filing cabinet can find a memory. The question is what the structure
gives you beyond retrieval.

SME adds seven structural categories on top of factual retrieval,
plus a graph-vs-no-graph baseline and an ontology coherence layer
that tries to measure whether structure actually earns its complexity.

## Status

**Beta-level instrumentation, actively evolving.** This is a
diagnostic toolkit shared because it has already been useful in
practice — it surfaced a real retrieval bug in the author's own
knowledge graph (0/12 → 7/12 on hybrid mode with a 15-line merge-
function fix) on the first serious run, and pointed at a single-
keyword routing collapse on a palace-architecture memory system.
Neither finding was visible to existing benchmarks because those
benchmarks use a single corpus shape; SME runs each test on multiple
corpus shapes precisely to expose this class of bug.

Several refinements are pending that affect how to read the current
numbers. See [`docs/mempalace_issue_comment_draft.md`](docs/mempalace_issue_comment_draft.md)
for the fullest discussion of the diagnostic-vs-benchmark distinction
and the known limitations, and [`docs/sme_spec_v8.md`](docs/sme_spec_v8.md)
for the full specification.

**What is implemented** (today):

- `sme-eval retrieve` — runs a YAML question set through an adapter
  and scores via substring match + tiktoken token count
- `sme-eval analyze` — loads a graph via an adapter and prints a
  structural report (modularity, entropy, isolation, degree
  distribution, optional Betti numbers)
- `sme-eval cat8` — Category 8 ontology coherence (implied ontology
  vs actual graph, claim library pattern matching)
- `sme-eval cat2c` — Category 2c multi-hop recall breakdown by depth
- Three working adapters: `flat` (ChromaDB baseline), `mempalace`
  (ChromaDB + SQLite triples), `ladybugdb` (embedded graph DB)

**What is planned** (not yet implemented):

- **Category 9 — The Handshake (harness integration).** Highest
  priority. Measures whether the model actually reaches the memory
  system through its production invocation surface (tool call, MCP
  resource, Claude Code hook, slash command, custom GPT action),
  whether the call succeeds, whether the returned context lands in a
  form the model uses, and whether the same (memory, harness, model)
  triple works across harnesses and model families. This is the
  category that turns every Cat 1–8 reading into a claim about a
  specific build rather than a retriever in isolation. See Cat 9 in
  the spec for the full sub-test definitions.
- Categories 1, 3, 4, 5, 6, 7 as standalone commands (partially
  covered by the existing commands above; spec'd but not exposed)
- Grep-floor baseline condition (quantifies filename-matcher bias)
- Reachability pre-test gate for Cat 2c (resolves "routing broken vs
  edges missing" ambiguity at multi-hop)
- Normalized edge-type entropy (vocabulary-size invariant)
- LLM judge for Cat 7 pairwise (with multi-sample + human
  calibration)
- Adapter contract: payload-vs-format separation, plus a
  `get_harness_manifest()` method that declares what invocation
  surfaces the system exposes (required for Cat 9)
- Neo4j, Mem0, Zep, Graphiti adapters

## The nine categories

Each category has both a `Cat N` identifier (for code) and a
descriptive "palace-nod" name (for readable output).

| # | Name | Category | Novel? | Status |
|---|---|---|---|---|
| 1 | **The Lookup** | Factual Retrieval | No (adopts LongMemEval methodology) | spec'd; covered by `retrieve` |
| 2 | **The Crossing / Registry / Stairway** | Cross-domain, canonicalization, multi-hop | Partially | 2c implemented (`cat2c`) |
| 3 | **The Dissonance** | Contradiction Detection | Partially | spec'd, not implemented |
| 4 | **The Threshold** | Ingestion Integrity (introspection vs external) | Yes | spec'd, not implemented |
| 5 | **The Missing Room** | Gap Detection (persistent homology) | Yes | partially via `analyze --betti` |
| 6 | **The Archive** | Temporal Reasoning + Provenance | Partially | spec'd, not implemented |
| 7 | **The Abacus** | Token Efficiency (graph vs flat, pairwise) | Yes (as formal benchmark) | partially via `retrieve` |
| 8 | **The Blueprint** | Ontology Coherence (operationalized claims) | Yes | implemented (`cat8`) |
| 9 | **The Handshake** | Harness Integration (tool call, MCP, hook, slash command, per-model, per-harness) | **Yes** | spec'd, not implemented — **highest-priority next build** |

**Cat 9 is the critical one for production use.** Cats 1–8 measure offline retrieval: "given this query, does the retriever return the right document?" Every published memory benchmark makes the same design choice, and so did the first eight categories of this framework. But production memory systems are never reached in isolation — they're reached through an invocation surface (tool call, MCP resource, Claude Code hook, slash command, custom GPT action) by a specific model with its own tool-use priors. The effective memory for a deployment is `retrieval_quality × invocation_rate × call_through_success × result_usage`, and the first eight tests only measure the first factor. Cat 9 measures the rest. Until it ships, every reading from this framework describes a lower bound on what the system could do if the model always reached for it — not an estimate of what happens in production under a specific model and harness.

Full rationale, prior art, and architectural decisions in
[`docs/sme_spec_v8.md`](docs/sme_spec_v8.md).

## Architecture

Pluggable adapter interface. Implement three required methods
(`ingest_corpus`, `query`, `get_graph_snapshot`) and the suite
handles scoring, topology analysis, and reporting. Current shipping
adapters:

| Adapter | Description |
|---|---|
| `flat` | ChromaDB vector-only baseline (control group) |
| `mempalace` | SQLite triples + ChromaDB (MemPalace pattern) |
| `ladybugdb` | Embedded graph DB with native vectors + optional HTTP API mode |

The topology layer (NetworkX + Ripser) is backend-agnostic and runs
on any adapter's graph snapshot.

## Shipping corpora

Three question sets live under `sme/corpora/`:

| Corpus | Shape | Size | Notes |
|---|---|---|---|
| `climate_research_v01` | Cross-topic research content | 19 files / 12 questions | Stresses routing systems that assume "one topic per room" |
| `personal_kg_pkm_v01` | Second-brain PKM (session logs, decisions) | ~70K chunks / 12 questions | Stresses merge strategies under hub-file-heavy indexes |
| `canadian_politics_v01` | Entity-per-file biographies | 45 files / 12 questions | Filenames contain subjects; deliberately "easy" corpus where substring matcher's floor equals ceiling |

**Important:** the source directories these corpora were authored
against are personal and are **not distributed with this repo**. Each
`questions.yaml` ships with a `corpus:` field set to
`PATH/TO/YOUR/...` that needs to be pointed at your own content before
the corpus can be run. A self-contained public reference corpus is
planned under `sme/corpora/standard_v0_1/` and is not yet populated.

Quickstart docs (install, run flat adapter against a shipped corpus,
expected output) are also pending and will land alongside the
reference corpus.

## Related docs

- [`docs/sme_spec_v8.md`](docs/sme_spec_v8.md) — Full specification:
  8 categories, use-case profiles, adapter interface, claim library
  design, planned refinements.
- [`docs/ideas.md`](docs/ideas.md) — Living design overview: headline
  findings, methodology notes, known limitations, comparative
  advantage vs existing benchmarks (A/B/C structural contribution
  isolation).
- [`docs/findings_personal_kg_rrf_fix.md`](docs/findings_personal_kg_rrf_fix.md) —
  Worked example: how the diagnostic surfaced a max-merge bug in a
  personal KG's hybrid retrieval and what the 15-line fix looks like.
- [`docs/findings_personal_kg_pkm_retest.md`](docs/findings_personal_kg_pkm_retest.md) —
  Follow-up: how running the same framework on a second corpus
  falsified a "hybrid is right for PKM" hypothesis.
- [`docs/mempalace_issue_comment_draft.md`](docs/mempalace_issue_comment_draft.md) —
  Diagnostic-posture discussion of running the framework against
  MemPalace, including the methodology and honest-limitations
  sections.

## Install

```bash
pip install -e .
# Optional extras:
pip install -e ".[topology]"   # Ripser + python-louvain
pip install -e ".[ladybugdb]"  # LadybugDB adapter
pip install -e ".[dev]"        # pytest, ruff
```

## License

MIT. See `pyproject.toml`.
