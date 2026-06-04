# SME Industry Integration Plan — Critique & Iteration (v2)

> **Status:** Implementation-ready revision.  
> **Date:** 2026-06-04  
> **Principle:** Harden before expand. Every new surface must survive the question: *"Will this break when the model version changes, when API prices shift, or when run without a network?"*

---

## 1. Critique of the v1 Plan

The v1 plan (`docs/industry_benchmark_gap_analysis_2026.md`) was directionally correct but had **five brittleness traps** that would have caused maintenance pain or misleading readings within one quarter of shipping.

### 1.1 Trap: LLM-Judge RAG Triad without calibration anchors

**What v1 proposed:** Add Faithfulness, Answer Relevancy, and Contextual Precision as new rubrics on the existing `longmemeval_judge.py` infrastructure.

**Why it's brittle:**
- The existing judge works because LongMemEval constrains the output to **five discrete labels** (`CORRECT`/`PARTIAL`/`INCORRECT`/`ABSTAIN`/`ERROR`). RAG Triad metrics require **continuous scores** (0.0–1.0) and **structured claim-level mappings** ("claim 3 is supported by chunk 7"). Getting an LLM to emit consistent continuous scores is an order of magnitude harder than discrete classification.
- Temperature=0 does not eliminate variance across model versions. GPT-4o-2024-08-06 and GPT-4o-2024-11-20 may score the same answer differently by ±0.15 on a 0–1 scale. Without a calibration fixture set and human-anchor baselines, the numbers drift silently.
- The v1 plan had **no calibration requirement**, no regression fixture set, and no caching strategy. Every developer running `pytest tests/test_rag_triad.py` would hit live API endpoints repeatedly.
- SME's own spec v8 lists "Human-judgment calibration without explicit calibration runs" as **deliberately out of scope** (issue #46). Adding generative metrics without addressing this is a spec violation.

**Hard truth:** We cannot ship calibrated, paper-faithful generative metrics in two weeks. We *can* ship deterministic approximations that catch the same failure modes 80% of the time at zero API cost.

### 1.2 Trap: TRACe via pure LLM judgment

**What v1 proposed:** Compute Utilization by asking the LLM judge to "map answer claims to source chunks," and Completeness by asking it to check subquestion coverage.

