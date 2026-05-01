# LoCoMo and MemoryBench

> Status: research note for SME issue #9 (cross-validation against industry
> benchmarks). Read date: 2026-05-01. WebFetch was blocked in this
> environment, so primary content was gathered via WebSearch result
> excerpts and ACL Anthology / arXiv abstract pages. Claims that come
> from third-party summaries (emergentmind.com, themoonlight.io, devpost
> writeups, vendor blog posts) rather than directly from the paper PDF
> or repo file are marked **[third-party]** inline. Anything not so
> marked was confirmed against the ACL Anthology landing page, the
> arXiv abstract page, the snap-research.github.io project page text
> shown in search snippets, the official MemoryBench repo description,
> or the supermemory.ai/docs/memorybench/cli reference.

## Part 1 — LoCoMo

### Provenance

- **Paper:** *Evaluating Very Long-Term Conversational Memory of LLM
  Agents*
- **Authors:** Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov,
  Mohit Bansal, Francesco Barbieri, Yuwei Fang
- **Venue / year:** ACL 2024 (Long Papers)
- **ACL Anthology:** https://aclanthology.org/2024.acl-long.747/
- **arXiv:** https://arxiv.org/abs/2402.17753 (id `2402.17753`, Feb 2024)
- **Project page:** https://snap-research.github.io/locomo/
- **GitHub:** https://github.com/snap-research/locomo
- **Read date:** 2026-05-01
- **Fetch method:** WebSearch (WebFetch denied in this sandbox); cross-
  referenced ACL Anthology, arXiv abstract listing, the project-page
  description that appears as a search snippet, and three independent
  third-party summaries.

### What it is

LoCoMo ("Long Conversational Memory") is a dataset and benchmark of
**very long-term, multi-session, multi-modal dialogues between two
personas**, plus a question-answering / event-summarization /
multi-modal-dialogue-generation suite over those dialogues.

Corpus shape, as reported by the authors and consistently echoed by
third-party summaries:

- **50 conversations** in the released benchmark **[third-party,
  multiple]**.
- Each conversation averages **~300 turns** and **~9,000 tokens**, over
  **up to 35 sessions** (mean session count ~19.3) **[third-party]**.
- Multi-modal: text plus images. Each dialogue integrates **~32 images
  on average** **[third-party — Emergent Mind summary, citing the
  paper]**.
- **~7,512 QA pairs** in the question-answering benchmark **[third-
  party — Emergent Mind summary]**.
- Generation pipeline: machine-human, with LLM agents grounded on
  **personas + temporal event graphs**, then human-validated. (This
  detail does come straight from the paper abstract on arXiv.)

The framing claim, lifted from the abstract: prior dialogue-memory
benchmarks evaluate over much shorter contexts, so this one
deliberately stretches dialogue to a regime where long-context LLMs
and RAG both visibly struggle.

### Evaluation methodology

LoCoMo defines **three tasks**:

1. **Question Answering (QA)** over the full dialogue history.
2. **Event summarization** of what happened across sessions.
3. **Multi-modal dialogue generation** — given dialogue history,
   generate the next turn (text + optional image reaction).

The QA task partitions questions into **five categories** (consistent
across the project page text, several third-party summaries, and the
arXiv abstract phrasing):

- **Single-hop** — answerable from a single session.
- **Multi-hop** — requires composing facts across multiple sessions.
- **Temporal** — date arithmetic, event ordering, "when did X happen
  relative to Y."
- **Open-domain** — requires combining persona/world knowledge with
  dialogue content.
- **Adversarial / unanswerable** — distractor questions designed to
  catch models that hallucinate when the dialogue does not contain
  the answer.

Baselines reported in the paper (per the abstract and the project-
page snippet) include long-context LLMs and RAG-style retrieval-
augmented configurations; the headline result is that all of them
"substantially lag behind human performance" on long-range temporal
and causal reasoning.

### Metrics defined

Based on the QA-leaderboard discussion and third-party metric
summaries:

- **QA:** F1-score on answer prediction; **Recall@k** on retrieved
  evidence sessions **[third-party]**.
- **Event summarization:** ROUGE (n-gram overlap) and **FactScore**
  (atomic-fact precision/recall) **[third-party]**.
