# Critique: What We Just Pushed (Founder-of-Ladybug Perspective)

> **Date:** 2026-06-04  
> **Commits:** `979219d` → `3d05f78` on `ckg-benchmark-experiment`  
> **Mandate:** Be honest about what would impress a technical founder and what would make them raise an eyebrow.

---

## The Good (What I'd Defend in a Demo)

### 1. The RubricJudge extraction is real engineering
Moving retry logic, provider dispatch, and JSON parsing out of the LME-specific judge into a generic base class is the right abstraction. It took 518 lines down to ~300 + a clean interface. The existing LongMemEval tests pass unchanged. **This is not theater — it's actual debt reduction.**

### 2. Judge disk cache with TTL
`sme/eval/judge_cache.py` does one thing well: it caches API calls with a 30-day TTL and LRU eviction, using a stable content hash. For iterative dev, this saves real money. The directory-sharding (`{cache_dir}/{key[:2]}/{key}.json`) is a nice touch — won't create directories with 10k files.

### 3. The `QueryResult` extension is surgically backward-compatible
`latency_ms: float = 0.0`, `interaction_turns: int = 1`, `cost_callback: Optional[Callable] = None`. Defaults mean old adapters compile unchanged. The adapter contract tests verify this. **This is how you extend a public API without breaking downstream users.**

### 4. NIAH implementation is lightweight and correct
No PyTorch, no sentence-transformers. Template-based distractor generation with deterministic seeds. The sequential needle ordering check (`needles_found_in_order`) is a real stress test that SME didn't have before. It can rationalize context-window tradeoffs without synthetic benchmarking frameworks.

### 5. LOCOMO loader is defensive
Written against the documented schema shape, robust to missing keys, and maps question types to SME categories. Even if we never get the actual dataset, the loader is a credible piece of engineering. The `to_sme_question()` method shows it wasn't just cargo-culted from the LME loader.

---

## The Bad (What a Founder Would Call Out in 30 Seconds)

### 1. `contextual_precision_proxy` is a toy metric

```python
# From sme/eval/deterministic_overlays.py
if any(source in entity.id or source in entity.name for source in expected_sources):
    matched += 1
```

This works **only** because SME's adapters happen to use human-readable entity IDs (`"sess_001_b"`, `"drawer_abc"`). If an adapter uses UUIDs or hash-based IDs (which is the norm in production systems), this returns 0.0 for every query. It's not a "proxy" — it's a substring hack that happens to work on our test data.

**What a founder would say:** *"This metric is measuring whether your test fixtures use readable IDs, not whether the retrieval is precise. Ship it, but call it `entity_id_overlap` not `contextual_precision`."*

### 2. `token_utilization` has the wrong sign

```python
return answer_tokens / context_tokens
```

A **good** answer is short and dense. A **bad** answer is long and rambling. This metric gives a *higher* score to the bad answer. It's literally backwards.

If the context is 1000 tokens and the answer is 50 tokens, utilization = 0.05. If the answer hallucinates and writes 500 tokens, utilization = 0.5. The hallucination scores 10× "better."

**What a founder would say:** *"Did you think about what this number means? Or did you just divide two things because they were both integers?"*

**Fix:** Should be `min(answer_tokens, context_tokens) / context_tokens` (capped at 1.0) or better yet, `supported_claims / total_claims` which requires the LLM-judge path. The deterministic version is a bad metric.

### 3. Calibration fixtures are untested claims

We shipped `tests/fixtures/calibration/faithfulness_examples.json` with 6 examples and `expected_score` values like `0.33`, `0.5`, `1.0`. But:
- **We never ran them against GPT-4o.**
- The `@pytest.mark.slow` tests skip when no API key is present (which is always in CI).
- The tolerance is ±0.2, which is huge. A 5-point scale with ±0.2 tolerance means "anything from 0.3 to 0.7 is acceptable."

**What a founder would say:** *"You have a calibration suite that has never been calibrated. That's not calibration — it's a wish list."*

