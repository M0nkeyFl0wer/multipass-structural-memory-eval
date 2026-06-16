# Upstream issue drafts — ontology/taxonomy standards coverage, 2026-05-30

These drafts came out of a method-coverage review prompted by three
newly-added skills in the local skills library
(`taxonomy-validation`, `library-skills`, `kg-ingestion`) and a
question about whether SME's method properly engages **SHACL**,
**Burt's structural holes**, and **ontology/taxonomy soundness**.

The review surfaced one clean framing of the gap, which the rest of
these drafts hang off:

> **OntoClean** (is the ontology coherent?) → **SHACL** (does the
> graph obey it?) → **Cat 8** (has it decayed since?).
> SME has the third, is planning the second, is missing the first.

Draft 04 (added 2026-05-31) reframes the batch around a third Cat 8
axis — **external-standard fit** — and a dependency inversion: a
published standard, once aligned to the corpus, *supplies* the spec
that OntoClean (02) and SHACL (03) currently demand by hand. 04 is the
organizing draft; 02/03 become its consumers, with their hand-authored
specs as the fallback when no standard aligns.

SME today computes declared-vs-actual drift (Cat 8), bridges +
Betti-1 (Cat 5), Louvain communities and inter-community ratio
(topology analyzer). It does **not** validate the soundness of a
declared taxonomy, does not compute brokerage, and only surveys SHACL
(scoped narrowly to Cat 4b required-fields, never built).

Each draft is independent and small. Format follows the
`2026-05-05-content-engine-feedback/` batch: workflow note → the gap
→ a proposal with a sketch of the shape.

| # | Draft | Effort | Status |
|---|---|---|---|
| 01 | Burt brokerage metric (+ Cat 5 rename) | ~half day | **IMPLEMENTED** on this branch (`analyze --brokerage`) |
| 02 | OntoClean as a Cat 8 deepening | ~1 day | spec'd here |
| 03 | SHACL `sh:ValidationReport` output, no pyshacl dep | ~half day | spec'd here |
| 04 | External-standard fit → auto-generated audit → counterfactual (organizing draft; Phase 1 = PROV-O/OWL-Time slice) | ~half day (Phase 1) | spec'd here |

**01 landed** (`TopologyAnalyzer.brokerage` + `analyze --brokerage` +
`tests/test_brokerage.py`): the Cat 5 rename and the
constraint/effective-size brokerage metric are both in the working
tree. 02 and 03 remain as drafts for review.

Recommended order: **01 first** — lowest risk, highest value, and it
adds a new diagnostic axis (concentrated vs distributed brokerage)
before touching any ontology theory. The Cat 5 rename inside 01 is
already done on this branch (`structural holes` → `topological holes
(H1 cycles)` across `gap_detection.py` + spec) because it's a
communication-bug fix that should land regardless.
