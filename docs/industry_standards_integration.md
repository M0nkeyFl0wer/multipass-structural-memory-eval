# Industry-Standards Integration Plan

A project-wide audit of where SME is rolling its own infrastructure
versus where battle-tested industry standards exist. Companion to —
and broader than — [`docs/ingestigation.md`](ingestigation.md), which
covered the Cat 4 / Cat 8b ingestigation surface specifically.

## Constitutional principle

**SME stays lightweight and locally runnable.** Anyone should be able
to clone the repo, `pip install -e ".[dev]"`, and run the test suite
plus the `sme-eval` CLI on their laptop without setting up backend
servers, downloading multi-GB model weights, or pulling massive
dependency trees. Integrations that violate this principle are
flagged below for **explicit discussion** rather than auto-adoption.

The trade-off is concrete: SME competes for adoption against
LangChain, LlamaIndex, RAGAS, etc. on a *different axis* — readable
spec, deterministic results, fast iteration, no service hosting
required. Pulling in heavy frameworks would erase that axis.

## Audit summary — every layer of SME

The framework decomposes into layers; each row below states what SME
currently does, the closest industry standard, and whether the
integration fits the constitutional principle.

| Layer | SME currently | Closest industry standard | Constitutional fit |
|---|---|---|---|
| Graph algorithms | NetworkX + Ripser | NetworkX + Ripser | ✅ already battle-tested |
| Token counting | tiktoken | tiktoken | ✅ already battle-tested |
| Test runner | pytest + ruff | pytest + ruff | ✅ already battle-tested |
| Code-quality scan | codetopo (informational CI step) | (no broader standard) | ✅ already there |
| YAML / JSON parsing | pyyaml + stdlib json | pyyaml + stdlib json | ✅ already there |
| Adapter Protocol | `SMEAdapter` ABC | LangChain `BaseRetriever`, LlamaIndex retriever | ⚠️ **discuss** — adoption would flatten distinctness |
| Corpus loaders | direct YAML / file walks | HuggingFace `datasets` library | ⚠️ **discuss** — single dep but substantial |
| Adapter test fixtures | hand-rolled per adapter | shared parametric testkit (issue #8) | ✅ in scope (testkit work) |
| **Cat 4a — alias resolution** | hand-rolled `default_canonical_key` + B-Cubed scorer (Bagga & Baldwin 1998 verbatim) | Splink (UK MoJ, MIT) | ⚠️ **discuss** — DuckDB dep |
| **Cat 4b — required-field coverage** | hand-rolled per-entity field check | W3C SHACL via `pyshacl` | ✅ adopt — single light dep |
| **Cat 4c — edge-type monoculture** | normalized Shannon entropy on edge_type counts | (no direct standard) | ✅ already distinctive |
| Cat 4 provenance metadata | `_created_by` per edge (per spec v8) | W3C PROV-O | ✅ adopt — JSON shape, no deps |
| Cross-validation `run_metadata` | hand-rolled JSON envelope | OpenLineage `RunEvent` JSON | ✅ adopt — emit-only is dep-free |
| Cross-validation runner state | local JSON checkpoint | Marquez server (LF AI ref impl) | ❌ **flag** — server-backed; SME stays JSON-only |
| **Cat 8a — declared-vs-built shape** | hand-rolled README-claim parser + graph diff | (no direct standard for natural-language claims) | ✅ already distinctive |
| **Cat 8b — phantom edges** | per-edge-type `evidence_rule` registry + lexical check | ProVe (Semantic Web Journal) — full LLM pipeline | ❌ **flag** — ProVe is T5 + BERT + entailment classifier; SME stays lexical, ProVe optional 2nd tier |
| Corpus-side validators | `validate.py` + `verify.py` (~400 LOC each) | Great Expectations + Pandera | ⚠️ **discuss** — pattern-borrowing only, full GE is heavy |
| LongMemEval cross-validation judge | `sme/eval/longmemeval_judge.py` (≈300 LOC, mocked-by-default) | RAGAS / TruLens / DeepEval / Phoenix | ❌ **flag** — full RAG-eval frameworks add huge dep trees; SME's 300-LOC wrapper around the OpenAI SDK is the lightweight version |
| Substring matcher | hand-rolled per-question | (every RAG eval framework has one) | ✅ already lightweight |
| Cat 9 — harness integration | spec'd; partial 9b implementation | MCP-Bench (`Execution Success Rate`); MCPAgentBench | ✅ adopt naming, not infrastructure |

## Three tiers of integration

### Tier 1 — adopt now (lightweight, fits constitution)

Single-PR tractable, ≤1 light Python dep added per item.

1. **W3C PROV-O JSON shape for `_created_by`.** No new dependency —
   PROV-O is just a JSON-shaped vocabulary. Edge property bag adopts
   the standard names (`prov:wasGeneratedBy`, `prov:wasAttributedTo`)
   when adapter exposes the underlying activity / agent. Aligns SME
   with the W3C-PROV ecosystem; queryable via SPARQL if desired.
   Documented in [`docs/ingestigation.md`](ingestigation.md) § 2.

2. **OpenLineage `RunEvent` emit-only.** Cross-validation harness
   writes one OpenLineage-shaped JSON sidecar per run. Standard
   schema; downstream tooling can read it without us hosting Marquez.
   No `marquez-py` or similar server-side dep — just emit the JSON.

3. **SHACL via `pyshacl` (`--shacl-shapes` flag for cat4).**
   `pyshacl` is a single Python package. Cat 4b becomes optional:
   `--shacl-shapes path/to/shapes.ttl` validates the adapter snapshot
   against W3C SHACL constraints, replacing hand-rolled required-
   field-coverage with the standard. Hand-rolled coverage stays as
   the no-shapes-file fallback — backwards compatible.

4. **LongMemEval question-type prompt names.** SME's
   `sme/eval/longmemeval_judge.py` already uses LongMemEval-aligned
   prompts; verifying they match the upstream `evaluate_qa.py`
   verbatim is a small read-and-copy task with no new deps. Adopting
   the *exact* prompt strings means SME judge results are
   directly comparable to published LongMemEval numbers.

5. **MCP-Bench `Execution Success Rate` naming for Cat 9b.** Already
   noted as a 30-min spec edit in issue #12; this is naming-only
   (no new dep), and aligns Cat 9b verbatim with the published metric
   per the primary-source-verified `docs/related_work/mcp-bench-and-mcpagentbench.md`.

### Tier 2 — discuss before adopting (medium weight)

Single new dep, but substantial; need explicit user sign-off because
the dep cost is non-trivial.

6. **Splink for Cat 4a as an opt-in mode.**
   - Dep cost: pulls in `splink` (~50MB) + DuckDB (single ~50MB
     binary, single-file embedded — already on the user's machine
     for `duckdb-rag` skill work, so likely no net cost in the
     SME-on-monk environment specifically)
   - Trade-off: gives SME a "is your adapter beating the
     reference-grade ER tool?" reading. SME's existing B-Cubed
     scorer is unchanged; Splink is a parallel mode.
   - Constitutional concern: if a user installs SME from PyPI
     without DuckDB on their system, the optional `[splink]` extra
     adds noticeable install weight. Recommend `pip install
     "sme-eval[splink]"` opt-in rather than default.

7. **HuggingFace `datasets` for LongMemEval corpus loader.**
   - Dep cost: `datasets` pulls in pyarrow, fsspec, and HuggingFace
     Hub plumbing — substantial. ~300MB install footprint.
   - Trade-off: replaces the current direct-JSON-download recipe in
     `sme/corpora/longmemeval/loader.py` with `datasets.load_dataset(
     "xiaowu0162/longmemeval-cleaned")`. Cleaner UX; standard caching;
     compatible with HuggingFace ecosystem.
   - Constitutional concern: 300MB is a real install cost for a
     loader. Counter-argument: any cross-validation work probably
     already uses `datasets` elsewhere, so the cost is amortized.
     Recommend: keep direct-JSON loader; add an opt-in
     `--use-hf-datasets` mode for users already in that ecosystem.

8. **Great Expectations / Pandera patterns for `validate.py` /
   `verify.py`.**
   - Dep cost (full GE): substantial — pulls in many transitive
     deps. Pandera is lighter (~20MB).
   - Trade-off: pattern-borrowing only might be enough. Express the
     existing checks as a YAML expectation suite without taking the
     dep. If someone *wants* the full GE dashboard, they can run it
     against the suite externally.
   - Constitutional concern: the existing `validate.py` + `verify.py`
     are already lightweight and good enough for SME's scale (24
     notes in good-dog-corpus, ≤100 in any planned corpus). Defer.

