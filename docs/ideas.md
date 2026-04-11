# SME onboarding guide

*Structural Memory Evaluation — how to run it against your own memory system.*

This document is a hands-on guide for someone who wants to use SME
against their own stack. If you're looking for the full specification
of what each test measures, read [`sme_spec_v8.md`](sme_spec_v8.md)
alongside this one — the spec is the reference, this is the walkthrough.

---

## What is SME for?

You built (or are using) a memory system — a RAG pipeline, a knowledge
graph, a personal knowledge base, a conversational memory layer — and
you want to know:

1. **Is it actually retrieving the right things**, or is it silently
   returning hub notes that happen to match keywords?
2. **Does its structural layer earn its complexity**, or would a flat
   vector store over the same content score the same?
3. **Does the graph match what the README says the graph is**? Are
   the declared entity types populated, are the tunnels connecting
   what they claim to connect, is the ontology drifting?
4. **Does the model actually reach the memory** when you plumb it
   into Claude Code hooks, an MCP server, or a custom tool? (Cat 9,
   spec'd but not yet implemented.)

Every published memory benchmark (LongMemEval, LoCoMo, MINE,
GraphRAG-Bench, BEAM) answers roughly question (1) against a single
corpus. SME is designed to answer all four, across **multiple corpus
shapes** per run, because brittle default behaviours hide on any
single corpus and only become visible when you compare readings side
by side.

---

## Who should run which categories?

SME's nine categories are a menu, not a hierarchy. Each has a
descriptive palace-nod name (The Lookup, The Stairway, The Blueprint,
etc.) and a `Cat N` identifier you'll see in the code.

| # | Name | Measures | Status today |
|---|---|---|---|
| 1 | The Lookup | Factual retrieval (known answer in known source) | Covered by `retrieve` |
| 2 | The Crossing / Registry / Stairway | Cross-domain discovery, canonicalization, multi-hop by depth | 2c implemented (`cat2c`) |
| 3 | The Dissonance | Contradiction detection | Spec'd |
| 4 | The Threshold | Ingestion integrity — introspection + external | Spec'd |
| 5 | The Missing Room | Gap detection (persistent homology) | Partial via `analyze --betti` |
| 6 | The Archive | Temporal reasoning + provenance | Spec'd |
| 7 | The Abacus | Token efficiency (graph vs flat, pairwise) | Partial via `retrieve` |
| 8 | The Blueprint | Ontology coherence (declared vs actual graph) | Implemented (`cat8`) |
| 9 | The Handshake | Harness integration (tool call, MCP, hook, per-model, per-harness) | Spec'd — **highest-priority next build** |

**Use-case profiles** — run these if you're building:

| System type | Run these first | Skip these |
|---|---|---|
| Conversational memory (MemPalace, Mem0, Zep) | 1, 3, 6, 7, 9 | 4, 5, 8 |
| Research / knowledge-graph infrastructure | all | — |
| Decision support (narrative KG, entity-per-file) | 1, 2, 5, 6, 8, 9 | 4 |
| Content strategy / research corpus | 5, 8 | 1–4, 6–7 |
| Any production deployment | 1, 7, **9 is essential** | — |
| Just use folders (Karpathy-style) | none — SME is overkill | all |

---

## Quickstart: your first diagnostic run

This walks you through running SME against your own content. You
don't need a pre-built reference corpus — you'll write a minimal
question set against a directory of markdown files you already have.

### 1. Install

```bash
git clone https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval
cd multipass-structural-memory-eval
pip install -e ".[topology]"    # topology extras for Cat 5 / analyze --betti
```

### 2. Pick a content directory

Point SME at any directory of markdown files you already have —
research notes, a project journal, a subset of your Obsidian vault,
a clone of a public wiki, whatever. Start small: 10–30 files is
enough for a first pass. Bigger corpora take longer to build and
make authoring the ground-truth question set harder.

### 3. Write a minimal question set

Copy `sme/corpora/standard_v0_1/AUTHORING.md` and read the corpus
contract — it's the authoritative format. The short version: a
`questions.yaml` file with a list of entries like:

```yaml
version: "my-corpus-v0.1"
corpus: "/absolute/path/to/your/content/dir"
collection: "my_test_collection"

questions:
  - id: Q01
    text: "What did I decide about X?"
    min_hops: 1
    expected_sources:
      - specific-filename-substring
    category: factual

  - id: Q02
    text: "How do Y and Z relate?"
    min_hops: 2
    expected_sources:
      - filename-substring-1
      - filename-substring-2
    category: cross_domain
```

A few tips from authoring the framework's own test corpora:

- Every `expected_sources` entry should be a filename **substring**
  that you've verified is present on disk. The matcher is mechanical
  — a hit counts if any expected filename appears in the retrieved
  context.
- `min_hops` is how many source files a reader needs to consult to
  answer the question. 1 = the answer is in one file. 2 = synthesis
  across two. 3 = synthesis across three or more.
- Start with 10–12 questions for a first pass. Small n means every
  per-bucket number is a directional signal, not a measurement — and
  the framework will be honest about that.

### 4. Run a retrieve pass against the flat baseline

The flat baseline is a ChromaDB vector store with no structural
routing — it's the control group every other condition compares
against.

```bash
sme-eval retrieve \
  --adapter flat \
  --questions path/to/your/questions.yaml \
  --collection-name my_test_collection \
  --n-results 5 \
  --json /tmp/flat.json
```

You'll see per-question hits (`✓` full recall, `~` partial, `✗`
miss), total recall and tokens-per-query, and a breakdown by hop
depth. The JSON output is the machine-readable version — keep it,
you'll diff it against other adapter runs.

### 5. Run the same questions against your actual memory system

Swap `--adapter flat` for `mempalace` or `ladybugdb` (or your own
adapter — see the next section). The point of SME is the comparison,
not any single run. Run all three conditions on the same questions:

- **Condition A** — `--adapter flat` — the baseline ceiling.
- **Condition B** — `--adapter <your-system>` with structure enabled
  — the full pipeline as users experience it.
- **Condition C** — your system with structure disabled (route off,
  filter off, whichever flag your adapter exposes) — the same
  underlying index without the structural layer.

The three-condition pattern (A/B/C) is the comparative-advantage
section below. It's where the defensible findings come from.

### 6. Run the Blueprint (Cat 8) against your graph

If your memory system has a declared ontology (a README describing
entity types, an `ONTOLOGY.md`, a schema file), you can test whether
the graph matches its own declarations:

```bash
sme-eval cat8 \
  --adapter ladybugdb \
  --db /path/to/your/graph.ldb \
  --implied-ontology sme/corpora/implied_ontology_mempalace.yaml
```

This compares declared entity types and edge vocabulary against
what's actually in the graph, then runs a claim library (regex
patterns operationalized as structural tests) against the README's
structural claims. Pass/fail per claim, plus a drift score and a
type distribution report. See the [spec](sme_spec_v8.md) Cat 8
section for the full metric definitions.

### 7. Analyze graph structure directly

For any adapter that returns a `get_graph_snapshot()`, the `analyze`
command computes modularity, edge-type entropy, isolation, degree
distribution, and optionally Betti numbers (persistent homology) for
gap detection.

```bash
sme-eval analyze \
  --adapter ladybugdb \
  --db /path/to/your/graph.ldb \
  --betti \
  --json /tmp/structure.json
```

---

## Writing an adapter for your system

An adapter is a thin layer that teaches SME how to talk to your
memory backend. The interface is in `sme/adapters/base.py`. Three
methods minimum:

```python
from sme.adapters.base import SMEAdapter, Entity, Edge, QueryResult

class MySystemAdapter(SMEAdapter):
    def ingest_corpus(self, corpus_path: str) -> None:
        """Point your system at a directory of source files. Called
        once per corpus before any queries run."""

    def query(self, text: str, n_results: int = 10) -> QueryResult:
        """Run a retrieval query. Return a QueryResult containing
        the rendered context_string, the retrieved entities, the
        retrieval_path (so SME can see what the router decided),
        and any error."""

    def get_graph_snapshot(self, view: str = "full") -> tuple[list[Entity], list[Edge]]:
        """Return a point-in-time snapshot of the graph as two lists.
        The topology layer consumes this for structural analysis."""
```

Reference implementations, in increasing order of complexity:

- `sme/adapters/flat_baseline.py` — the simplest case, ChromaDB
  vector store with no structure. Read this first.
- `sme/adapters/mempalace.py` — ChromaDB + SQLite-triples pattern.
- `sme/adapters/ladybugdb.py` — embedded graph DB with an optional
  HTTP API mode for systems that expose a `/search` endpoint and
  have writer-lock problems opening the DB file directly.

Optional method for Cat 9 (harness integration, not yet
implemented but part of the adapter contract going forward):

```python
    def get_harness_manifest(self) -> list[HarnessDescriptor]:
        """Declare the invocation surfaces your memory system
        supports: ToolCall, MCPResource, ClaudeCodeHook,
        SlashCommand, CustomAction. Cat 9 uses this to run the same
        question set through each surface and measure call-through
        rate, result usage, and per-model sensitivity."""
```