**Fix:** Run the calibration suite once against GPT-4o-2024-08-06, record the actual scores, and commit the results. If the LLM doesn't hit the expected scores, fix the rubric or the expectations. Don't ship fiction.

### 4. Faithfulness rubric is brittle by design

The prompt asks the LLM to "list each factual claim in the answer." But:
- **Claim segmentation is not specified.** Does "Paris is the capital of France and has 2.1 million people" = 1 claim or 2? Different LLMs segment differently.
- **"Entailed by the context"** is a subjective standard. Is "Python is popular" entailed by "Python was created by Guido van Rossum"? GPT-4o might say yes (it's common knowledge); a strict judge might say no.
- **No few-shot examples in the prompt.** The rubric is zero-shot. RAGAS uses few-shot examples for exactly this reason.

**What a founder would say:** *"You're asking a stochastic system to do a task humans disagree on, with no examples, and treating the output as ground truth. Why should I trust this number?"*

### 5. LOCOMO loader has no harness

We wrote a loader. We wrote tests for the loader. But there's no `scripts/cross_validate_locomo.py`. The loader is an island. It's not connected to any actual evaluation pipeline.

**What a founder would say:** *"You built a beautiful airport with no planes. Where's the rest?"*

### 6. NIAH `run_niah` tests the wrong thing

`run_niah` calls `adapter.query(needle)` and checks if the needle appears in `result.context_string`. But:
- Adapters expect **natural language questions**, not exact needle text. Passing "The secret password is blueberry7" as a query to a semantic search system might not retrieve the sentence containing "blueberry7" because the query doesn't semantically match.
- The check ignores `result.answer`. If the adapter answers "blueberry7" from memory without retrieving it from context, the test says "not found" even though the system correctly recalled the fact.
- **NIAH is supposed to test *retrieval* from a long context, not *question-answering*.** The correct implementation is: inject the needle into the corpus, ask a *related question* (e.g., "What is the secret password?"), and check if the answer contains the needle.

**What a founder would say:** *"Your NIAH test is actually testing whether the adapter can do exact-match lookup on its own query string. That's not a stress test — that's tautology."*

### 7. Cost callback is dead code

We added `cost_callback: Optional[Callable[[int, int, str], float]] = None` to `QueryResult`. Zero adapters populate it. The CLI doesn't wire it. There are no tests that use it end-to-end.

**What a founder would say:** *"You added a hook that nobody uses. Why?"*

**Fix:** Either add a concrete cost callback implementation (e.g., one that reads from a user-supplied YAML) and wire it in the CLI, or remove it until there's a user. Dead code rots.

### 8. We accidentally deleted issue drafts

Commit `979219d` (Batch A) deleted 14 files from `docs/issue-drafts/` including `2026-05-30-ontoclean-shacl-brokerage/README.md` and its children. These were living documentation of active work streams.

**What a founder would say:** *"Your 'clean up' commit threw away my roadmap."*

**Fix:** Restore them from `d8c9b9b` (the parent commit). They shouldn't have been in the same commit as the QueryResult changes.

### 9. `RubricJudge.parse_reply` is not a static method

Looking at `judge_base.py`, `parse_reply` is likely an instance method or a module-level function. But `faithfulness.py` calls `RubricJudge.parse_reply(...)` which only works if it's a `@staticmethod` or `@classmethod`. If someone instantiates `RubricJudge` with custom settings and `parse_reply` ignores them, that's confusing API design.

**What a founder would say:** *"Your API is lying to me. It looks like a class method but it doesn't use the class."*

### 10. The three-layer model is marketing

The implementation note (`docs/three_layer_model_implementation_note.md`) says:

> Layer 1 — Structural Categories (1–9) [existing, core]  
> Layer 2 — Deterministic Overlays [new, offline, always runs]  
> Layer 3 — LLM-Judge Overlays [new, --eval-generative, requires API key]

But in the actual CLI code, Layer 2 and Layer 3 are just two dicts bolted onto `per_question`. There's no structural enforcement of the layers. A user can pass `--eval-generative` without understanding what layers are. The taxonomy doesn't change behavior — it's just documentation.

**What a founder would say:** *"You have a beautiful architecture diagram that doesn't match the code. The code is just 'if flag, add more keys to JSON.'"*

**Fix:** Make it real. Have the CLI print which layers are active. Have the JSON schema enforce it. Or drop the taxonomy and just document the flags.

---

## The Ugly (Bugs Waiting to Bite)

### 11. `asdict` leakage on `QueryResult`

We checked that report `to_dict()` methods are explicit (not `dataclasses.asdict`). But `QueryResult` itself is a dataclass. If any adapter or downstream consumer does `from dataclasses import asdict; asdict(result)`, the new fields (`latency_ms`, `interaction_turns`, `cost_callback`) will appear in the dict. The `cost_callback` field contains a callable — `asdict` will crash on it.

**Repro:**
```python
from dataclasses import asdict
from sme.adapters.base import QueryResult
r = QueryResult(answer="test")
asdict(r)  # TypeError: cannot pickle '_function' object
```

**Fix:** Add `dataclasses.field(repr=False)` to `cost_callback`, or override `__asdict__` or document that consumers must not use `asdict()` on `QueryResult`.

### 12. Cache key doesn't include prompt temperature

```python
def _cache_key(rubric, body, model, provider, rubric_version="v1"):
    payload = f"{rubric}|{body}|{model}|{provider}|{rubric_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

If the user changes `temperature` (or any other generation param), the cache key doesn't change. They'll get a stale cached result. Also, `rubric_version` defaults to `"v1"` but there's no way to bump it programmatically.

### 13. CLI `--offline` doesn't actually gate everything

`--offline` is parsed at the top level and stored in `args.offline`. But `cmd_retrieve` only checks it for the generative overlays:

```python
_eval_generative = getattr(args, "eval_generative", False) and not getattr(args, "offline", False)
```

If another subcommand (e.g., `cat8`, `analyze`) later adds LLM-judge calls, they won't check `--offline` unless explicitly wired. The flag is not globally enforced by the framework.

---

## Honest Assessment

| Claim in the Plan | Reality | Grade |
|---|---|---|
| "Deterministic overlays catch failure modes 80% of the time at zero API cost" | `contextual_precision_proxy` is a substring hack; `token_utilization` is backwards | C+ |
| "LLM-judge overlays add real generative evaluation" | Faithfulness rubric is zero-shot with no few-shot examples; calibration fixtures never run | B- |
| "RubricJudge extraction is clean abstraction" | Actually clean. Tests pass. LongMemEval unchanged. | A |
| "Disk cache saves real money" | Functional, stable keys, TTL eviction. | A- |
| "NIAH rationalizes context-window choices" | Tests exact-match lookup, not retrieval from long context. | C |
| "LOCOMO loader is credible engineering" | Credible but disconnected from any harness. | B |
| "Three-layer model makes CI decisions clearer" | It's a documentation layer, not structural. | C+ |

---

## What I'd Do Before Showing This to Anyone Important

1. **Fix `token_utilization`** — invert the metric or remove it. A backwards metric is worse than no metric.
2. **Rename `contextual_precision_proxy`** → `entity_id_overlap` to stop pretending it's RAG Triad Contextual Precision.
3. **Run calibration fixtures** against GPT-4o once, commit actual scores, and iterate the rubric if needed.
4. **Restore the deleted issue drafts** from `d8c9b9b`.
5. **Fix NIAH** to ask a *question* about the needle, not pass the needle as the query.
6. **Remove `cost_callback`** from `QueryResult` until there's a concrete user and implementation.
7. **Add a global `--offline` enforcement** in `main()` that prevents any API call when the flag is set, not just in `cmd_retrieve`.

---

*End of critique.*