### Tier 3 — flag for explicit discussion / probably do NOT adopt

These violate the lightweight constitutional principle.

9. **ProVe full-pipeline integration for Cat 8b.**
   - Dep cost: T5 model weights (~1GB) + BERT model weights (~500MB)
     + textual-entailment classifier weights. Multi-GB before any
     SME run.
   - Trade-off: ProVe is the published reference implementation of
     Cat 8b; integrating it means SME's phantom-edge probe matches
     the literature.
   - **Constitutional concern: this is exactly the kind of "framework
     bloat" SME is supposed to be the lightweight alternative to.**
   - **Recommended:** cite ProVe in the spec as the heavy semantic
     tier; SME's per-edge-type `evidence_rule` registry stays the
     lightweight first-tier. An optional `[prove]` extra could wire
     ProVe in for users who want it, but **do not make it the default
     path**. Issue #4 follow-up comment makes this two-tier framing
     explicit.

10. **LangChain `BaseRetriever` / LlamaIndex retriever interface
    adoption for `SMEAdapter` ABC.**
    - Dep cost: massive. LangChain's transitive dep tree includes
      hundreds of packages by default; even `langchain-core` is
      non-trivial.
    - Trade-off: adapting to BaseRetriever would let SME inherit ~50
      existing retriever implementations rather than asking each
      backend to write a 300-LOC bespoke adapter (which is the issue
      #8 motivation).
    - **Constitutional concern: catastrophically violates lightweight
      principle.** SME-as-LangChain-retriever-evaluator would also
      blur the project's positioning.
    - **Recommended:** keep the SME adapter ABC. **For users who
      want to evaluate a LangChain BaseRetriever via SME**, ship a
      tiny `sme/adapters/langchain_compat.py` that wraps any
      BaseRetriever as an SMEAdapter — but ship it in an `extras`
      that adds the LangChain dep only when needed, and never
      require LangChain to run SME itself. Same for LlamaIndex.

11. **Full RAG-eval frameworks (DeepEval / RAGAS / TruLens / Phoenix /
    MLflow) replacing `sme/eval/longmemeval_judge.py`.**
    - Dep cost: each is a substantial framework. RAGAS pulls in
      LangChain. DeepEval pulls in many evaluator deps. TruLens has
      observability infrastructure. Phoenix is dashboard-heavy.
    - Trade-off: any of these would replace SME's 300-LOC LongMemEval
      judge wrapper with a more general RAG-evaluation framework.
    - **Constitutional concern: replaces a deliberate 300-LOC
      lightweight wrapper with a 30-MB+ framework.** SME's design
      explicitly chose to ship a thin OpenAI-SDK wrapper, mocked by
      default for tests, no-API-key-graceful in production. That
      design point is load-bearing.
    - **Recommended:** **keep the existing wrapper as the default.**
      Document the alternative frameworks in a "if you want richer
      eval, here are the standard tools" pointer in the spec, but
      don't take any of them as a dep.

12. **Marquez backend server for run-history.**
    - Dep cost: Java service + Postgres database. Heavy.
    - Trade-off: would let multiple SME runs aggregate into a
      shared dashboard.
    - **Constitutional concern: server-backed; explicitly
      out-of-bounds for the lightweight principle.**
    - **Recommended:** **do not adopt.** OpenLineage event JSON
      sidecars (Tier-1 item 2) give the same data; users who want
      Marquez can stand it up themselves and point it at SME's
      emitted events.

## Genuinely SME-distinctive contributions (defend, don't replace)

After auditing the layers above, the parts of SME that survive as
distinctive — not partially or fully replicated by any surveyed
tool — are:

1. **Per-edge-type evidence-rule registration at corpus-design time.**
   The `evidence_rule` field in `ontology.yaml` per edge type. SHACL
   expresses constraints; PROV-O expresses provenance; ProVe verifies
   support post-hoc. None of them require corpora to *register* the
   evidence rule at design time per edge type.
2. **A/B/C/D condition isolation methodology.** Same system run flat
   / structured / structure-disabled-on-same-index / no-retrieval
   on the same corpus. None of the surveyed tools test this axis.
3. **Multi-corpus stress testing** — three deliberately-shaped
   corpora that surface different failure modes.
4. **Cat 8 ontology coherence as natural-language README-claim
   verification.** Formal-ontology validation tools exist (HermiT,
   Pellet, pyshacl); applied to LLM-extracted KGs against
   natural-language README claims is genuinely novel.
5. **Cat 9a binary invocation-decision signal isolated from
   argument-correctness.** No surveyed metric isolates this.
   `docs/related_work/mcp-bench-and-mcpagentbench.md` confirmed
   it primary-source.
6. **Per-category cross-validation discipline** — never aggregate
   across categories that map to semantically-different external
   primitives. Documented in
   [`feedback_per_category_cross_validation.md`](../../.claude/projects/-home-m0nk-Projects-multipass-structural-memory-eval/memory/feedback_per_category_cross_validation.md).
7. **The category vocabulary as synthesis** — SME's 9-category
   taxonomy with the spatial-metaphor names is a synthesis-with-
   distinct-axes positioning, not a reinvention of any one tool.

## Integration roadmap respecting the constitution

Single tracking issue is [#12](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval/issues/12);
the items below are the constitutionally-approved subset:

| Priority | Item | Tier | Effort |
|---|---|---|---|
| 1 | Cite ProVe in #4 + spec Cat 8b as **heavy second tier**; SME's per-edge-type rule registry stays the lightweight first tier | T1 | 30 min |
| 2 | `--shacl-shapes` flag for `sme-eval cat4` (`pyshacl` opt-in) | T1 | half day |
| 3 | OpenLineage `RunEvent` emission from cross-validation harness (JSON sidecar, no Marquez) | T1 | half day |
| 4 | PROV-O JSON shape for `_created_by` (no new dep) | T1 | 1 day |
| 5 | LongMemEval prompt-string verification against upstream `evaluate_qa.py` (no new dep) | T1 | 30 min |
| 6 | Cat 9b naming alignment to MCP-Bench `Execution Success Rate` | T1 | 30 min |
| 7 | Splink as opt-in `[splink]` extra (NOT default) | T2 | 1 day |
| — | LangChain BaseRetriever compat shim as opt-in `[langchain]` extra (NOT default) | T2 | half day |
| — | HuggingFace `datasets` as opt-in `--use-hf-datasets` (NOT default) | T2 | 1 day |
| — | Great Expectations pattern-borrowing (probably skip) | T3 | n/a |
| — | ProVe full pipeline (probably skip; document as heavy tier only) | T3 | n/a |
| — | RAG-eval framework replacement (skip; lightweight wrapper is the design) | T3 | n/a |
| — | Marquez server (skip; OpenLineage JSON suffices) | T3 | n/a |

## What this means for the project's positioning

After Tier 1 lands:
- SME's internal vocabulary aligns with W3C-PROV / OpenLineage / SHACL
  / MCP-Bench naming where the standards exist
- The lightweight constitutional principle is preserved — none of
  the Tier-1 items add heavy deps; SHACL and OpenLineage are JSON-
  level adoptions
- The "synthesis-with-distinct-axes" positioning sharpens — SME
  visibly speaks the same vocabulary as the rest of the field, while
  the genuinely-distinctive contributions (per-edge-type evidence
  rules, A/B/C/D, multi-corpus, Cat 8 README-claim verification, Cat
  9a binary invocation) are no longer at risk of being read as
  reinvention
- Heavy-tool integrations (ProVe / LangChain / RAGAS / Splink /
  Marquez) live in opt-in extras, never the default install path

After explicit user sign-off on Tier 2 items:
- Splink and LangChain become opt-in capabilities for users who want
  them, with the install cost they imply
- The default `pip install sme-eval` install stays small

After explicit user rejection of Tier 3:
- The corresponding tools are documented in the spec as "if you want
  the heavy version, here are the standard frameworks" pointers,
  with SME's design positioned as the deliberately-light alternative

## Open questions for discussion

1. **Splink dep policy** — opt-in extra vs hard dep vs not-at-all?
   Tier-2 recommendation is opt-in; user call.
2. **HuggingFace `datasets` dep policy** — currently we ship a direct-
   JSON loader and a download recipe. Cleaner UX with `datasets`,
   but 300MB install. Tier-2 recommendation: keep current loader,
   add opt-in mode.
3. **LangChain compat shim — ship or skip?** Adds optional surface
   for a popular ecosystem; could meaningfully lower SME's adoption
   barrier for LangChain users. Tier-2 recommendation: ship as
   opt-in extra.
4. **The `extras_require` proliferation** — we now plan
   `[topology, viz, ladybugdb, neo4j, dev]` already; adding
   `[splink, langchain, llamaindex, hf]` would compound. Worth
   discussing whether the install-path ergonomics need a meta-extra
   like `[everything]`.

## Citations

See [`docs/ingestigation.md`](ingestigation.md) § Citations and
[`docs/related_work/`](related_work/) for the primary-source-verified
references behind each tool listed above. New citations from this
doc:

- [LLM Evaluation Frameworks comparison (atlan, 2026)](https://atlan.com/know/llm-evaluation-frameworks-compared/) — RAGAS / TruLens / DeepEval / Phoenix / LangSmith head-to-head
- [Choosing the Right LLM Evaluation Framework in 2025 (Medium)](https://medium.com/@mahernaija/choosing-the-right-llm-evaluation-framework-in-2025-deepeval-ragas-giskard-langsmith-and-c7133520770c) — DeepEval as "Pytest for LLMs" framing
- [LangChain `BaseRetriever` API](https://api.python.langchain.com/en/latest/retrievers/langchain_core.retrievers.BaseRetriever.html) — abstract method `_get_relevant_documents`, the integration target if we ship a compat shim
- [Ragas framework integrations](https://deepwiki.com/explodinggradients/ragas/9.1-langchain-integration) — pattern reference for what a framework-spanning eval tool's adapter layer looks like