See [spec Cat 9](sme_spec_v8.md#category-9-harness-integration--the-handshake)
for the full manifest contract.

---

## How to read the output

### The delta is the product, the levels are decoration

The reproducible findings SME produces are **controlled before/after
deltas** under identical conditions (same matcher, same corpus, same
questions) and **within-system ablations** (route on vs off, merge
variant A vs B, structure enabled vs disabled). A 0/12 → 7/12 delta
when you swap a merge function is a real, reproducible finding. The
"7/12" on its own is a diagnostic reading inheriting whatever biases
the substring-on-filename matcher has.

Absolute recall numbers are downstream of the matcher, which fails
in both directions:

- A system returning synthesized content with the right answer under
  a different filename is scored wrong.
- A system returning the expected filename but the wrong chunk
  excerpt is scored right.
- Corpora with subjects in filenames (biographical, entity-per-file)
  are trivially "solved" by filename overlap — a plain `grep` would
  score the same.

Read SME outputs as diagnostic readings from controlled experiments,
not as scores on a fixed scale. Call the framework a diagnostic, not
a benchmark. The difference is whether "X beats Y by 3 points" is a
defensible claim (it isn't, at current matcher maturity) or whether
"swapping the merge function under identical conditions moved this
system from 0/12 to 7/12" is (it is).

### The A/B/C isolation pattern

The biggest thing SME does that existing memory benchmarks don't is
isolate the contribution of the **structural layer** from the
contribution of the **underlying index**. Every Cat 2c / Cat 7 run
executes the same system in three conditions on the same questions:

- **Condition A (flat baseline)** — no structure, top-K cosine
  similarity on the raw index.
- **Condition B (full pipeline)** — structural layer enabled, the
  thing users actually experience.
- **Condition C (structure disabled, same index)** — same underlying
  index as B, with the router / filter / scoper turned off.

LongMemEval, LoCoMo, GraphRAG-Bench, and BEAM can tell you which
system scored higher on a fixed corpus. They cannot tell you whether
**the structure that system added** is what earned the score, or
whether the raw index would have scored the same without it. The
B−C delta is the structural contribution. The C−A delta is whatever
metadata, rendering, or scoping overhead the pipeline adds on top of
the same index. Reporting both separately is what turns "structure
earns its complexity" from a vibe into a testable claim.

The A/B/C pattern is also how you distinguish "the router is broken"
from "the underlying index was already good enough." If Condition B
and Condition C produce identical readings on your corpus, your
structural layer is contributing nothing measurable — whatever
retrieval quality you're getting is coming from the raw index, not
from your routing logic.

### Why you need multiple corpus shapes

A single corpus can only tell you how your system behaves on that
shape of data. Different corpus shapes stress different parts of a
retrieval pipeline:

- **Clean biographical / entity-per-file corpora** — filenames
  contain their subjects, the matcher floor equals the ceiling, and
  every retriever scores high. Forgiving to every ontology. You
  learn almost nothing from running a system against only this.
- **Cross-topic research corpora** — queries span multiple topics
  and room names collide with content vocabulary. Adversarial to
  spatial routing systems that assume "one topic per room."
- **Hub-heavy PKM / daily-driver corpora** — a handful of long
  context files (project READMEs, session logs, `CLAUDE.md`-style
  hub docs) dominate any keyword signal. Adversarial to merge
  strategies that let one signal outweigh others.

Running all three shapes (or whatever shapes exist in your domain)
is the only way to see which failures are structural bugs and which
are corpus artefacts. This is the single most important methodology
point in the whole exercise: **no single benchmark corpus can tell
you whether your retrieval is any good**. Every published memory
benchmark uses one corpus shape. The sampling bias is enormous and
largely invisible until you compare across shapes.

### Honest limitations of the current matcher

Read these alongside the spec's limitations section before treating
any specific SME output as gospel:

- **Substring match on filenames is a proxy for correctness.** Fails
  in both directions (see above). The planned grep-floor baseline
  condition will quantify how much of every reported score is
  filename overlap — implement that first if you're building on the
  framework.
- **12 questions per corpus is below the noise floor for per-hop
  claims.** Aggregate recall numbers are more stable than per-depth
  breakdowns. Per-depth numbers read as directional signals at
  small n. The honest statistical bar for hop-bucket claims is
  n ≥ 30 per depth.
- **Hop depth is annotated on the ground-truth graph, not on the
  system's graph.** A question labelled 3-hop in the corpus may be
  1-hop in a system whose index contains a direct edge between
  endpoints, or structurally unreachable in a system whose graph is
  missing intermediate edges. Planned fix: a per-question
  reachability pre-test against each system's graph snapshot.
- **Mine / index / chunk variance is not measured.** The current
  numbers are single-run. Running mine + index 3–5 times and
  reporting ±1SD is the honest fix.
- **No LLM answer-quality judge yet.** The substring matcher grades
  presence, not answer quality. Cat 7's pairwise LLM judge is
  planned, with multi-sample and human calibration required
  (because a single-judge single-sample call replaces one known
  bias with three new ones: model bias, sampling variance,
  calibration drift).
- **Cat 9 is not implemented yet.** Everything in the current
  framework measures offline retrieval. Until Cat 9 ships, any
  reading describes a lower bound on what your system could do if
  the model always reached for the memory. It does not estimate
  what happens in production under a specific model and harness.
  See Cat 9 in the spec for why this is the largest gap in current
  instrumentation.

---

## What's next

### Categories that aren't implemented yet

Cats 1 (standalone), 3, 4, 5 (full), 6, and 7 (standalone with LLM
judge) are spec'd but not wired as CLI commands. Cats 2c and 8 are
implemented; Cats 1 and 7 are partially covered by `retrieve`; Cat 5
has a partial implementation via `analyze --betti`. See the spec for
the full definitions — the category-sized work is there, waiting for
someone who wants it.

### Planned refinements to the current implementation

In priority order:

1. **Grep-floor baseline condition** — report `grep -l <keywords>`
   on filenames alongside every retriever. Quantifies how much of a
   score is filename-matcher bias before spending money on a judge.
2. **Hop-reachability pre-test gate** — per-question path check
   against each system's graph snapshot. Resolves the "routing
   broken vs edges missing" conflation at multi-hop.
3. **Normalized edge-type entropy** — `H / log2(vocab_size)`,
   vocabulary-size invariant, [0,1] scale.
4. **Cat 9 (The Handshake) MVP** — adapter `get_harness_manifest()`
   method; model-runner shim for Claude Sonnet 4.5 and Opus 4.6;
   sub-tests 9a (invocation rate), 9b (call-through success), 9c
   (result usage) against a tool-call harness first; 9g (Claude
   Code hook-driven) after.
5. **LLM judge for Cat 7 pairwise** — with k=3 samples and 20-item
   human calibration per corpus. Replaces the substring matcher with
   a judge that reads context and grades answerability.
6. **Adapter contract refinement** — payload-vs-format separation
   so adapters emit `payload_chunks: list[str]` alongside the
   rendered `context_string`, and the matcher scores against the
   payload list rather than a format-sensitive joined blob.

### Cat 9 (The Handshake) — the largest gap

Every test in this framework currently measures **offline retrieval**:
"given this query, does the retriever return the right document?"
That's what Cats 1–8 test. It's also what every published memory
benchmark tests. The thing none of them measure is whether the
**model actually reaches the memory system** when the model is
running inside a specific harness.

In production, no memory system is ever reached in isolation. It's
reached through an invocation surface — a tool call definition, an
MCP resource, a Claude Code hook, a slash command, a custom GPT
action, a file watcher. The effective memory for a deployment is
roughly:

```
effective_memory ≈ retrieval_quality × invocation_rate × call_through_success × result_usage
```

Cats 1–8 measure the first factor. Cat 9 measures the rest. A
system scoring 95% on offline Cat 1 that gets invoked 20% of the
time in production is a 19% effective memory for that deployment,
and the gap is a strong function of (a) which model is at the wheel
and (b) which harness mediates the call. See [spec Cat 9](sme_spec_v8.md)
for the full sub-test definitions (9a–9g, including a distinct 9g
for hook-driven event-based access). This is the highest-priority
next build because it's the thing that turns every other reading
in the framework into a claim about a **specific build**, with a
specific model, under a specific harness — rather than a claim
about a retriever in isolation.

---

## Prior art

SME builds on and cites work from:

- **LongMemEval** (ICLR 2025) — 500 questions, LLM-judge methodology.
- **KGGen MINE** (Stanford, NeurIPS 2025) — extraction quality benchmark.
- **GraphRAG-Bench** (ICLR 2026) — pipeline-wide RAG evaluation.
- **Microsoft BenchmarkQED** — automated RAG benchmarking, pairwise judge pattern.
- **Zep / Graphiti** — temporal knowledge graphs, 94.8% DMR.
- **ENGRAM** — typed memory, 95.5% token reduction.
- **Karpathy's LLM Wiki** (April 2026) — folders + markdown + LLM, the honest baseline for personal KBs at sub-500K-word scale. The explicit anti-pattern list is worth reading before over-engineering anything.

Everything SME produces, and every system it tests, is open source.
Everything the framework depends on (NetworkX, Ripser, ChromaDB,
LadybugDB, tiktoken, pyyaml) is open source. The goal is shared
instrumentation the community can run on its own systems, not a
leaderboard any single author owns.
