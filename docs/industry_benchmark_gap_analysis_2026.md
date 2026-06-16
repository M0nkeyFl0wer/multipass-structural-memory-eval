# SME Test Suite vs. Industry Benchmarks — Gap Analysis & Integration Roadmap

> **Date:** 2026-06-04  
> **Scope:** `multipass-structural-memory-eval` existing test surface vs. the four benchmark families described in the industry survey (RAG Triad/TRACe, Conversational Memory, NIAH variants, Domain-Specific Reasoning).  
> **Purpose:** Identify where SME already covers industry patterns, where it reinvents wheels, and where adopting external methodologies would strengthen the framework without violating its "lightweight and locally runnable" constitutional principle.

---

## 1. Executive Summary

SME's test suite is **structurally unique** — no industry benchmark covers Categories 4 (Ingestion Integrity), 5 (Gap Detection via TDA), 7 (Token Efficiency with A/B/C isolation), or 8 (Ontology Coherence). These are SME's defensible contribution and should not be diluted.

However, SME is **weak on generative evaluation** — it tests retrieval and graph structure exhaustively but does not systematically evaluate whether the *answer* the LLM generates from retrieved context is (a) faithful to that context, (b) relevant to the query, or (c) complete. The industry has consolidated on the **RAG Triad** (Contextual Relevancy, Faithfulness, Answer Relevancy) plus **TRACe** (Utilization, Completeness) for exactly this gap. SME should add lightweight, local versions of these metrics.

Similarly, SME's conversational-memory coverage is **longitudinally thin** — we cross-validate against LongMemEval but lack the very-long-horizon, multi-session stress that LOCOMO provides. SME also lacks **efficiency/cost benchmarking** (Stompy-style API cost, interaction turns, wall-clock time) and **semantic NIAH** (NoLiMa-style associative retrieval).

**Bottom line:** SME should adopt industry-standard *generative-evaluation* and *efficiency* metrics as additive layers on top of its existing structural diagnostics, rather than rebuilding them from scratch. Its structural categories (4, 5, 7, 8) remain distinctive and should be deepened, not replaced.

---

## 2. What SME Already Has (Mapped to Industry Categories)

### 2.1 RAG Triad & LLM-as-a-Judge

| Industry Metric | SME Equivalent | Status | Notes |
|---|---|---|---|
| **Contextual Relevancy / Precision** | Cat 1 (`sme_recall`, substring match of expected sources) | **Partial** | SME measures whether expected sources appear in retrieved context, but does NOT penalize *unnecessary* context (noise). A system returning 100 chunks when only 3 are needed scores perfect on SME Cat 1 but would fail Contextual Precision. |
| **Faithfulness / Groundedness** | *None* | **Missing** | SME verifies structural claims (Cat 8e) and graph topology, but never checks whether the *LLM's generated answer* is supported by the retrieved context. A hallucinated answer on perfect retrieval is invisible to SME. |
| **Answer Relevancy** | *None* | **Missing** | SME's `QueryResult.answer` field is populated by adapters but never scored. The framework is retrieval-centric; generative quality is out of scope per `sme_spec_v8.md` §Limitations. |
| **TRACe: Utilization** | *None* | **Missing** | SME tokenizes `context_string` (Cat 7) but does not measure how much of that context the LLM *used* in its answer. |
| **TRACe: Completeness** | *None* | **Missing** | SME's Cat 2c measures whether the *retriever* found all relevant graph nodes, but not whether the *generator* incorporated all relevant retrieved information. |
| **LLM-as-a-Judge** | `sme/eval/longmemeval_judge.py` | **Present** | Paper-faithful GPT-4o judge for LongMemEval (CORRECT/INCORRECT/ABSTAIN/PARTIAL). Multi-provider (OpenAI, Anthropic, OpenRouter). Good bones, but only applied to LongMemEval-format QA. |

**Verdict:** SME has a solid judge infrastructure but applies it narrowly to LongMemEval answer correctness. It does not use an LLM judge for the RAG Triad dimensions. The gap is **not infrastructure** — it's **scoring functions** that call the existing judge with different rubrics.

### 2.2 Conversational Memory Benchmarks

| Benchmark | SME Equivalent | Status | Notes |
|---|---|---|---|
| **LongMemEval** | `scripts/cross_validate_longmemeval.py` + `tests/test_cross_validate_longmemeval.py` | **Direct integration** | SME runs its adapters against the LME dataset and compares SME structural recall against the LME judge's correctness labels. This is SME's strongest external-calibration surface. |
| **LOCOMO** | *None* | **Missing** | LOCOMO tests ~300-turn, ~9,000-token, multi-session dialogues over up to 35 sessions. SME's longest horizon is LongMemEval (~50 sessions, shorter per-session). LOCOMO's temporal and adversarial categories are richer. |
| **LongMemEval variants** (BEAM, MemoryArena) | *None* | **Missing** | BEAM tests belief updating; MemoryArena tests competitive multi-agent settings. Both are adjacent to SME's Cat 3 (Contradiction Detection) but more sophisticated. |
| **Stompy efficiency metrics** (API cost, turns, wall-clock) | Cat 7 token efficiency (`multi_hop.py`) | **Partial** | SME measures tokens-per-correct-answer but NOT API cost, number of interaction turns, or wall-clock latency. These are load-bearing for production rationalization. |

**Verdict:** SME should ingest LOCOMO as a corpus (the related-work doc already proposes this) and add Stompy-style efficiency tracking. The judge infrastructure already supports multi-provider; adding cost/latency hooks is mechanical.

### 2.3 Needle-in-a-Haystack (NIAH) Stress Tests

| Variant | SME Equivalent | Status | Notes |
|---|---|---|---|
| **Single-needle NIAH** | *None explicitly* | **Missing** | SME's retrieval tests use real corpora with expected-source annotations, not synthetic sparse needles in distractor data. |
| **Sequential-NIAH** | *None* | **Missing** | No test forces the model to preserve order of multiple needles across a long context. |
| **NoLiMa (Nonliteral / Semantic NIAH)** | *None* | **Missing** | All SME retrieval scoring is literal/substring based (`sme_substring_recall`). No test requires associative or semantic retrieval with minimal lexical overlap. |
| **MM-NIAH (Multimodal)** | *None* | **Missing** | SME is text-only. No image+text retrieval or vision-memory tests. |

**Verdict:** SME's retrieval philosophy is "real corpus, real questions" rather than synthetic stress tests. This is defensible for diagnosis but means SME cannot rationalize context-window expansion choices the way NIAH benchmarks do. A lightweight synthetic NIAH suite (text-only) would complement the real-corpus tests without replacing them.

### 2.4 Multi-Step & Domain-Specific Reasoning

| Benchmark | SME Equivalent | Status | Notes |
|---|---|---|---|
| **ORAN-Bench-13K** (telecom) | *None* | **Missing** |
| **τ-voice Bench** (enterprise workflows) | *None* | **Missing** |
| **ThermoQA / GeoChallenge / M2-Verify** | *None* | **Missing** |
| **CKG-Benchmark** (education/concept DAGs) | `sme/adapters/ckg.py` + `docs/ckg_benchmark_experiment.md` | **Direct integration** | SME's A/B/C isolation (flat vs structured vs flat-equivalent) is a genuine contribution to Yarmoluk's benchmark. This is SME's domain-specific strength. |

**Verdict:** SME has one strong domain-specific integration (CKG) but no others. The framework is designed to be adapter-agnostic — adding new domain-specific benchmark adapters is the intended extension pattern. No structural changes needed; the gap is corpus coverage.

---

## 3. Where SME Reinvents the Wheel (And Whether That's OK)

### 3.1 B-Cubed Clustering Evaluation

**What SME does:** `sme/categories/_bcubed.py` implements Bagga & Baldwin 1998 from scratch, integrated with collision-group detection.

**Industry alternative:** `pybubed`, `cluster-evaluation` packages.

