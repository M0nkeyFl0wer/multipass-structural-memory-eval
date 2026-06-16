# SME Three-Layer Model — Implementation Note

> **Date:** 2026-06-04  
> **Applies to:** `sme-eval >= 0.0.2` (post Batch A–I)

## What Changed

The framework now organizes its evaluation surface into three explicit layers:

```
Layer 1 — Structural Categories (1–9)
Layer 2 — Deterministic Overlays
Layer 3 — LLM-Judge Overlays
```

### Layer 1: Structural Categories (unchanged)
- Cat 1 (Factual Retrieval)
- Cat 2 (Cross-Domain Discovery / Multi-Hop)
- Cat 3 (Contradiction Detection)
- Cat 4 (Ingestion Integrity)
- Cat 5 (Gap Detection)
- Cat 6 (Temporal Reasoning)
- Cat 7 (Token Efficiency)
- Cat 8 (Ontology Coherence)
- Cat 9 (Harness Integration)

These answer: **"Is the graph healthy?"**

### Layer 2: Deterministic Overlays (new)
Computed from `QueryResult` fields without any API calls.

| Metric | Module | Description |
|---|---|---|
| `entity_id_overlap` | `sme/eval/deterministic_overlays.py` | Fraction of retrieved entities whose id/name contains an expected source substring. Only meaningful when adapter IDs are human-readable. Not a general contextual-precision metric. Returns `null` when no oracle is available. |
| `token_utilization` | `sme/eval/deterministic_overlays.py` | Ratio of answer tokens to context tokens. Weak signal for TRACe Utilization. Uses tiktoken (cl100k_base) when available; falls back to whitespace split. |
| `latency_ms` | Harness layer | Wall-clock time per query. Populated by `timed_query()` wrapper in `sme/harness/wrapper.py`. |
| `interaction_turns` | Adapter layer | Number of turns per query. Single-turn adapters default to 1. Multi-turn adapters increment. Used for Stompy-style exploration overhead. |
| `latency_ms` | Harness layer | Wall-clock time per query. Populated by `timed_query()` wrapper. |

These answer: **"Is the retrieval precise and efficient?"**

### Layer 3: LLM-Judge Overlays (new, opt-in)
Require API key. Gated by `--eval-generative` flag. Skipped when `--offline`.

| Metric | Module | Description |
|---|---|---|
| `faithfulness` | `sme/eval/faithfulness.py` | Fraction of answer claims supported by context. Uses `RubricJudge` infrastructure. |
| `answer_relevancy` | `sme/eval/answer_relevancy.py` | Score 0.0–1.0 for how directly the answer addresses the question. Uses `RubricJudge` infrastructure. |

These answer: **"Is the generated answer faithful and complete?"**

## CLI Changes

```bash
# Run retrieval with deterministic overlays (always)
sme-eval retrieve --adapter mempalace --db ./palace --questions corpus.yaml --json out.json

# Also run LLM-judge overlays (requires API key)
sme-eval retrieve --adapter mempalace --db ./palace --questions corpus.yaml --eval-generative --json out.json

# Skip all LLM-judge calls (CI-friendly)
sme-eval retrieve --adapter mempalace --db ./palace --questions corpus.yaml --offline --json out.json
```

The `--offline` flag is global and applies to all subcommands that might invoke an LLM judge.

## JSON Output Changes

Each question in the `retrieve` JSON output now includes an `overlays` key:

```json
{
  "id": "q001",
  "recall": 1.0,
  "tokens": 452,
  "elapsed_ms": 120.5,
  "overlays": {
    "entity_id_overlap": 0.6,
    "token_utilization": 0.08,
    "generative": {
      "faithfulness": 0.85,
      "answer_relevancy": 0.92
    }
  }
}
```

When `--offline` is set, `"generative": null`. When `--eval-generative` is not set, `"generative": null`.

## Backward Compatibility

- `QueryResult` new fields (`latency_ms`, `interaction_turns`) have safe defaults and do not break existing adapters.
- Report `to_dict()` methods are explicit (not `dataclasses.asdict`) so new dataclass fields do not auto-leak into JSON output.
- Overlay data is nested under `overlays` in CLI JSON output, not at the top level, so existing consumers that only look at `recall`, `tokens`, etc. are unaffected.
- The `RubricJudge` extraction in Batch D preserved the public API of `grade_answer()` — all existing LongMemEval tests pass unchanged.

## Calibration Fixtures

Hand-crafted calibration examples live in `tests/fixtures/calibration/`:
- `faithfulness_examples.json` — 6 examples (supported, partial, contradicted, hallucination, empty)
- `relevancy_examples.json` — 4 examples (perfect, partial, irrelevant, refusal)

Tests marked `@pytest.mark.slow` validate that the rubric produces scores within ±0.2 of expected on these anchors. Run with `python3 -m pytest tests/ -m slow` when API keys are available.

## Files Added / Modified

| File | Change |
|---|---|
| `sme/adapters/base.py` | Added `latency_ms`, `interaction_turns` to `QueryResult` |
| `sme/harness/wrapper.py` | New — `timed_query()` wrapper |
| `sme/eval/deterministic_overlays.py` | New — Layer 2 metrics |
| `sme/eval/judge_base.py` | New — extracted `RubricJudge` class |
| `sme/eval/judge_cache.py` | New — disk cache for judge calls |
| `sme/eval/faithfulness.py` | New — Layer 3 faithfulness rubric |
| `sme/eval/answer_relevancy.py` | New — Layer 3 relevancy rubric |
| `sme/eval/niah.py` | New — synthetic NIAH runner |
| `sme/corpora/locomo_loader.py` | New — LOCOMO dataset loader |
| `sme/cli.py` | Added `--offline`, `--eval-generative`, wired overlays into retrieve output |
| `pyproject.toml` | Registered `slow` pytest marker |

*End of implementation note.*
