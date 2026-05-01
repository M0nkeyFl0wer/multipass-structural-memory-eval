# LongMemEval — SME corpus loader

This directory holds the loader and SME-shape conversion for the
**LongMemEval** benchmark (Wu et al., ICLR 2025; arXiv 2410.10813;
MIT license). The dataset itself is **not committed** to this repo
(15–90 MB upstream JSON files); see the download list below.

The loader exists as the first concrete deliverable of [SME #9 —
Cross-validate SME categories against LongMemEval / LoCoMo /
MemoryBench](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval/issues/9).

## Why

LongMemEval is the de-facto memory-systems benchmark — Mem0 / Zep /
ENGRAM / EverMemOS / LiCoMemory all report against it. SME claims its
Cat 1 (factual retrieval) maps to LongMemEval's *information
extraction* primitive; the cross-validation experiment runs both
scorers on the same retrievals to verify or refute the equivalence.
See `docs/related_work/longmemeval.md` for the primary-source-verified
mapping.

## Dataset download

```bash
mkdir -p sme/corpora/longmemeval/data
cd sme/corpora/longmemeval/data
# Oracle subset (only evidence sessions; smallest, ~15 MB):
wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json
# (Optional) S subset (~115K tokens per question, ~85 MB):
wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json
# (Optional) M subset (~1.5M tokens per question, larger):
wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_m_cleaned.json
```

The `data/` directory is gitignored — keep the upstream JSON local.

## Format mapping (LongMemEval → SME)

| LongMemEval field | SME mapping |
|---|---|
| `question_id` | `id` in questions.yaml |
| `question_type` | preserved under `longmemeval.question_type`; mapped to SME category via `LME_TO_SME_CATEGORY` |
| `question` | `text` |
| `answer` | `gold_answer` (used by LongMemEval's GPT-4o judge; outside SME's substring matcher) |
| `question_date` | preserved under `longmemeval.question_date` |
| `haystack_sessions` | one markdown file per session under `vault/<question_id>/<session_id>.md`, with each turn rendered as `## role` + content |
| `answer_session_ids` | `expected_sources` (session-level — the SME substring matcher checks whether retrieval surfaces these session ids) |
| turn-level `has_answer: true` | rendered as `<!-- evidence -->` HTML comment in the markdown; available via `LMEQuestion.expected_sources_turn_level()` for finer-grained matching |

## Architectural note: per-question vaults

LongMemEval gives each question its own haystack — there is no shared
corpus. SME's standard adapter pattern assumes one corpus that all
questions query against. The loader resolves this by writing each
question's haystack to its own subdirectory under `vault/<question_id>/`.

Cross-validation runs against this corpus must therefore loop:

```
for q in questions:
    adapter.reset()
    adapter.ingest_corpus_from_dir(vault_dir / q.question_id)
    result = adapter.query(q.text, n_results=5)
    sme_score = sme_substring_match(result, q.expected_sources_session_level())
    judge_score = longmemeval_judge(result.context_string, q.gold_answer)
    record(q.question_id, sme_score, judge_score)
```

— rather than the single-vault-many-questions pattern SME uses for
`standard_v0_1` and `good-dog-corpus`.

## SME ↔ LongMemEval category mapping (verification status)

Verified primary-source 2026-05-01 against the LongMemEval paper §3
(arXiv 2410.10813):

| LongMemEval | SME category | Mapping confidence |
|---|---|---|
| Information Extraction (IE) — single-session-* | Cat 1 | **Exact primitive match.** Only divergence is scorer (substring vs GPT-4o judge). |
| Multi-Session Reasoning (MR) — multi-session | Cat 2c | **Approximate.** LongMemEval doesn't test canonicalization-dependent discovery. |
| Knowledge Updates (KU) — knowledge-update | Cat 3 (partial) | **Semantically different primitive.** KU rewards returning the new value after overwrite; Cat 3 rewards flagging both old and new. A silent-overwriter scores better on KU than a contradiction-surfacing system. |
| Temporal Reasoning (TR) — temporal-reasoning | Cat 6 | Strong match. |
| Abstention (ABS) — `*_abs` | Cat 1 (negative class) | Different from positive-class Cat 1 — the system is supposed to refuse, not retrieve. |

## Status

- `loader.py` — `LMEQuestion` / `LMESession` / `LMETurn` dataclasses, `load_questions(path)` iterator, `materialize_sme_corpus(questions, output_dir)` for on-disk vault rendering.
- `tests/test_longmemeval_loader.py` — schema-fidelity tests against an inline 2-record fixture.
- **Pending:** the cross-validation harness itself (loops over questions, runs an SME adapter, runs LongMemEval's GPT-4o judge on the same retrievals, reports per-category correlation). Issue #9 next concrete step after this PR lands.
- **Pending:** B-Cubed scorer for Cat 4a (separate, ~50 LOC drop-in; see issue #9 deliverables list).

## Citation

Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., & Yu, D. (2025).
*LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive
Memory.* ICLR 2025. arXiv:2410.10813. MIT license.

Upstream repo: https://github.com/xiaowu0162/LongMemEval
Cleaned dataset: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned
