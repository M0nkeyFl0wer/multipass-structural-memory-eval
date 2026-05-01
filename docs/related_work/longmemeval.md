# LongMemEval

## Provenance

- **arXiv:** [2410.10813](https://arxiv.org/abs/2410.10813)
- **Title:** *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*
- **Authors:** Wu et al. (lead: Di "Xiao" Wu, GitHub `xiaowu0162`); UCLA NLP / collaborators per the maintainer's faculty page (cs.ucla.edu/~kwchang).
- **Venue:** ICLR 2025 (conference paper). Also indexed on OpenReview `pZiyCaVuti` and the ICLR 2025 proceedings page `28290`.
- **GitHub:** [xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval) (MIT license per third-party summaries; license text not re-verified in this session).
- **Dataset:** Hugging Face `xiaowu0162/longmemeval` and `xiaowu0162/longmemeval-cleaned`.
- **Project page:** https://xiaowu0162.github.io/long-mem-eval/
- **Read date:** 2026-04-30
- **Method:** Direct fetch of the arXiv PDF/HTML and the GitHub README was blocked in this sandbox (WebFetch + MCP fetch tools both denied). Primary-source claims below are reconstructed from `WebSearch` results that quote the paper directly. Where a claim could only be sourced from a third party (Mastra, Supermemory, OMEGA, emergentmind summaries) it is marked `[third-party]`. Quotes attributed to the paper were cross-checked against at least two independent search results returning the same wording before being treated as verbatim.

## What it is

LongMemEval is a benchmark of **500 manually curated question instances** for evaluating long-term interactive memory in chat assistants. Each question is embedded inside a long, multi-session, timestamped user-assistant conversation history, and the system under test must answer the question after observing the entire interaction stream. The benchmark targets five "core long-term memory abilities" that the authors argue are not jointly covered by prior conversational-memory benchmarks (LoCoMo, DMR, MSC).

The five abilities, with the paper's own definitions (verbatim per multiple search snippets, see Citations):

- **Information Extraction (IE):** *"Ability to recall specific information from extensive interactive histories, including the details mentioned by either the user or the assistant."*
- **Multi-Session Reasoning (MR):** *"Ability to synthesize the information across multiple history sessions to answer complex questions that involve aggregation and comparison."*
- **Knowledge Updates (KU):** *"Ability to recognize the changes in the user's personal information and update the knowledge of the user dynamically over time."*
- **Temporal Reasoning (TR):** *"Awareness of the temporal aspects of user information, including both explicit time mentions and timestamp metadata in the interactions."*
- **Abstention (ABS):** *"Ability to identify questions seeking unknown information, i.e., information not mentioned by the user in the interaction history, and answer 'I don't know'."*

Headline finding: long-context LLMs show a **30%-60% accuracy drop on LongMemEval-S** vs. an oracle setting, and state-of-the-art commercial systems (e.g. GPT-4o) only achieve **~30%-70% accuracy** in the simpler setting. The paper also proposes memory-design improvements (session decomposition, fact-augmented key expansion, time-aware query expansion, Chain-of-Note reading) and reports up to **+10 absolute points** of reading accuracy from structured-JSON + Chain-of-Note.

## Evaluation methodology

**Corpus structure.** Each of the 500 questions is shipped with: a list of `haystack_session_ids`, a list of `haystack_dates` (timestamps), a list of `haystack_sessions` (the actual user-assistant chat content), and (for non-abstention questions) evidence-snippet metadata locating the answer-bearing turns. The conversation histories are produced via an "attribute-controlled pipeline" that yields coherent, extensible, timestamped histories.

**Three released variants:**

| Variant | Sessions per question | Tokens per question | Use |
|---|---|---|---|
| `longmemeval_oracle` | only evidence sessions | small | isolates *reading* ability from retrieval |
| `longmemeval_s` | ~30-40 (capped at 80 fillers, ~115K tokens) | ~115K | standard "small" leaderboard variant |
| `longmemeval_m` | ~500 | ~1.5M | "medium"; stresses retrieval + scaling |

**N.** 500 questions across all variants; LongMemEval-S corpus totals roughly **57M tokens of conversation** at ~50 sessions per question on average `[third-party: Mastra, OMEGA]`.

**Question-type breakdown** (six types, 500 total):

| Type | Count |
|---|---|
| single-session-user | 70 |
| single-session-assistant | 56 |
| single-session-preference | 30 |
| multi-session | 133 |
| knowledge-update | 78 |
| temporal-reasoning | 133 |
| **(plus) abstention `_abs`** | 30 (derived from the above; "false-premise" rewrites) |

Counts per `[third-party: emergentmind, ResearchGate Fig.1 caption, Backboard]`; the count column should be re-verified once direct paper access is restored.

**Scorer.** A prompt-engineered LLM judge — specifically `gpt-4o-2024-08-06` — with question-type-specific prompts. Each question type has its own grading prompt because the "correct" surface form differs (e.g. KU expects the *new* value, ABS expects an "I don't know"). The paper's meta-evaluation reports **>97% agreement with human experts**. Implementation: `src/evaluation/evaluate_qa.py`, invoked as `python3 evaluate_qa.py gpt-4o <hypothesis_file> ../../data/longmemeval_oracle.json`; it appends an `autoeval_label` field per row.

**Retrieval scoring vs. answer scoring.** For *retrieval* metrics (Recall@K), the 30 abstention items are **skipped** because they have no ground-truth evidence sessions. For *answer* scoring, abstention questions are graded on whether the model correctly refuses to answer.

## Metrics defined

- **Answer accuracy (per ability and overall).** Fraction of questions on which the GPT-4o judge labels the model's answer correct, broken down by the five abilities (IE, MR, KU, TR, ABS) and the six question types.
- **Recall@K** (retrieval metric). Whether the system surfaces an evidence session in its top-K, evaluated on the 470 non-abstention items.
- **Reading accuracy.** Accuracy when given oracle evidence sessions, isolating reading capability from retrieval.

The paper distinguishes "offline reading" (oracle) from "online / interactive memory" — letting authors decompose end-to-end accuracy into a retrieval bottleneck and a reading bottleneck. This decomposition is one of LongMemEval's most-cited contributions.

## Mapping to SME categories — VERIFICATION

`docs/sme_spec_v8.md` claims four direct mappings (Cat 1, 2c, 3, 6). Verifying each against the primary definitions above:

### Cat 1 (Factual Retrieval) ↔ LongMemEval IE
**Status: tight match.** SME's spec says (line 414): *"Equivalent to LongMemEval's information extraction category. Every memory system must pass this."* The paper's IE definition — recall of specific information from interactive histories — is the same primitive SME tests. **Divergence comes from the scorer**, not the primitive: SME currently substring-matches on filenames; LongMemEval uses a calibrated GPT-4o judge with >97% human agreement. SME's own spec already acknowledges this and plans Cat 7's LLM-judge upgrade.

- *LongMemEval scores correct, SME would miss:* a synthesized answer that paraphrases the source ("you said you had three bikes") with no filename token overlap with the evidence session ID.
- *SME scores correct, LongMemEval would miss:* the system returns the right source filename / pointer but the surfaced chunk does not actually contain the answer string.

### Cat 2c (Multi-hop) ↔ LongMemEval MR
**Status: approximate, with a real semantic gap.** MR is *"synthesize information across multiple history sessions … aggregation and comparison."* SME Cat 2c is canonicalization-dependent multi-hop discovery. SME's spec (line 426) is honest about the gap: *"LongMemEval's multi-session reasoning is adjacent but doesn't test canonicalization-dependent discovery. No existing benchmark distinguishes 'traversal failed' from 'entity resolution failed.'"* That self-assessment is correct against the primary definition: MR tests cross-session aggregation but not whether the system canonically resolved "Dr. Smith" and "the cardiologist" to one entity before traversing. Mapping should be cited as **adjacent, not equivalent**.

### Cat 3 (Contradiction Detection) ↔ LongMemEval KU + ABS
**Status: weakest of the four mappings.** KU tests whether the system returns the *updated* value after an overwrite — i.e. it tests "do you give me the new fact?" SME Cat 3 tests whether the system *flags the contradiction explicitly* — both old and new, with conflict surfaced. The spec at line 455 makes this distinction correctly: *"LongMemEval tests whether the system returns updated facts, not whether it explicitly flags contradictions."* KU's grading prompt rewards the new value; a system that surfaces both old and new with a "these conflict" flag may score worse on KU than a system that silently overwrites. ABS partially overlaps with SME Cat 5 (gap detection) more than Cat 3.

### Cat 6 (Temporal Reasoning) ↔ LongMemEval TR
**Status: tight on the time-point-query dimension; SME extends.** TR is "awareness of temporal aspects … explicit time mentions and timestamp metadata." SME Cat 6 covers time-point queries (the LongMemEval primitive) **and** adds Cat 6b "provenance chain integrity" — tracking which enrichment process produced an edge and whether it was superseded. LongMemEval has no provenance-chain test. So: Cat 6a ≈ TR; Cat 6b is novel to SME.

## What SME could directly incorporate

1. **The 500-question dataset, as-is.** The schema is straightforward (`haystack_session_ids`, `haystack_dates`, `haystack_sessions`, evidence metadata). A `sme/corpora/longmemeval/loader.py` that emits SME corpus YAML from `longmemeval_oracle.json` is a few hundred lines and unblocks the cross-validation experiment in Issue #9.
2. **The GPT-4o judge with type-specific prompts.** SME's spec already names this as the upgrade path for Cat 1. The judge prompts live in `src/evaluation/` of the LongMemEval repo and are MIT-licensed. Adopting them gives SME the same >97%-human-agreement scorer used by every comparable system (Mem0, Zep, ENGRAM, Mastra, Supermemory). **Caveat the spec already flags:** SME's substring-on-filename matcher and LongMemEval's GPT-4o judge will systematically diverge on (a) synthesized answers without source-token overlap, and (b) right-filename-wrong-chunk cases. The disagreement set is itself the calibration finding.
3. **The oracle/S/M tiering pattern.** Letting SME decompose Cat 1 into a "reading" sub-score (oracle context) and a "retrieval" sub-score (full haystack) would make SME's numbers comparable to every published LongMemEval result and would isolate which structural categories (4, 5, 8) actually move the retrieval needle vs. the reading needle.

## What SME measures that LongMemEval doesn't

Cross-checked against the five-ability taxonomy: LongMemEval has **no analogue** for —

- **Cat 4 (Ingestion Integrity).** LongMemEval ships pre-built timestamped histories; the system under test never extracts entities from raw documents, so pipeline corruption cannot be measured.
- **Cat 5 (Gap Detection / topology-driven holes).** ABS tests "the user never said it" gaps in *conversation*, not structural gaps in a knowledge graph found via persistent homology. Different primitive.
- **Cat 7 (Token Efficiency).** Not measured. LongMemEval's reading-vs-retrieval split is in the same neighborhood but doesn't formalize tokens-per-correct-answer across flat vs. graph vs. graph+topology.
- **Cat 8 (Ontology Coherence).** Not measured. LongMemEval has no schema-vs-claims test surface.
- **Cat 9 (Harness Integration / invocation surface).** Not measured. LongMemEval is a corpus-and-judge benchmark; it does not test whether a memory system is reachable from a given LLM harness via tool/MCP/hook surfaces.

This division of labor is what the SME spec frames as "filing-cabinet vs. structure" benchmarks — and the framing survives cross-checking against the primary source.

## Open questions

1. **Exact per-type counts.** The 70/56/30/133/78/133 breakdown is consistent across third-party summaries but was not confirmed against the paper's Table 2 in this session because direct PDF access was blocked. Should be verified before quoted in the spec.
2. **Per-type judge prompts.** The README references question-type-specific prompts; their exact text matters for cross-validation (especially the KU prompt, which determines whether a contradiction-flagging system is graded as correct). To be re-read before implementing the loader.
3. **TR sub-types.** The paper's TR appears to mix "explicit time mention" and "timestamp metadata" cases without an enumerated sub-typing the way LoCoMo splits single-hop / multi-hop / commonsense. Worth confirming whether the dataset's `question_type` field exposes any TR sub-tagging.
4. **License text on the dataset.** Third-party summaries list MIT for the code; the dataset on Hugging Face was not re-verified for redistribution terms.
5. **Direct verification of the 97% number.** Cited as "the paper reports >97%". Section / table ref to be pinned down on next read.

## Citations

- arXiv abstract: https://arxiv.org/abs/2410.10813
- arXiv PDF: https://arxiv.org/pdf/2410.10813
- arXiv HTML v1: https://arxiv.org/html/2410.10813v1
- arXiv HTML v2: https://arxiv.org/html/2410.10813v2
- GitHub repo: https://github.com/xiaowu0162/LongMemEval
- Project page: https://xiaowu0162.github.io/long-mem-eval/
- HuggingFace paper page: https://huggingface.co/papers/2410.10813
- HuggingFace dataset: https://huggingface.co/datasets/xiaowu0162/longmemeval
- OpenReview: https://openreview.net/forum?id=pZiyCaVuti
- ICLR 2025 poster: https://iclr.cc/virtual/2025/poster/28290
- Third-party deep summary (emergentmind): https://www.emergentmind.com/topics/longmemeval
- Third-party leaderboard tracking (OMEGA): https://omegamax.co/benchmarks
- Mastra "Observational Memory: 95% on LongMemEval": https://mastra.ai/research/observational-memory
- Supermemory research page: https://supermemory.ai/research/
- Follow-up systems benchmarking against LongMemEval: ENGRAM, LiCoMemory (Huang et al. Nov 2025), EverMemOS, Zep/Graphiti, JordanMcCann/agentmemory (96.2%), shane-farkas/memento-memory.
- Related ICLR 2026 paper (HTML 2510.27246) — review for refinements to the methodology.
- MEMTRACK (arXiv 2510.01353) and AbstentionBench (arXiv 2506.09038) — adjacent benchmarks worth a follow-up scan.