**Verdict:** **Acceptable.** The integration with `collision_groups_to_clusters` (filtering singleton groups, handling adapter-specific entity shapes) is tight enough that an off-the-shelf library would require significant wrapping. The test file (`test_bcubed.py`) includes the canonical literature example, which is good scientific practice.  
**Recommendation:** Keep as-is. Optionally add a cross-check test that runs the same inputs through `sklearn.metrics` adjusted Rand index to confirm agreement on simple cases.

### 3.2 SHACL-like Audit Reports (Cat 8f)

**What SME does:** `sme/categories/external_fit.py` emits JSON-LD shaped like a SHACL ValidationReport with `sh:Violation`, `sh:Info`, `sh:conforms`, etc.

**Industry alternative:** `pyshacl` (full SHACL engine), `rdflib` + OWL reasoners.

**Verdict:** **Acceptable and documented.** `sme_spec_v8.md` and `test_cat8_shacl_conformance.py` explicitly note this is a *lightweight first tier* — real SHACL engines are Tier 3 (deliberately out of scope). The test verifies that the emitted JSON-LD parses correctly in `rdflib` and that severity terms resolve to real SHACL IRIs.  
**Recommendation:** Keep as-is. The tradeoff is explicit and defensible.

### 3.3 LongMemEval Judge

**What SME does:** `sme/eval/longmemeval_judge.py` replicates the LME judge methodology (prompt rubrics, JSON response parsing, retry logic) with multi-provider support.

**Industry alternative:** The LongMemEval repo provides `evaluate_qa.py`; DeepEval/RAGAS provide generic LLM judges.

**Verdict:** **Acceptable.** SME needed (a) methodology-faithfulness tracking (only GPT-4o-2024-08-06 via OpenAI is "paper-faithful"), (b) multi-provider support (Anthropic for cost, OpenRouter for fallback), and (c) graceful degradation when no API key is present. None of the existing packages provide this combination.  
**Recommendation:** Keep as-is. Consider wrapping the judge in a generic `RubricJudge` class so the same infrastructure can serve RAG Triad rubrics without duplicating retry/parse logic.

### 3.4 Persistent Homology (Ripser wrapper)

**What SME does:** `sme/categories/gap_detection.py` wraps `ripser` to compute Betti numbers on the largest connected component.

**Industry alternative:** `gudhi`, `scikit-tda`.

**Verdict:** **Acceptable.** Ripser is the standard for fast persistent homology; SME's usage is a thin wrapper. No wheel is being reinvented — it's just using the library.  
**Recommendation:** Keep as-is.

### 3.5 Adapter Contract Test Framework

**What SME does:** `test_adapter_contract.py` provides parametric contract tests across all registered adapters.

**Industry alternative:** `pytest-harness`, `hypothesis` stateful testing, Pact contract testing.

**Verdict:** **Acceptable and well-designed.** The parametric fixture pattern (`ADAPTER_FACTORIES`) is clean and extensible. This is SME's core value — architecture-agnostic testing — and industry contract-testing tools are overkill for this scale.  
**Recommendation:** Keep as-is. Add more adapters to the registry rather than changing the framework.

---

## 4. Gap Analysis: What to Add or Incorporate

### 4.1 High Priority: RAG Triad + TRACe Generative Metrics

**Gap:** SME measures retrieval quality but not generative quality. A system can retrieve perfectly and generate a hallucinated answer; SME would score it as perfect.

**Proposed additions:**

1. **`sme/eval/rag_triad.py`** — Lightweight, locally runnable scorers using the existing `longmemeval_judge.py` infrastructure with new rubrics:
   - **Contextual Precision:** "Rate what fraction of the retrieved context is necessary to answer the query. 1 = every retrieved sentence is used; 0 = most is irrelevant." (LLM judge on retrieved chunks vs. query)
   - **Faithfulness:** "For each claim in the answer, label it as 'supported by context', 'contradicted by context', or 'not in context'." (LLM judge on answer vs. context_string)
   - **Answer Relevancy:** "Rate how directly and usefully the answer addresses the query." (LLM judge on answer vs. query)

2. **`sme/eval/trace.py`** — TRACe extensions:
   - **Utilization:** `len(answer_claims_supported_by_context) / len(retrieved_chunks)` — how much retrieved context was actually used. Can be approximated by asking the LLM judge to map answer claims to source chunks.
   - **Completeness:** `len(query_subquestions_answered) / len(query_subquestions)` — did the answer cover all aspects of the query? Again, LLM-judge based.

**Implementation notes:**
- Reuse `sme/eval/longmemeval_judge.py` — add rubric templates for each metric.
- These are **additive** — they run on top of existing retrieval results, not replacing them.
- Keep them in `sme/eval/` (not `sme/categories/`) to maintain the distinction between structural categories and generative-evaluation overlays.
- Add `tests/test_rag_triad.py` with mocked judge responses, following the pattern in `test_longmemeval_judge.py`.

### 4.2 High Priority: Stompy-Style Efficiency Metrics

**Gap:** SME's Cat 7 measures tokens but not cost, latency, or interaction overhead. For production rationalization, these are often decisive.

**Proposed additions:**

1. **API Cost Tracking:** Add `cost_usd` field to `QueryResult` and judge-call metadata. Use provider-specific token pricing (cached in `sme/eval/pricing.yaml`).
2. **Wall-Clock Latency:** Add `latency_ms` to `QueryResult` (time from query emission to response receipt) and `ProbeResult`.
3. **Interaction Turns:** For adapters that support multi-turn (future), count turns per correct answer.
4. **`sme/categories/efficiency.py`** (or extend Cat 7) to report:
   - `cost_per_correct_usd`
   - `latency_per_correct_ms`
   - `tokens_per_dollar` (efficiency normalized by spend)

**Implementation notes:**
- Latency can be measured at the adapter level (wrap `query()` calls).
- Cost requires a pricing table; start with OpenAI/Anthropic list prices, allow override.
- Add to `Cat2cReport` and `Cat7Report` as additive fields.
- Tests: `test_efficiency.py` with mocked adapter timing and pricing.

### 4.3 Medium Priority: LOCOMO Corpus Loader

**Gap:** SME's longest-horizon conversational memory test is LongMemEval. LOCOMO's ~300-turn, 35-session dialogues would stress temporal reasoning (Cat 6) and multi-hop (Cat 2c) more severely.

**Proposed addition:**

1. **`sme/corpora/locomo_loader.py`** — Load LOCOMO's released JSON into SME's session/question format.
2. **Integration with `cross_validate_longmemeval.py`** — Generalize the harness to accept any conversational-memory dataset (LME, LOCOMO, EverMemBench) with a standard interface.

**Implementation notes:**
- The related-work doc (`docs/related_work/locomo-and-memorybench.md`) already maps LOCOMO categories to SME categories — this is pre-rationalized.
- LOCOMO is multi-modal (images). SME is text-only, so image questions would be skipped or marked "untestable."
- Add `tests/test_locomo_loader.py` following `test_longmemeval_loader.py` pattern.

### 4.4 Medium Priority: Synthetic NIAH (Text-Only)

**Gap:** SME cannot rationalize context-window size or embedding-model choices for semantic retrieval.

**Proposed addition:**

1. **`sme/eval/niah.py`** — Synthetic needle insertion:
   - Generate distractor corpus (random Wikipedia paragraphs or synthetic text).
   - Insert needles: (a) literal match, (b) paraphrase/semantic match (NoLiMa-style), (c) sequential orderings.
   - Run adapter retrieval and score recall.
   - Report recall vs. context depth and needle sparsity.

**Implementation notes:**
- Use `sentence-transformers` or an LLM to generate paraphrase needles for the NoLiMa variant.
- This is intentionally synthetic — keep it separate from the real-corpus categories.
- Add `tests/test_niah.py` with small distractor sets and known needle positions.

### 4.5 Low Priority: Domain-Specific Benchmark Adapters

**Gap:** SME only has CKG as a domain-specific benchmark.

**Proposed additions:**

1. **ORAN-Bench-13K adapter** — For telecom/5G reasoning. Add if the project has a user in that domain.
2. **τ-voice Bench adapter** — For enterprise workflow reasoning (retail, aviation, telecom).
3. **Scientific reasoning suite** — ThermoQA, GeoChallenge, M2-Verify adapters.

**Implementation notes:**
- These are pure adapter work — no framework changes needed.
- The pattern is already established in `CKGAdapter`.
- Add on demand per user request rather than speculatively.

---

## 5. Concrete Implementation Roadmap

### Phase 1: Generative Evaluation (Weeks 1–2)

| Task | File(s) | Test File |
|---|---|---|
| Extract generic `RubricJudge` from `longmemeval_judge.py` | `sme/eval/judge_base.py` | `tests/test_judge_base.py` |
| Add Contextual Precision rubric | `sme/eval/rag_triad.py` | `tests/test_rag_triad.py` |
| Add Faithfulness rubric | `sme/eval/rag_triad.py` | `tests/test_rag_triad.py` |
| Add Answer Relevancy rubric | `sme/eval/rag_triad.py` | `tests/test_rag_triad.py` |
| Wire RAG Triad into `retrieve` CLI as optional `--eval-generative` flag | `sme/cli.py` | `tests/test_cli.py` |

### Phase 2: Efficiency Metrics (Weeks 2–3)

| Task | File(s) | Test File |
|---|---|---|
| Add `latency_ms`, `cost_usd` to `QueryResult` dataclass | `sme/adapters/base.py` | `tests/test_adapter_contract.py` |
| Create `sme/eval/pricing.yaml` with OpenAI/Anthropic list prices | `sme/eval/pricing.yaml` | `tests/test_pricing.py` |
| Extend Cat 7 with cost/latency per correct | `sme/categories/multi_hop.py` | `tests/test_multi_hop.py` |
| Add `--track-efficiency` CLI flag | `sme/cli.py` | — |

### Phase 3: LOCOMO Integration (Weeks 3–4)

| Task | File(s) | Test File |
|---|---|---|
| LOCOMO corpus loader | `sme/corpora/locomo_loader.py` | `tests/test_locomo_loader.py` |
| Generalize cross-validation harness to multi-dataset | `scripts/cross_validate_longmemeval.py` | `tests/test_cross_validate_longmemeval.py` |
| Add LOCOMO category mapping to related-work doc | `docs/related_work/locomo-and-memorybench.md` | — |

### Phase 4: Synthetic NIAH (Weeks 4–5, optional)

| Task | File(s) | Test File |
|---|---|---|
| NIAH needle inserter + evaluator | `sme/eval/niah.py` | `tests/test_niah.py` |
| NoLiMa paraphrase needle generator | `sme/eval/niah.py` | `tests/test_niah.py` |
| Add `sme-eval niah` CLI subcommand | `sme/cli.py` | — |

---

## 6. What NOT to Add (Anti-Recommendations)

To preserve SME's identity and avoid bloat, the following industry trends should be **explicitly rejected** or **delegated to Tier 3** (per `sme_spec_v8.md` §Heavyweight integrations):

1. **Full DeepEval/RAGAS/TruLens integration.** These frameworks are large, server-dependent, and opinionated about their own pipeline shapes. SME's 300-LOC judge wrapper is the right tradeoff. If users need full RAGAS, they can run it side-by-side; SME should not import it.

2. **MM-NIAH (multimodal needle-in-haystack).** SME is text-only today. Adding vision would require a fundamental architecture change (image embeddings, multimodal adapters). Defer until Cat 10 or a dedicated multimodal adapter ships.

3. **LangChain/LlamaIndex native adapter inheritance.** SME already ships an opt-in compat wrapper. Making the core ABC inherit from LangChain chains would violate the "no framework lock-in" principle.

4. **Full pyshacl engine for Cat 8f.** The lightweight JSON-LD emitter is working and tested. A full SHACL engine is overkill for a diagnostic framework and would add `rdflib` + `pyshacl` as required dependencies.