- **Multi-modal dialogue generation:** BLEU, ROUGE-L, and
  **MM-Relevance** (a multi-modal relevance score the paper
  introduces); some summaries also describe a composite (L)
  averaging ROUGE-1 recall, METEOR, BERTScore-F1, and SentenceBERT
  similarity **[third-party]**.

I did not read the metrics section of the paper PDF directly in this
session, so the exact definition of MM-Relevance, FactScore's
implementation, and whether the composite (L) is used in headline
numbers or only ablations is **not verified to the primary source**.
Anyone using these as load-bearing numbers for SME claims should
grep the PDF before quoting.

### Mapping to SME categories

This is the section the issue actually cares about. Walking SME's
v8 categories against LoCoMo's QA partitioning:

| SME category | LoCoMo coverage | Notes |
|---|---|---|
| **Cat 1 — Factual Retrieval (Lookup)** | **Direct match** via LoCoMo *single-hop* QA. Both measure "given a query, can the system recall the right fact from a single seed location." Same metric family (recall + answer correctness). | SME's Cat 1 explicitly cites LongMemEval's "information extraction"; LoCoMo's single-hop is the same primitive. |
| **Cat 2c — Multi-hop reasoning by depth** | **Partial match** via LoCoMo *multi-hop*. LoCoMo composes facts across sessions; SME composes across **typed graph edges** with a hop-depth gate (1/2/3-hop) and a `unreachable_in_graph` bucket. LoCoMo does not break out by hop depth or do a graph-side reachability check. | LoCoMo can *validate* that SME's Cat 2c readings agree on the easy end (1-hop) but cannot *falsify* the hop-depth claim — only an SME-style annotated graph can. |
| **Cat 2 — Cross-Domain Discovery / Cat 2b canonicalization** | **No direct equivalent.** LoCoMo persona graphs do span topics, but the questions are not designed to require alias resolution ("ZK proofs" ≡ "zero-knowledge cryptography") to succeed. | SME's claim that no benchmark distinguishes "traversal failed" vs "entity resolution failed" survives. |
| **Cat 3 — Contradiction Detection** | **Adjacent, not equivalent.** LongMemEval has a "knowledge updates" category (returning the latest fact); LoCoMo's adversarial/unanswerable category is closer to **abstention under distractors**, not contradiction *flagging*. | Cat 3's distinguishing feature — surface both facts AND flag the conflict — is not what either LoCoMo or LongMemEval scores for. |
| **Cat 6 — Temporal Reasoning** | **Direct match (partial).** LoCoMo's *temporal* QA category tests date arithmetic and event ordering. SME's Cat 6 *adds* provenance-chain integrity (which process produced an edge, was it superseded). | LoCoMo can validate Cat 6a (time-point queries) but not Cat 6b (provenance). |
| **Cat 4 — Ingestion Integrity (Threshold)** | **No equivalent.** LoCoMo evaluates output, not the structural shape of any system's index/graph. | SME claim "no existing benchmark tests this" is not threatened by LoCoMo. |
| **Cat 5 — Gap Detection** | **No equivalent.** LoCoMo asks questions that *do* have answers in the dialogue (modulo the adversarial bucket); it does not seed *missing* concepts and ask the system to detect the hole. | Same as above — claim survives. |
| **Cat 7 — Token Efficiency** | **No equivalent.** LoCoMo does not normalize by tokens-per-correct-answer or compare flat-vs-structured under matched conditions. | The Cat 7 framing is novel relative to LoCoMo. |
| **Cat 8 — Ontology Coherence** | **No equivalent.** LoCoMo has no notion of testing the system's claimed ontology against its actual graph. | Claim survives. |
| **Cat 9 — Harness Integration** | **No equivalent**, but MemoryBench is itself an instance of what Cat 9 is *about* (harness-level integration of providers). | See Part 2. |

**Summary of mapping:** LoCoMo most strongly validates **Cat 1** (single-
hop ≈ factual retrieval) and **Cat 6a** (temporal point queries). It
gives partial coverage for **Cat 2c** (multi-hop without the hop-depth
breakdown). It does **not** test Cat 2b, 3, 4, 5, 7, 8, or 9. SME's
"unique-to-SME" framing for Cats 4, 5, 7, 8 is unthreatened by LoCoMo.

### Concrete divergence cases

A retrieval that LoCoMo and SME would score differently:

