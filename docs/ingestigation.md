# Ingestigation — Cat 4 + Cat 8b expanded with primary-source-verified prior art

> *Ingestigation* (n.) — investigating the ingestion process. Portmanteau
> coined accidentally 2026-05-01 and adopted because it captures what
> Cat 4 actually is: not just *validating* whether the ingestion produced
> a graph, but *interrogating* what the ingestion did and didn't preserve
> from the source corpus.

## Status

This document renames and re-scopes Cat 4 (was "Ingestion Integrity / The
Threshold") and proposes specific integrations with existing tools so SME
isn't reinventing primitives the field already has. It is the v8.1 design
note for the ingestigation surface; spec v8 § Categories will be updated
to reference this document, not re-state its contents.

## Why rename

The existing name "Ingestion Integrity" describes a binary: did ingestion
produce a clean graph? In practice the work Cat 4 does is more like a
*post-hoc investigation* of the ingestion run — what got dropped, what
got over-merged, what got asserted without source support. The category
also has an implicit time axis (re-ingestion changes scores) and a
provenance axis (which extraction config produced these specific edges)
that the "integrity" framing flattens.

"Ingestigation" keeps the spelling proximity to *ingestion* — readers
immediately recognize the subject — while signalling the investigative
posture. It reads as a portmanteau that earns its place rather than a
label.

The existing module name (`sme/categories/ingestion_integrity.py`) does
not need to change; cross-imports stay stable. The category's
display-name + spec section header + README pointer is what gets renamed.

## Existing tools — what we are NOT going to reinvent

A focused 2026-05-01 research pass surfaced six existing tools or
standards that already do parts of what Cat 4 / Cat 8b are reaching
for. Citations are primary-source verified per the
`feedback_cite_primary_source_first.md` discipline rule.

### 1. SHACL (W3C Shapes Constraint Language) — for required-field + structural validation

SHACL is the W3C-recommended vocabulary for expressing constraints on
RDF-shaped data and validating instances against them. Modern KG
pipelines (per
[GraphGuard, SemIIM 2023](https://ceur-ws.org/Vol-3647/SemIIM2023_paper_5.pdf)
and [xpSHACL, VLDB 2025](https://arxiv.org/html/2507.08432v1)) treat
SHACL validation as the standard post-ingestion-pre-production check.
[A 2025 paper](https://arxiv.org/abs/2507.22305) explicitly evaluates
"Is SHACL Suitable for Data Quality Assessment?" — the answer being
*yes, with caveats*.

**What SME currently does that overlaps:** Cat 4b (required-field
coverage) checks "every entity has a name + entity_type." This is a
hand-rolled constraint that SHACL expresses natively as `sh:minCount 1`
on the relevant property paths.

**Proposed integration:** add a `--shacl-shapes PATH` flag to
`sme-eval cat4` that loads a shapes graph and runs `pyshacl` against
the adapter's snapshot. Report SHACL violations alongside the existing
required-field-coverage number. Lets corpus authors express richer
constraints declaratively (e.g., "every breed entity must have an
`alias_of` edge to a canonical name" → declarable in SHACL, currently
not testable in SME).

### 2. W3C PROV-O / DCAT / DQV — for provenance + quality vocabularies

PROV-O is the W3C-recommended vocabulary for provenance: what *agent*
produced what *entity* via what *activity*, with timestamps and
references. SME already reserves a `_created_by` property per spec v8;
PROV-O is the standard form of the same idea, with established
tooling and a wider compatibility surface.

**What SME currently does that overlaps:** the cross-validation
harness's `run_metadata` field captures "this run was produced by
this adapter, this corpus version, at this timestamp." That's a
home-rolled subset of PROV-O.

**Proposed integration:** ship a small `sme/eval/prov.py` that emits
PROV-O-shaped JSON for each cross-validation run. Compatible with the
W3C-PROV ecosystem; queryable via SPARQL if desired. The
`_created_by` field on edges should be paired with PROV-O `prov:Activity`
references when the adapter exposes them.

### 3. ProVe (Semantic Web Journal, accepted 2024-25) — Cat 8b's published reference implementation

[ProVe — A Pipeline for Automated Provenance Verification of Knowledge
Graphs Against Textual Sources](https://www.semantic-web-journal.net/content/prove-pipeline-automated-provenance-verification-knowledge-graphs-against-textual-sources-0)
is **the published implementation of what SME proposed as Cat 8b /
The Phantom Wall** in issue #4. Its 4-stage pipeline:

1. **Text extraction** — retrieves and processes text from documented
   provenance sources (plain text + HTML)
2. **Triple verbalisation** — fine-tuned T5 model converts triples
   to natural language
3. **Sentence selection** — BERT relevance scoring over the source
   text
4. **Claim verification** — textual entailment classifier (supports /
   refutes / insufficient)

ProVe achieves **87.5% accuracy** and **82.9% F1-macro** on the
Wikidata Textual References (WTR) dataset (416 statement-reference
pairs across 76 Wikidata properties).

**Implication for SME:** the issue #4 phantom-edge proposal needs a
follow-up comment **explicitly citing ProVe as prior art**. SME's
distinctive contribution at the Cat 8b layer is no longer "introducing
the per-edge-type evidence-rule probe" — it's the **per-edge-type
evidence-rule registration** at corpus-design time + the **
substring-and-registry-rules-only fallback** for graphs that don't
have ProVe-grade infrastructure.

ProVe needs T5 + BERT + a textual-entailment classifier; SME's per-
edge-type rules can be lexical-only for systems that don't run those
models. The two methods are complementary: SME's lighter probe
catches *structural unsupportedness* (registry mismatches, evidence
field absence); ProVe catches *semantic unsupportedness* (the source
text doesn't actually entail the claim).

The cleanest framing: Cat 8b operates at two tiers — a lightweight
SME-native registry/lexical check, and an optional ProVe-based
semantic check for systems that can afford the LLM cost.

### 4. Splink (UK Ministry of Justice, MIT) — probabilistic entity resolution at scale

[Splink](https://github.com/moj-analytical-services/splink) is a
production-grade entity-resolution library implementing the
Fellegi-Sunter probabilistic record-linkage framework. Scales to
hundreds of millions of records. Backends: SQL (DuckDB, Athena, Spark).
Active maintenance; stable since 2020.

The 2024 paper [How to Evaluate Entity Resolution Systems](https://arxiv.org/pdf/2404.05622)
empirically confirms what SME's `_bcubed.py` already cites: **B-Cubed
estimators are the most accurate of the common ER metrics** (pairwise
< cluster < B-Cubed in RMSE).

**What SME currently does that overlaps:** `sme/categories/_bcubed.py`
implements B-Cubed P/R/F1 from the Bagga & Baldwin 1998 definitions.
The existing Cat 4a `default_canonical_key` does crude case +
whitespace canonicalization; richer probabilistic linkage would need
a Splink-shaped dependency.

**Proposed integration:** add an `--entity-resolution-mode {default,
splink}` flag to `sme-eval cat4`. In `splink` mode, SME ingests the
graph entities into a Splink session, runs Splink's full pipeline, and
scores its output against the gold registry via the same B-Cubed
scorer SME already has. Lets the same evaluation run compare the
adapter's native dedup vs Splink's reference-grade dedup on the same
data, with a clean "is your adapter beating the standard ER tool"
reading.

This is a Splink-as-baseline, not Splink-as-replacement. SME's
distinctive contribution stays: scoring against a corpus-registered
gold registry (the per-edge-type-evidence-rule pattern), and the
multi-corpus comparison methodology.

### 5. OpenLineage + Marquez (LF AI & DATA) — pipeline observability standard

[OpenLineage](https://github.com/OpenLineage/OpenLineage) is the open
standard for metadata + lineage collection. Defines `run`, `job`,
`dataset` entities with consistent naming. [Marquez](https://marquezproject.ai/)
is the LF AI reference implementation. Integrations published for
Spark, Flink, Airflow, dbt, Dagster, **Great Expectations**.

**What SME currently does that overlaps:** the cross-validation
harness writes a homegrown JSON envelope per run. PR #6's 8 baseline
JSONs each have their own ad-hoc format with no shared lineage
identity (one of the open issues from the overnight critical-read
session).

**Proposed integration:** the cross-validation harness emits an
OpenLineage `RunEvent` for each cross-validation run. Adopting the
standard means SME runs are queryable from any OpenLineage-aware
tool without further work. Backwards-compatibility: the harness still
writes its existing JSON for direct reading; OpenLineage events go to
a sibling file (or to a Marquez instance if `--marquez-url` is given).

### 6. Great Expectations + Pandera — corpus-side input validation

[Great Expectations](https://greatexpectations.io/) is a Python data-
validation framework with first-class OpenLineage integration. The
ecosystem treats it as the canonical "did your input data meet your
expectations before pipeline ran?" tool. Pandera is the lighter-
weight schema-validation cousin.

**What SME currently does that overlaps:** the corpus-side validators
(`sme/corpora/good-dog-corpus/validate.py` and `verify.py`) check
frontmatter shape and source-URL liveness. That's a hand-rolled subset
of what Great Expectations does for tabular data, and the patterns
transfer cleanly to corpus YAML/markdown.

**Proposed integration:** restructure `validate.py` + `verify.py` to
emit Great-Expectations-shaped expectation suites where it makes
sense (frontmatter has these fields, every URL returns 2xx, etc.).
Existing pytest-style checks stay; the suite lets corpus authors
declare expectations in a standard format and surface them in a GE
dashboard if they want.

This is the lowest-priority integration of the six — it's a pattern-
adoption move, not a missing-capability move.

## What SME's distinctive contribution still is, after these integrations

After folding in the six tools above, what remains uniquely SME:

1. **Per-edge-type evidence-rule registration at corpus-design time.**
   The `evidence_rule` field in `ontology.yaml` per edge type is the
   distinctive claim. SHACL expresses constraints; PROV-O expresses
   provenance; ProVe verifies textual support post-hoc. None of them
   require corpora to *register* the evidence rule at design time
   per edge type. SME's good-dog-corpus is the first worked example
   of that contract.
2. **A/B/C/D condition isolation** — running the same system across
   four conditions (flat / structured / structure-disabled-on-same-index
   / no-retrieval) on the same corpus to isolate structural contribution
   from index contribution from no-retrieval baseline. None of the
   surveyed tools test this axis.
3. **Multi-corpus stress testing** — three deliberately-shaped corpora
   (clean / cross-topic / hub-dominated, plus the LongMemEval / good-dog
   axes) that surface different failure modes. Existing benchmarks ship
   one corpus.
4. **Cross-category report discipline** — per-category aggregation only,
   no aggregate correlations across SME's categories that map to
   semantically-different external primitives (e.g., Cat 3 ↔ KU
   directionality inversion). This is enforced in
   `scripts/cross_validate_longmemeval.py` and documented in
   `feedback_per_category_cross_validation.md`.
5. **The category vocabulary itself** — SME's nine-category taxonomy
   with palace-nod names is a synthesis-with-distinct-axes positioning
   (per the existing spec v8 Prior Art section), not a direct
   reinvention of any one of the six surveyed tools.

## Proposed Cat 4 sub-test additions (informed by the research)

Beyond the existing 4a/4b/4c, the research above suggests these
additions:

| Sub-test | What it does | Tool integration |
|---|---|---|
| 4a (existing) | Canonical-collision dedup | extends with optional Splink mode (above) |
| 4b (existing) | Required-field coverage | optional SHACL `--shacl-shapes` flag (above) |
| 4c (existing) | Edge-type monoculture entropy | unchanged |
| **4d (new)** | **Provenance completeness** | what fraction of edges carry full PROV-O agent/activity references vs `_created_by` only? |
| **4e (new)** | **Lineage event emission** | does the ingestion pipeline emit OpenLineage events Marquez can ingest? |
| **4f (new)** | **Input-corpus validation** | did the corpus pass its own validate.py / verify.py / Great-Expectations suite *before* ingestion? |

Plus the Cat 8b two-tier framing: lightweight SME registry/lexical
check + optional ProVe semantic check for systems that can afford the
LLM cost.

## Implementation roadmap (separate PRs)

Each row below is a tractable single-PR follow-up. Prioritized by
leverage-per-LOC.

| Priority | PR | Estimated effort |
|---|---|---|
| 1 | Cite ProVe in issue #4 + spec Cat 8b section as prior art; reframe SME contribution at that layer | 30 min — comment + spec edit |
| 2 | `--shacl-shapes` flag for `sme-eval cat4` + a small good-dog-corpus shapes file as worked example | half day |
| 3 | OpenLineage event emission from cross-validation harness | half day |
| 4 | PROV-O JSON emission alongside `_created_by` in adapter graph snapshots | 1 day |
| 5 | `--entity-resolution-mode splink` flag for cat4 | 1 day (depends on Splink dependency policy decision) |
| 6 | Cat 4d/4e/4f sub-test scoring + spec text | 1-2 days, batched after PRs 2-4 |

These are independent of the issue #9 cross-validation work.
None of them block running the after-lunch GPT-4o-judge experiment.

## Citations

- [SHACL Dashboard, Springer Nature 2025](https://link.springer.com/chapter/10.1007/978-3-032-09530-5_6)
- [xpSHACL: Explainable SHACL Validation, VLDB 2025](https://arxiv.org/html/2507.08432v1)
- [Is SHACL Suitable for Data Quality Assessment? (arXiv 2507.22305)](https://arxiv.org/abs/2507.22305)
- [GraphGuard: Enhancing Data Quality in Knowledge Graph Pipelines (SemIIM 2023)](https://ceur-ws.org/Vol-3647/SemIIM2023_paper_5.pdf)
- [ProVe (Semantic Web Journal)](https://www.semantic-web-journal.net/content/prove-pipeline-automated-provenance-verification-knowledge-graphs-against-textual-sources-0)
- [Splink (MoJ, MIT-licensed)](https://github.com/moj-analytical-services/splink)
- [How to Evaluate Entity Resolution Systems (arXiv 2404.05622)](https://arxiv.org/pdf/2404.05622) — confirms B-Cubed accuracy ranking
- [OpenLineage (LF AI)](https://github.com/OpenLineage/OpenLineage)
- [Marquez Project (LF AI)](https://marquezproject.ai/)
- [Building massive knowledge graphs using automated ETL pipelines (metaphacts)](https://blog.metaphacts.com/building-massive-knowledge-graphs-using-automated-etl-pipelines)