---

## 7. Summary Table

| Industry Benchmark Family | SME Coverage | Gap Severity | Proposed Action |
|---|---|---|---|
| **RAG Triad** (Contextual Precision, Faithfulness, Answer Relevancy) | Infrastructure exists, rubrics missing | **High** | Add `sme/eval/rag_triad.py` with 3 rubrics, reuse judge infrastructure |
| **TRACe** (Utilization, Completeness) | Entirely missing | **High** | Add `sme/eval/trace.py` as TRACe overlay on existing retrieval results |
| **LOCOMO** (long-horizon conversational memory) | Loader missing | **Medium** | Add `sme/corpora/locomo_loader.py`, generalize cross-validation harness |
| **Stompy efficiency** (cost, latency, turns) | Tokens only | **Medium** | Extend Cat 7 with cost/latency fields; add pricing table |
| **NIAH / Sequential NIAH** | None | **Low-Medium** | Add synthetic `sme/eval/niah.py` for context-window rationalization |
| **NoLiMa** (semantic NIAH) | None | **Low-Medium** | Add paraphrase needle variant to NIAH suite |
| **Domain-specific** (ORAN, τ-voice, etc.) | CKG only | **Low** | Add adapters on demand; no framework changes needed |
| **MM-NIAH** (multimodal) | N/A | **Out of scope** | Reject until multimodal adapter exists |

---

## 8. Appendix: Existing Test Inventory (For Reference)

**Structural / Graph Tests:**
- `test_graph_mapping.py` — Graph projection (wings, rooms, tunnels, KG entities/triples)
- `test_ontology_coherence.py` — Cat 8 (type coverage, edge vocabulary, schema alignment, drift, hall usage, claim verification)
- `test_gap_detection.py` — Cat 5 (components, bridges, isolates, candidate gaps, persistent homology via Ripser)
- `test_brokerage.py` — Cat 5 Burt structural-hole brokerage
- `test_bcubed.py` — B-Cubed clustering evaluation (Bagga & Baldwin 1998 canonical example)
- `test_ingestion_integrity.py` — Cat 4 (canonical collisions, required field gaps, edge type distribution)
- `test_multi_hop.py` — Cat 2c (hop-bucket grouping, A/B/C deltas, verdict logic)
- `test_cat8_external_fit.py` — Cat 8f SHACL/PROV-O/OWL-Time external standard fit
- `test_cat8_external_fit_webstd.py` — Cat 8f with schema.org/FOAF/SKOS/Dublin Core
- `test_cat8_shacl_conformance.py` — SHACL JSON-LD round-trip conformance via rdflib
- `test_cat8_counterfactual.py` — Counterfactual reasoning on graph structure

**Adapter Contract Tests:**
- `test_adapter_contract.py` — Parametric contract tests (mock, flat_baseline, full_context)
- `test_familiar_adapter.py` — FamiliarAdapter HTTP/wire tests
- `test_mempalace_adapter.py` — MemPalaceAdapter ChromaDB None-metadata guards
- `test_mempalace_daemon_adapter.py` — MemPalace daemon integration
- `test_ckg_adapter.py` — CKG adapter (conditions A/B/C, hierarchical queries, token ratio)
- `test_full_context_adapter.py` — Karpathy baseline (full context vault)
- `test_cli_adapter_forwarding.py` — CLI adapter dispatch

**LLM-as-a-Judge / Benchmark Integration:**
- `test_longmemeval_judge.py` — LongMemEval judge (CORRECT/INCORRECT/ABSTAIN/PARTIAL, multi-provider, methodology-faithfulness)
- `test_cross_validate_longmemeval.py` — Cross-validation harness (SME recall vs. judge labels, disagreement detection)
- `test_longmemeval_loader.py` — LongMemEval dataset loading

**Harness & Integration:**
- `test_harness_integration.py` — Cat 9b (The Handshake) probe success/failure banding

---

*End of analysis.*