1. **A 3-hop graph traversal on a corpus with weak embedding signal**
   between intermediate entities. SME Cat 2c would credit the typed-
   graph traversal and dock the flat baseline. LoCoMo's multi-hop
   bucket has no notion of graph hop depth — both systems sit in the
   same "multi-hop" bucket and the per-question ground-truth doesn't
   reward the graph for using its structure.
2. **A system that returns the most recent value of a contradicted
   fact without flagging the contradiction.** LoCoMo (and LongMemEval
   knowledge-updates) score this as **correct**. SME Cat 3 scores it
   as **partially correct** (returned something, didn't flag).
3. **A system that produces 8,238 identical-evidence edges during
   ingestion.** LoCoMo: invisible — no ingestion-shape signal. SME
   Cat 4-external: large H0 signature, flagged.

These divergences are not LoCoMo failures — they are out-of-scope by
design. They demarcate where SME is doing something LoCoMo can't.

## Part 2 — MemoryBench (supermemoryai)

### Provenance

- **GitHub:** https://github.com/supermemoryai/memorybench
- **Docs:** https://supermemory.ai/docs/memorybench/cli
- **Authoring org:** Supermemory (the same company that ships the
  supermemory provider; this is a non-trivial fact for the
  positioning discussion below)
- **Read date:** 2026-05-01
- **Fetch method:** WebSearch over the README, the
  `src/benchmarks/README.md` path, the official CLI docs page, and
  the LinkedIn launch post by Dhravya Shah (Supermemory). I was not
  able to render the raw README in this session.

> **Disambiguation warning.** There are at least three distinct
> projects named "MemoryBench": (a) `supermemoryai/memorybench`, the
> subject of this section; (b) `LittleDinoC/MemoryBench`, a separate
> academic benchmark; (c) `arxiv:2510.17281` "MemoryBench: A
> Benchmark for Memory and Continual Learning in LLM Systems," also
> distinct. Don't conflate.

### What it is

Self-description from the repo header (rendered consistently across
the README snippet, the LinkedIn launch post, and the docs site):

> *"Unified benchmark for evaluating conversational memory and RAG
> across multiple datasets."*

It is a **runner**, not a dataset. It glues three orthogonal axes
together:

- **Datasets / benchmarks:** `locomo`, `longmemeval`, `convomem`.
- **Providers (memory systems under test):** `supermemory`, `mem0`,
  `zep`. Configured via per-provider `.env` keys
  (`SUPERMEMORY_API_KEY`, `MEM0_API_KEY`, `ZEP_API_KEY`).
- **Judges (LLMs that score answers):** `gpt-4o`, `sonnet-4` (Claude
  Sonnet 4), `gemini-2.5-flash`, and others. Configured via
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`.

The headline marketing line is "judge-agnostic, provider-agnostic,
dataset-agnostic, single CLI."

### Architecture

From the CLI docs (https://supermemory.ai/docs/memorybench/cli) and
the README description:

**Pipeline phases (executed in order, checkpointed):**

```
Ingest  →  Index  →  Search  →  Answer  →  Evaluate  →  Report
```

- **Ingest:** load benchmark sessions, push them to the provider's
  ingestion API.
- **Index:** wait for the provider to finish indexing (some
  providers are async).
- **Search:** for each evaluation question, query the provider for
  retrieved context.
- **Answer:** call the answering LLM with retrieved context to
  produce a candidate answer.
- **Evaluate:** call the judge LLM to score candidate vs ground
  truth.
- **Report:** aggregate scores, dump structured artifacts.

**State / resume contract:**

- Runs are persisted to `data/runs/{runId}/`.
- Re-invoking with the same `--run-id` resumes from the last
  successful phase. `--force` clears the checkpoint.

**CLI surface (verified from supermemory.ai/docs/memorybench/cli):**

- `run -p <provider> -b <benchmark> -j <judge> -r <run-id>` — full
  pipeline.
- `compare -p supermemory,mem0,zep -b locomo -j gpt-4o` — same
  benchmark, multiple providers, parallel.
- `test -r <run-id> -q <question-id>` — single-question debug.
- `status`, `show-failures`, `list-questions`, `serve`, `help`.
- Optional: `-m` answering model, `-l` question limit, `--force`.

**Implementation:** TypeScript, Bun runtime. Entrypoint
`bun run src/index.ts <command>`. A `serve` subcommand provides a
web UI for interactive run inspection.

I did **not** in this session read the actual TypeScript provider
interface (`src/providers/*.ts`) so I cannot quote the exact method
signatures a provider adapter must implement. From phase semantics
the contract is clearly some shape of:

```
ingest(sessions)  → void
search(question)  → context_chunks
answer(question, context) → string   # often delegated to judge-stack LLM
```

Confirming the exact interface (param shapes, return types, async
contract, error semantics) is a 30-minute follow-up read of
`src/providers/` once WebFetch or `gh api` is available.

### What it could mean for SME

Two ways SME could connect to MemoryBench, with different costs and
different scientific value:

**Option A: SME registers its memory adapters as a MemoryBench
"provider."**

- Cost: implement the MemoryBench provider TypeScript interface,
  pointing at SME's adapter infrastructure (likely an HTTP shim
  fronting the Python adapters).
- Value: SME's adapters get scored on LoCoMo and LongMemEval
  alongside Mem0/Zep/Supermemory by a judge-agnostic harness owned
  by a third party. This is **the strongest possible answer to "are
  SME's Cat 1 numbers calibrated to industry benchmarks."**
- Limit: only Cats 1, 2c, 6a get cross-validated. Cats 4/5/7/8 are
  invisible to MemoryBench because LoCoMo/LongMemEval don't probe
  for them.

**Option B: SME builds a LoCoMo loader as an SME corpus.**

- Cost: write a corpus adapter that consumes LoCoMo's released JSON
  and emits SME-shaped session/question artifacts.
- Value: SME's full category surface runs against a corpus the
  industry already knows. Cat 7 (token efficiency) becomes
  comparable across SME runs with same corpus.
- Limit: SME is the harness, so SME is also the marker — no third-
  party calibration. The industry result on LoCoMo is what
  MemoryBench publishes, not what SME publishes.

**Option C: both.** Register as a provider for industry calibration
on Cats 1/2c/6a, and ingest LoCoMo as a corpus so SME-unique cats
(4/5/7/8) get reported against the same dialogues. This is the
research-honest answer and the cheapest of the three on the margin
once Option A is done — most of the LoCoMo loader work overlaps
with the ingestion path needed for the provider adapter.

**Bias caveat to note in any writeup:** MemoryBench is published by
Supermemory, which is also one of the providers tested. The
mitigations (judge-agnostic, multi-provider, open code) are the
right ones, but third-party readers will reasonably want
independent harness runs. SME publishing its own LoCoMo-loader
results is itself a form of that independent verification.

## Citations

Primary:

- ACL Anthology — Maharana et al., *Evaluating Very Long-Term
  Conversational Memory of LLM Agents*, ACL 2024:
  https://aclanthology.org/2024.acl-long.747/
- arXiv abstract: https://arxiv.org/abs/2402.17753
- Project page: https://snap-research.github.io/locomo/
- LoCoMo repo: https://github.com/snap-research/locomo
- MemoryBench repo: https://github.com/supermemoryai/memorybench
- MemoryBench CLI docs: https://supermemory.ai/docs/memorybench/cli
- MemoryBench benchmarks README path:
  https://github.com/supermemoryai/memorybench/blob/main/src/benchmarks/README.md

Related / referenced for context:

- LongMemEval (ICLR 2025), the other dataset MemoryBench wraps:
  arXiv 2410.10813, https://github.com/xiaowu0162/LongMemEval
- LiCoMemory, Huang et al., 2025 (cited in earlier SME searches as
  outperforming on both LoCoMo and LongMemEval): arXiv 2511.01448
- "A Simple Yet Strong Baseline for Long-Term Conversational Memory
  of LLM Agents," arXiv 2511.17208 (recent baseline paper that
  benchmarks against LoCoMo).

Third-party summaries used as **secondary** corroboration only
(flagged inline as **[third-party]** wherever load-bearing):

- emergentmind.com topic pages on LoCoMo, LongMemEval, and the
  joint LoCoMo/LongMemEval comparison.
- themoonlight.io literature review of the LoCoMo paper.
- Devpost project writeup for MemoryBench.
- Dhravya Shah's LinkedIn launch post for MemoryBench.

Repo SHAs were not captured this session — both repos should be
re-pinned to a specific commit before any of these claims are
quoted in a paper or commit message.
