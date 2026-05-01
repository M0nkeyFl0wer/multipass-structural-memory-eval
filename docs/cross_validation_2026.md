# Cross-Validation 2026 — Plan, Status, and Findings

This document is the working plan for [SME #9 — Cross-validate SME categories
against LongMemEval / LoCoMo / MemoryBench](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval/issues/9).
It also scopes the **Karpathy-baseline condition D** (full-corpus-in-context)
that pairs naturally with SME's existing A/B/C condition methodology.

The standard scientific move when introducing a new measurement instrument
is to first calibrate it against known-working ones. This issue does that
for SME's category readings against the most-cited industry benchmarks.

---

## Status (as of 2026-05-01)

### Done

- **`sme/corpora/longmemeval/loader.py`** — loads the 500-question
  LongMemEval-cleaned dataset (Hugging Face xiaowu0162/longmemeval-cleaned,
  MIT license) into SME-shape `LMEQuestion` records. Ships with a
  primary-source-verified LME → SME category mapping (with the KU semantic-
  divergence caveat: KU rewards returning the new value after overwrite,
  Cat 3 rewards flagging both old and new — partial mapping flagged as
  `cat_3_partial`). 12 tests, full schema verified against the cached
  arXiv PDF. Architecture: per-question vault subdirectories, since
  LongMemEval gives each question its own haystack rather than a shared
  corpus. Commit `6d2bed9`.

- **`sme/categories/_bcubed.py`** — B-Cubed precision/recall/F1 scorer
  (Bagga & Baldwin 1998; Amigó et al. 2009 proved it satisfies all four
  formal cluster-eval constraints). Includes the canonical Bagga-Baldwin
  §3.2 example as a regression test (P=11/15, R=1.0). 16 tests, all
  pass. Commit `db5c79b`.

- **B-Cubed wired into Cat 4a CLI** — `sme-eval cat4 --gold-aliases PATH`
  takes a YAML registry (e.g. `good-dog-corpus/ontology.yaml#aliases`),
  scores the system's canonical-collision output against it, surfaces
  precision/recall/F1 in the report and JSON output. Verified end-to-end
  against the good-dog-corpus seeded GSD / APBT alias pairs. 8 integration
  tests. Commit *(this PR)*.

### Pending (this document plans them)

- Cross-validation harness — `scripts/cross_validate_longmemeval.py`
- MemoryBench provider registration (TypeScript bridge + adapter shim)
- Karpathy-baseline condition D (full-corpus-in-context)
- First reading writeup once the harness has produced numbers

---

## (2) Cross-validation harness design

### What it does

`scripts/cross_validate_longmemeval.py` runs each LongMemEval question
through both:

1. SME's existing scoring pipeline (substring match on `expected_sources`
   over the retrieved `context_string`)
2. LongMemEval's official GPT-4o judge methodology (>97% reported human
   agreement)

— against the same retrieval per question, then reports per-category
correlation between the two scorers. The disagreement set is itself a
finding, not a bug: it characterizes SME's substring matcher's known
limitations against a stronger judge.

### Architecture

LongMemEval's per-question haystack design forces a per-question loop
rather than SME's standard ingest-once-query-many pattern. Pseudocode:

```python
for q in load_questions(longmemeval_oracle_path):
    adapter = make_adapter(...)
    adapter.reset()  # clears any prior state
    adapter.ingest_corpus_from_dir(per_question_vault_dir / q.question_id)

    result = adapter.query(q.text, n_results=5)

    # Score 1: SME substring matcher (existing path)
    sme_score = sme_substring_match(
        retrieved=result.context_string,
        expected=q.expected_sources_session_level(),
    )

    # Score 2: LongMemEval GPT-4o judge (new — wraps their evaluate_qa.py)
    judge_label = longmemeval_judge(
        question=q.text,
        gold_answer=q.gold_answer,
        hypothesis=result.context_string,  # or model-generated answer
        model="gpt-4o-2024-08-06",
        question_type=q.question_type,
    )

    record_per_question(
        question_id=q.question_id,
        sme_category=q.sme_category,
        sme_score=sme_score,
        judge_label=judge_label,
    )

aggregate_and_report()
```

### Open design questions

1. **What runs in `result.context_string`?** Two options:
   - **(a) Retrieved context text** — what SME's substring matcher already
     scores against. Cheap, deterministic, doesn't need an LLM at retrieve
     time. But LongMemEval's judge expects a *generated answer*, not raw
     retrieval, and may score retrieval text poorly even when the right
     content is present.
   - **(b) Model-generated answer from retrieved context** — call an LLM
     with the retrieved context as input and a task-specific prompt,
     capture the answer. This is what LongMemEval was designed to score.
     More expensive (one extra LLM call per question), but apples-to-apples
     with the published numbers.

   **Recommendation:** start with (b) using a single mid-tier reader model
   (e.g., gpt-4o-mini) so the scorer is comparing against what LongMemEval
   actually measures. Add (a) as a side-channel reading for SME-internal
   diagnosis.

2. **Which adapters do we run against?** Each LongMemEval question has
   ~3–6 oracle sessions; ingest is fast. Run all three already-merged
   adapters (`MemPalaceDaemonAdapter`, `FamiliarAdapter`, `RlmAdapter`)
   plus a flat-ChromaDB baseline. The four-way comparison is itself
   informative.

3. **How do we run only Cat 1 / 2c / 6 (the LongMemEval-equivalent
   categories) and not Cat 3?** Cat 3's KU mapping is partial — KU rewards
   silent overwriting, Cat 3 rewards flagging. Running SME's Cat 3 against
   LongMemEval KU would produce a misleadingly bad correlation. Filter by
   `sme_category` field at aggregation time; report per-category
   separately; explicitly do NOT compute a single overall correlation.

4. **API key management.** GPT-4o judge needs `OPENAI_API_KEY`. Document
   in the script's `--help` and skip cleanly when not set (run SME-only
   pass instead).

### Concrete next-PR scope

```
scripts/cross_validate_longmemeval.py     # the harness CLI
sme/eval/longmemeval_judge.py             # thin wrapper around upstream evaluate_qa.py
docs/cross_validation_2026.md             # update this doc with first findings
tests/test_longmemeval_judge.py           # mocked OpenAI call
```

Estimated work: half a day. Blocking dependencies: a working SME adapter
(have several), an `OPENAI_API_KEY` (deferred to runtime).

---

## (3) MemoryBench provider registration

### What MemoryBench is

[supermemoryai/memorybench](https://github.com/supermemoryai/memorybench)
is a unified benchmark runner — TypeScript / Bun — with three orthogonal
axes:

- **datasets** — `locomo`, `longmemeval`, `convomem`
- **providers** — `supermemory`, `mem0`, `zep` (today)
- **judges** — `gpt-4o`, `sonnet-4`, `gemini-2.5-flash`

Pipeline: `Ingest → Index → Search → Answer → Evaluate → Report`,
checkpointed under `data/runs/{runId}/`.

### Why register SME

MemoryBench is the closest thing to a one-runner-many-systems harness in
the memory-eval space. Registering SME as a provider means:

- SME numbers appear alongside Mem0 / Zep / Supermem on the same datasets
- Independent third-party calibration (MemoryBench is published by
  Supermemory — one of the providers it tests; SME-as-provider numbers
  would be third-party verification of MemoryBench's own framing, *and*
  give SME externally-runnable scores)
- Drops SME into a dataset-agnostic harness without us building one

### Architectural shape

MemoryBench's provider interface is a TypeScript class with hooks like
`ingest(text)`, `search(query, options)`, `answer(query, context)`. SME's
adapters are Python classes with `query()` / `get_graph_snapshot()` /
`ingest_corpus()`. The bridge needs a thin TypeScript shim that:

1. Spawns a Python subprocess holding an SME adapter session
2. Translates MemoryBench provider calls to SME adapter calls over stdin/
   stdout JSON-RPC (or a small HTTP server)
3. Reports SME results back in MemoryBench's expected format

### Open design questions

1. **JSON-RPC over stdio vs HTTP?** stdio is simpler; HTTP scales to
   parallel runs. Start with stdio; can swap to HTTP if perf demands.

2. **Which SME adapter does the provider wrap?** Probably parameterizable
   — register `sme-mempalace-daemon`, `sme-familiar`, `sme-flat` as
   distinct MemoryBench providers, each backed by the corresponding SME
   adapter. Lets MemoryBench compare SME's *adapters* against Mem0/Zep,
   not just SME-as-monolith.

3. **Where does the bridge live?** Sub-repo at
   `~/Projects/sme-memorybench-provider/`, separate from the SME repo,
   so its TypeScript surface doesn't pollute SME's Python package. Or as
   a contrib/ folder inside SME — maintainer call.

4. **Coordinate with Supermemory?** They actively maintain MemoryBench
   and might accept an upstream PR. Worth opening an issue on their repo
   asking before building a fork-local provider. The SME naming convention
   would benefit from a short conversation.

### Concrete next-PR scope

```
~/Projects/sme-memorybench-provider/      # new repo
  src/sme_provider.ts                     # TS provider class
  scripts/sme_bridge_server.py            # Python side: wraps an SME adapter
  README.md                               # how to register + run
```

Estimated work: 2 days. Blocking dependencies: a couple-hour session to
read MemoryBench's provider interface in detail; an exchange with
Supermemory about the upstream-vs-fork question.

---

## (4) Karpathy-baseline condition D — full-corpus-in-context

### What this is

[Andrej Karpathy's personal LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
describes a deliberately-simple knowledge-base architecture — `raw/`
source material + `wiki/` LLM-compiled summary articles + a single
`index.md` fitting in a context window — and an explicit anti-pattern
list calling out HTTP servers, graph databases, and local embedding
models as overengineering for personal KBs at this scale (~100 articles,
~400K words).

The mempalace#101 long comment names the live question this raises:
**at what corpus size does structured retrieval start outperforming
flat context-window retrieval?** No published memory benchmark answers
this — they all run at one corpus size.

A "Karpathy condition D" baseline puts the entire corpus in the model's
context, asks the question, and scores. SME's existing A/B/C condition
methodology becomes A/B/C/D:

| Condition | What it tests |
|---|---|
| A — flat ChromaDB | retrieval-only baseline, no structure |
| B — full structured pipeline | retrieval + structure |
| C — same index, structure disabled | isolates structural contribution |
| **D — full corpus in context** | tests whether retrieval is buying anything at all |

### Two flavors

- **D1 — raw context.** Concatenate every source note's text into one
  prompt. No retrieval, no compilation. Cheap; only works if the corpus
  fits in the model's context. good-dog-corpus (24 notes, ~50KB total
  text) fits trivially in any frontier model. standard_v0_1 fits
  comfortably. LongMemEval-S (~115K tokens per question) fits in current
  long-context models (Claude 4, Gemini 1.5+, GPT-4 Turbo 128k). M
  variants probably don't.
- **D2 — Karpathy-compiled.** Add the `wiki/` LLM-compilation step:
  LLM summarizes each source note into a wiki article, builds a
  hierarchical index, prepends the index plus on-demand-fetched articles
  to the prompt. More expensive (one-time compilation cost) but mirrors
  Karpathy's actual setup. Tests whether the LLM-compilation layer adds
  value over raw context.

### Why this matters for SME's positioning

- Adds a fourth condition that directly answers the scale question
- Provides an absolute lower-bound reading: *if condition D scores higher
  than B+C on a corpus, structured retrieval is overhead at that scale*
- Validates SME's three-corpus methodology — the A/B/C/D delta will
  shift dramatically across corpus sizes, which is the structural axis
  SME exists to surface

### Architectural shape

```python
# sme/conditions/full_context.py

class FullContextAdapter(SMEAdapter):
    """Condition D adapter — no retrieval, full corpus in context.

    Loads every text file under the corpus's vault/ at construction;
    `query()` returns the entire corpus content as context_string.
    For SME's substring matcher this is trivially correct (every
    expected_source is present). For an LLM-judge pipeline (issue #9
    cross-validation), this becomes the no-retrieval baseline.
    """
```

For D2 (Karpathy-compiled), add a separate `KarpathyCompiledAdapter` that
runs an LLM compilation pass at ingest time and uses the compiled wiki +
index instead of raw notes.

### Concrete next-PR scope

For D1 (small):

```
sme/conditions/full_context.py       # adapter (~80 LOC)
tests/test_full_context.py
```

For D2 (larger, separate PR):

```
sme/conditions/karpathy_compiled.py  # adapter (~200 LOC + LLM pipeline)
sme/conditions/wiki_compiler.py      # one-time LLM compilation
tests/test_karpathy_compiled.py
```

Estimated work: D1 = 1-2 hours, D2 = 1 day. Both blocked on nothing
internal; D2 needs `OPENAI_API_KEY` or equivalent for the compilation
step.

### Run plan

Once D1 lands, run all four conditions against good-dog-corpus and
report A/B/C/D deltas. Then run against standard_v0_1 (when authored).
Then against LongMemEval-S oracle. The cross-corpus comparison is
the actual scale-question reading.

### Why this slots into issue #9 specifically

Issue #9 is "cross-validate SME categories against LongMemEval / LoCoMo /
MemoryBench." The Karpathy condition is the *implicit* baseline those
other benchmarks compare against — frontier models with full-context
retrieval are the regularly-cited reference numbers in LongMemEval
(see paper §5 — "long-context LLMs" rows in their tables). Adding
condition D to SME makes that comparison explicit and reproducible
inside SME's harness, rather than leaving it as a paper-published
external number.

---

## Open issues / decisions deferred

- **Cross-validation reader model.** The harness needs a "reader" — the
  model that turns retrieved context into an answer for the GPT-4o judge
  to score. Options: gpt-4o-mini (cheap, calibrates against published
  baselines), Claude Haiku (free local-ish via Anthropic), the same
  judge model (gpt-4o-2024-08-06 — apples-to-apples with LongMemEval's
  published numbers but most expensive). Default: gpt-4o-mini, with a
  flag to override.

- **Per-corpus gold-alias registries.** B-Cubed for Cat 4a needs gold
  alias clusters per corpus. good-dog-corpus has them; standard_v0_1
  doesn't yet (the `aliases` section in spec v8 mentions ZK proof / k8s /
  CBT pairs, but they're not committed in YAML form). Authoring is
  ~30 minutes; deferred to a separate small PR.

- **Reproducibility metadata on baseline JSONs.** PR #6's 8 baseline
  JSONs don't carry the SME framework git SHA, the adapter version, or
  the corpus version. Adding a `run_metadata` field is a separate small
  refactor — the cross-validation harness should ship with this from
  day 1, retroactive backfill of older baselines is optional.

---

## Citations

- Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., & Yu, D. (2025).
  *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive
  Memory.* ICLR 2025. arXiv:2410.10813. MIT license.
- Maharana, A., et al. (2024). *Evaluating Very Long-Term Conversational
  Memory of LLM Agents.* ACL 2024. arXiv:2402.17753.
- supermemoryai/memorybench — unified benchmark runner.
  https://github.com/supermemoryai/memorybench
- Bagga, A., & Baldwin, B. (1998). *Algorithms for Scoring Coreference
  Chains.* LREC 1998 Workshop on Linguistic Coreference.
- Amigó, E., Gonzalo, J., Artiles, J., & Verdejo, F. (2009). *A
  comparison of extrinsic clustering evaluation metrics based on formal
  constraints.* Information Retrieval Journal.
- Karpathy, A. (2024). *LLM Wiki — a personal knowledge-base setup.*
  GitHub gist 442a6bf555914893e9891c11519de94f.