**Why it's brittle:**
- Claim-to-chunk alignment is an **active research problem** (see RAGAS's `faithfulness` implementation, which uses a multi-step pipeline: claim extraction → claim decomposition → NLI scoring per claim). Doing this in a single judge prompt is optimistic.
- It requires **multiple LLM calls per question** (extract claims → match claims → score coverage). At 500 questions × 3 calls × $0.005 = **$7.50 per run**, which is fine for CI, but without disk caching, iterative debugging costs add up fast.
- The v1 plan did not specify where this lives in the report pipeline. Is it part of `QueryResult`? A post-processing overlay? A new category?

### 1.3 Trap: Hardcoded API pricing YAML

**What v1 proposed:** `sme/eval/pricing.yaml` with OpenAI/Anthropic list prices.

**Why it's brittle:**
- OpenAI changed pricing **four times** in 2024–2025. A YAML file committed today is stale in 90 days.
- Users on Azure, enterprise tiers, or OpenRouter have **different effective prices** than list prices. Hardcoding list prices produces systematically wrong cost metrics for every non-retail user.
- Maintaining pricing tables is not core to SME's mission. It's a tax.

### 1.4 Trap: "Generalize the cross-validation harness"

**What v1 proposed:** Make `scripts/cross_validate_longmemeval.py` accept any conversational-memory dataset (LME, LOCOMO, EverMemBench) via a standard interface.

**Why it's brittle:**
- The existing harness is **568 lines** deeply specialized to LongMemEval's JSON shape, question-type taxonomy, haystack/session structure, and judge rubric dispatch.
- LOCOMO's data shape is different: ~300-turn dialogues with images, different question categories (single-hop, multi-hop, temporal, open-domain, adversarial), and no `expected_sources` session-id list.
- Abstracting two different shapes into a "standard interface" before we have a third shape is **premature abstraction** (Rule of Three). We'd end up with an interface that serves neither dataset well.
- The related-work doc maps *categories* (SME Cat 6a ≈ LOCOMO temporal), but category mapping ≠ data pipeline mapping.

### 1.5 Trap: `sentence-transformers` for NoLiMa paraphrase needles

**What v1 proposed:** Use `sentence-transformers` to generate paraphrase needles for a semantic NIAH variant.

**Why it's brittle:**
- `sentence-transformers` pulls in **PyTorch (~2GB)** and `transformers`. SME's core install is three lightweight packages (`numpy`, `networkx`, `pyyaml`). Adding PyTorch violates the "lightweight and locally runnable" constitutional principle.
- Generating semantically equivalent but lexically distinct needles is doable with simple synonym substitution (WordNet) or pre-cached paraphrase tables. It doesn't need a neural model at test-generation time.

---

## 2. What the v1 Plan Left Out

| Omission | Why it matters |
|---|---|
| **Disk cache for judge calls** | Without caching, every CI run and every developer re-running tests burns API credits. The existing `longmemeval_judge.py` has no cache either, but it's only used for batch cross-validation, not per-commit CI. |
| **Schema migration strategy for `QueryResult`** | Adding `latency_ms` and `cost_usd` changes the dataclass. Every adapter in the repo and every downstream consumer (notebooks, external adapters) must be audited. |
| **Where generative metrics live in the 9-category framework** | Categories 1–9 are structural. RAG Triad is generative. If we add it as an overlay, users need a mental model for how overlays relate to categories. If we add it as Cat 1b, we expand the framework. |
| **Deterministic fallback when LLM judge is unavailable** | SME must run in CI without API keys. The new metrics need graceful degradation (skip, zero-fill, or deterministic proxy) rather than ERROR-spam. |
| **Stompy "exploration overhead" metric** | The industry survey's most actionable finding: memory reduces wasted turns and tokens. The v1 plan added generic cost/latency but not *turns-per-correct* or *exploration overhead* — the memory-specific efficiency signal. |
| **Backward-compat contract for `to_dict()` reports** | `Cat2cReport.to_dict()`, `Cat8Report.to_dict()`, etc. are consumed by downstream dashboards. Adding new top-level keys without a nesting convention is a breaking change. |
| **Test fixture strategy for new rubrics** | Every new rubric needs a 10–20 example calibration fixture (hand-crafted answers with known scores) to detect prompt drift across model versions. |

---

## 3. Iterated Plan (v2)

### 3.1 Guiding Principles

1. **Deterministic before stochastic.** If a metric can be computed without an LLM call, do it. Use LLM judgment only for the dimensions that genuinely require semantic understanding (faithfulness of generated claims).
2. **Adapter-agnostic before adapter-specific.** New harness-layer features (timing, cost hooks) must not require editing every adapter.
3. **Cache by default.** Any code path that hits an API must write to a disk cache keyed by `(input_hash, rubric_version, model_id)`.
4. **Fail soft, not hard.** When API keys are missing, metrics degrade to "unavailable" — they do not crash the run.
5. **Calibrate before ship.** Every LLM-judge rubric must have a `tests/test_*_calibration.py` with hand-crafted fixtures asserting known-good labels.

### 3.2 Revised Architecture: Three Layers

Instead of bolting everything onto the 9 categories, introduce a clean **three-layer model**:

```
Layer 1 — Structural Categories (1–9)          [existing, core]
Layer 2 — Deterministic Overlays               [new, runs offline]
Layer 3 — LLM-Judge Overlays                   [new, requires API key]
```

- **Layer 1** is unchanged. It answers: "Is the graph healthy?"
- **Layer 2** answers: "Is the retrieval efficient and precise?" — computed from `QueryResult` fields without API calls.
- **Layer 3** answers: "Is the generated answer faithful and complete?" — computed via LLM judge, gated behind `--eval-generative`.

This lets users run SME in CI (Layers 1+2 only) and opt into Layer 3 when they have API keys and want the full picture.

### 3.3 Phase 1: Deterministic Overlays (Week 1–2)

These are high-value, zero-brittle, and address the same gaps as the RAG Triad without LLM calls.

#### 3.3.1 Contextual Precision (deterministic proxy)

**Metric:** `contextual_precision = len(relevant_chunks) / len(retrieved_chunks)`

**How:** A chunk is "relevant" if it contains at least one expected-source substring (same logic as SME's existing substring recall). This penalizes noise without calling an LLM.

**File:** `sme/eval/deterministic_overlays.py`
**Test:** `tests/test_deterministic_overlays.py`
**Integration:** Add to `retrieve` JSON output as `overlay.contextual_precision` (nested, not top-level — backward compat).

**Limitation:** It only works when expected sources are known (benchmark corpora like LME/CKG). For ad-hoc user queries without oracle annotations, it returns `null`. This is acceptable — it's a diagnostic overlay, not a universal metric.

#### 3.3.2 Token Utilization (deterministic proxy for TRACe Utilization)

**Metric:** `token_utilization = len(tokenize(answer)) / len(tokenize(context_string))`

**How:** If the answer is shorter than the context, the model likely compressed. If it's longer, it may have hallucinated or elaborated. This is a **weak signal** — it correlates with utilization but does not prove it. Document it as such.

**File:** `sme/eval/deterministic_overlays.py`
**Integration:** Same overlay namespace.

#### 3.3.3 Latency Tracking (harness-level, no adapter changes)

**How:** Wrap `adapter.query()` in a timing decorator inside the harness/CLI layer.

```python
# In sme/cli.py or harness layer
start = time.perf_counter()
result = adapter.query(question)
latency_ms = (time.perf_counter() - start) * 1000
```

**File:** Add `latency_ms` to `QueryResult` with default `0.0`. Populate it in the CLI harness, not in adapters.
**Test:** `tests/test_adapter_contract.py` already has parametric adapter tests — extend `test_query_returns_QueryResult` to assert `latency_ms >= 0`.

**Why this way:** Zero adapter changes. No wrapper complexity. Works for all adapters immediately.

#### 3.3.4 Cost Hook (opt-in, no hardcoded prices)

**How:** Add a `cost_callback: Optional[Callable[[int, int, str], float]] = None` to `QueryResult`.

- `cost_callback(prompt_tokens, completion_tokens, provider_name) -> float`
- When the harness calls the judge or the adapter calls an LLM, it passes the token counts to the callback.
- SME ships a **default no-op callback** that returns `0.0`.
- Users who care about cost provide their own callback (e.g., reading from their own pricing table or API dashboard).

**File:** `sme/adapters/base.py` (add field), `sme/eval/cost_tracker.py` (helper)
**Test:** `tests/test_cost_tracker.py`

**Why this way:** Avoids the pricing-YAML maintenance trap. Respects different pricing tiers. Keeps SME agnostic.

#### 3.3.5 Exploration Overhead (Stompy-style)

**Metric:** For adapters that expose multi-turn interaction, count `interaction_turns` per correct answer. Single-turn adapters report `1`.

**How:** Add `interaction_turns: int = 1` to `QueryResult`. Adapters that do multi-step retrieval (e.g., iterative graph traversal) increment this. The CLI tracks the total.

**Report:** `exploration_overhead = mean(interaction_turns)` across correct answers, broken down by Condition (A/B/C).

**File:** `sme/adapters/base.py`, `sme/categories/multi_hop.py` (extend `Cat2cReport`)
**Test:** `tests/test_multi_hop.py`

### 3.4 Phase 2: LLM-Judge Overlays (Week 3–4, gated behind calibration)

Only proceed to Phase 2 after Phase 1 is merged, tested, and the harness can populate the new `QueryResult` fields reliably.

#### 3.4.1 Generic RubricJudge base class

**What:** Extract the retry logic, provider dispatch, and response parsing from `longmemeval_judge.py` into `sme/eval/judge_base.py`.

**Interface:**
```python
class RubricJudge:
    def __init__(self, provider="openai", model=None, client=None)
    def judge(self, rubric: str, body: str) -> dict  # content, usage, error
```

**Why:** The existing `grade_answer` conflates rubric construction with API calling. Separating them lets Phase 2 rubrics reuse the same retry/cache layer without duplicating `_call_openai_compat`, `_call_anthropic`, `_retry`, etc.

**File:** `sme/eval/judge_base.py`
**Test:** `tests/test_judge_base.py`

#### 3.4.2 Faithfulness Rubric (LLM-based, calibrated)

**Rubric design:** Single LLM call, binary output per claim.

```
You are a fact-checker. Given the CONTEXT and the ANSWER, list each
claim in the answer. For each claim, mark it:
  - SUPPORTED: directly found in context
  - CONTRADICTED: context says the opposite
  - UNSUPPORTED: not in context

Reply as JSON: {"claims": [{"text": "...", "verdict": "SUPPORTED|..."}]}
```

**Calibration requirement:** Before shipping, create `tests/test_faithfulness_calibration.py` with 15 hand-crafted examples:
- 5 fully supported
- 3 contradicted
- 4 unsupported (hallucinations)
- 3 partially supported

Assert that GPT-4o-2024-08-06 scores ≥ 13/15 correctly. If it fails, iterate the rubric. This is the **anchor** that prevents silent drift.

**File:** `sme/eval/faithfulness.py`
**Test:** `tests/test_faithfulness.py` (mocked), `tests/test_faithfulness_calibration.py` (live API, marked `slow`)

#### 3.4.3 Answer Relevancy Rubric (LLM-based, calibrated)

**Rubric design:**
```
Rate how directly the ANSWER addresses the QUESTION.
- 1.0: fully addresses all aspects
- 0.5: partially addresses, misses sub-questions
- 0.0: irrelevant or refuses incorrectly
Reply as JSON: {"score": 0.0-1.0, "rationale": "..."}
```

**Calibration:** 10 examples with known scores.

**File:** `sme/eval/answer_relevancy.py`
**Test:** `tests/test_answer_relevancy.py`, `tests/test_answer_relevancy_calibration.py`

#### 3.4.4 Judge Response Disk Cache

**What:** Before every API call, check `~/.cache/sme-eval/judge/{hash}.json`. If present and `< 30 days old`, return it.

**Key:** `hashlib.sha256(rubric + body + model + provider + "v1")`

**Why:** Makes iterative development and CI caching possible. The v1 plan had no cache.

**File:** `sme/eval/judge_cache.py`
**Test:** `tests/test_judge_cache.py`

### 3.5 Phase 3: LOCOMO (Week 5–6, copy-pattern, not abstraction)

**Revised approach:** Do **not** generalize `cross_validate_longmemeval.py`. Instead:

1. Write `sme/corpora/locomo_loader.py` — map LOCOMO JSON to SME's internal `Question` dataclass.
2. Write `scripts/cross_validate_locomo.py` — **copy the pattern** of `cross_validate_longmemeval.py` but adapted to LOCOMO's shape. Reuse `grade_answer` and the judge infrastructure.
3. After both harnesses exist and are stable, **then** consider extracting common utilities (e.g., `sme.harness.common.py` with `disagreement_detection`, `per_category_aggregation`).

**Why copy-pattern:** LOCOMO's question types (single-hop, multi-hop, temporal, open-domain, adversarial) do not map 1:1 to LME's types. A premature abstraction would force both datasets into a least-common-denominator shape, losing per-benchmark nuance.

**File:** `sme/corpora/locomo_loader.py`, `scripts/cross_validate_locomo.py`
**Test:** `tests/test_locomo_loader.py`, `tests/test_cross_validate_locomo.py`

**Multi-modal skip:** LOCOMO includes ~32 images per dialogue. SME is text-only. The loader skips image-dependent questions and logs a `skipped_multimodal` count.

### 3.6 Phase 4: Synthetic NIAH (Week 7–8, text-only, no torch)

**Revised approach:**

1. **Literal NIAH:** Insert exact-match needles into a distractor corpus. Use public-domain text (Project Gutenberg, CC0 Wikipedia excerpts) or simple synthetic generation (`lorem` style).
2. **Skip NoLiMa for now.** Semantic paraphrase needles require either `sentence-transformers` (PyTorch, too heavy) or an LLM call per needle (too expensive for synthetic data generation). Revisit when SME has a lighter paraphrase library or when a multimodal adapter ships.
3. **Sequential NIAH:** Insert 3–5 ordered needles and test whether retrieval returns them in the correct sequence. This is a lightweight extension of literal NIAH.

**File:** `sme/eval/niah.py`
**Test:** `tests/test_niah.py`
**CLI:** `sme-eval niah --adapter <name> --corpus-size 10000 --needles 5`

### 3.7 Phase 5: Hardening & Integration (Week 9)

1. **Audit all `to_dict()` methods** for backward compatibility. New fields must be nested under an `overlays` or `extensions` key, not top-level.
2. **Add `--offline` CLI flag.** When set, Layer 3 (LLM-judge) metrics are skipped. Layers 1+2 run normally.
3. **Document the three-layer model** in `docs/sme_spec_v8.md` (or v9) so users understand when API keys are needed.
4. **Run a full calibration pass** on all new LLM-judge rubrics and commit the calibration fixture sets to `tests/fixtures/calibration/`.

---

## 4. What We Still Explicitly Reject

These remain out of scope per SME's constitutional principle:

| Rejected Item | Reason |
|---|---|
| **Full RAGAS/DeepEval/TruLens integration** | Too heavy, too opinionated. We borrow their *concepts* but not their code. |
| **NoLiMa with neural paraphrase** | Requires PyTorch. Violates "lightweight and locally runnable." |
| **MM-NIAH (multimodal)** | SME is text-only. Wait for Cat 10 or multimodal adapter. |
| **Hardcoded API pricing tables** | Maintenance trap. Use callback hooks instead. |
| **Generalized cross-validation harness abstraction** | Premature. Two datasets don't justify an abstraction layer yet. |
| **LangChain/LlamaIndex native inheritance** | Framework lock-in. Keep the thin compat wrapper. |
| **Full pyshacl engine** | Already documented as Tier 3. JSON-LD emitter is sufficient. |

---

## 5. Implementation Task Table (v2)

### Phase 1: Deterministic Overlays (Weeks 1–2)

| Task | File(s) | Test(s) | Brittle? |
|---|---|---|---|
| Add `latency_ms`, `interaction_turns`, `cost_callback` to `QueryResult` (all with safe defaults) | `sme/adapters/base.py` | `tests/test_adapter_contract.py` | **No** — defaults preserve backward compat |
| Add harness-level timing wrapper | `sme/cli.py` | manual / existing harness tests | **No** |
| Implement deterministic Contextual Precision | `sme/eval/deterministic_overlays.py` | `tests/test_deterministic_overlays.py` | **No** — substring based |
| Implement deterministic Token Utilization | `sme/eval/deterministic_overlays.py` | `tests/test_deterministic_overlays.py` | **No** — tiktoken based |
| Implement CostTracker helper | `sme/eval/cost_tracker.py` | `tests/test_cost_tracker.py` | **No** — callback pattern |
| Extend `Cat2cReport` with `exploration_overhead` | `sme/categories/multi_hop.py` | `tests/test_multi_hop.py` | **No** — additive field |
| Wire overlays into `retrieve` JSON output under `overlays` key | `sme/cli.py` | `tests/test_cli.py` | **No** — nested, ignored by old consumers |

### Phase 2: LLM-Judge Overlays (Weeks 3–4)

| Task | File(s) | Test(s) | Brittle? |
|---|---|---|---|
| Extract `RubricJudge` base class + disk cache | `sme/eval/judge_base.py`, `sme/eval/judge_cache.py` | `tests/test_judge_base.py`, `tests/test_judge_cache.py` | **Medium** — cache key versioning required |
| Write Faithfulness rubric + calibration fixture | `sme/eval/faithfulness.py` | `tests/test_faithfulness.py`, `tests/test_faithfulness_calibration.py` | **High** — mitigated by calibration |
| Write Answer Relevancy rubric + calibration fixture | `sme/eval/answer_relevancy.py` | `tests/test_answer_relevancy.py`, `tests/test_answer_relevancy_calibration.py` | **High** — mitigated by calibration |
| Wire `--eval-generative` flag + `--offline` flag | `sme/cli.py` | `tests/test_cli.py` | **No** |

### Phase 3: LOCOMO (Weeks 5–6)

| Task | File(s) | Test(s) | Brittle? |
|---|---|---|---|
| LOCOMO loader | `sme/corpora/locomo_loader.py` | `tests/test_locomo_loader.py` | **Low** |
| LOCOMO cross-validation harness (copy-pattern) | `scripts/cross_validate_locomo.py` | `tests/test_cross_validate_locomo.py` | **Medium** — judge variance, mitigated by skip-judge path |

### Phase 4: Synthetic NIAH (Weeks 7–8)

| Task | File(s) | Test(s) | Brittle? |
|---|---|---|---|
| Literal + Sequential NIAH | `sme/eval/niah.py` | `tests/test_niah.py` | **No** |
| `sme-eval niah` CLI | `sme/cli.py` | manual | **No** |

### Phase 5: Hardening (Week 9)

| Task | File(s) | Test(s) | Brittle? |
|---|---|---|---|
| Backward-compat audit for all `to_dict()` methods | all `to_dict()` in `sme/categories/` | existing tests + schema checks | **No** |
| `--offline` flag implementation | `sme/cli.py` | `tests/test_cli.py` | **No** |
| Update spec v8/v9 with three-layer model | `docs/sme_spec_v8.md` | — | **No** |
| Final calibration run + fixture commit | `tests/fixtures/calibration/` | all calibration tests | **No** |

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Faithfulness rubric fails calibration (GPT-4o scores < 13/15) | Medium | High | Iterate rubric for 3 rounds max; if still failing, ship without it and document as "future work." |
| LOCOMO dataset changes shape (new release) | Low | Medium | Pin to specific GitHub release/tag in loader docs. |
| Adding `latency_ms` to `QueryResult` breaks external adapters | Low | High | Default value `0.0` means old adapters compile; document in changelog. |
| Judge cache grows unbounded | Medium | Low | Add 30-day TTL + LRU eviction in `judge_cache.py`. |
| Cost callback is never populated by adapters | High | Low | Document clearly that cost tracking is opt-in; default is zero. |
| Deterministic Contextual Precision confuses users ("why doesn't it use an LLM?") | Medium | Low | Name it `contextual_precision_proxy` in output to signal approximation. |

---

*End of v2 iteration.*
