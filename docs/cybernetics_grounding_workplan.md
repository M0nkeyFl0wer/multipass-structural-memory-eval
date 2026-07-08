# SME Cybernetics/Bateson — Grounded Parallel Work Plan

> **Provenance.** Produced 2026-07-08 by a 6-agent ultracode workflow
> (`wf_06e3a315-cad`): five parallel **read-only** repo audits (the
> "prompt-of-prompts" E1–E5 from the design brief) + one synthesis pass.
> Every claim below is sourced to one of the five audits, never to the
> brief. Where the brief and an audit conflict, **the audit wins.**
>
> The brief itself ("Grounding SME, kg-common, and SKILL.md in Cybernetics
> and Bateson") proposed seven design changes (A1–A7) + a SKILL.md
> restructure (B). This plan is the *verified* reconciliation of those
> proposals against the actual code on branch `ckg-benchmark-experiment`.

Anchor repo: `/home/m0nk/Projects/multipass-structural-memory-eval`.

---

## 1. Reconciliation table

| Prop | Status | Concrete evidence (from audits) |
|---|---|---|
| **A1** Requisite-Variety Ratio | **partial — metric real, RVR is analysis-only** | The underlying metric already ships: `sme/categories/ingestion_integrity.py:85-86` `_NORM_ENTROPY_HEALTHY = 0.80` / `_NORM_ENTROPY_WARN = 0.50`, field `edge_type_entropy_normalized:135`. RVR itself computed by the A1 audit (V_graph Hill=17.06 semantic / 18.00 full; RVR spans **0.19–1.64** across 5 denominators) but the audit returned **empty `proposed_changes`** — no code target. `scripts/run_ckg_diagnostics.py:71-78` normalizes by `log2(#observed)`, not `log2(#declared)`. |
| **A2** Confidence-of-measurement field | **partial — real anchor, fields phantom** | Status discriminant is **per-CLAIM**, one place: `ClaimResult.status` at `sme/categories/ontology_coherence.py:96-104` (`# "pass"|"fail"|"untestable"|"skipped"`). Brief's guessed values (`measured|not_applicable|stub|skipped`) match **nothing**. `expected_evidence` = **0 grep hits**; no `confidence` on any status type (only unrelated term-alignment gating in `external_fit.py:270`, `counterfactual.py:85`). No per-category status object exists at all. |
| **A3** Blind-spot / negative-space report | **partial — overlaps Cat 5, hard constraint** | Cat 5 Gap Detection already IS "what's missing" (`docs/sme_spec_v8.md:567`). **Settled constraint:** `docs/industry_benchmark_gap_analysis_2026.md:103` "Do not instantiate the blind-spot with any storage-corruption claim." No dedicated code audit of an A3 anchor. |
| **A4** Learning-level (I/II) tagging + mismatch guard | **blocked — previously decided against** | `docs/ideas.md:258` heading "The delta is the product, the levels are decoration." Mismatch-guard = already-settled "trustworthy null" (`skill-delta/.../probe-result-good-dog.md:55`). L1/L2/L3 already exist as decoration (`sme_spec_v8.md:574-586`). |
| **A5** Edge-type witness lint | **partial — corpus real, harness absent** | `good-dog-corpus/ontology.yaml:68-167` declares 11 edge types; all instanced (mentions=102 … member_of=3, total 288). **0 ghosts, 0 witnesses**: `grep -rniE 'witness\|canary' sme/ tests/ scripts/` = 0. `counterfactual.py` is a re-TYPE counterfactual, not presence/absence ablation. **Blocker:** `validate.py` currently FAILS (see §5 — actually 17 errors, not the 2 the audit saw). |
| **A6** First-class View object | **partial — model decided, object absent** | Two-view model canonical in `docs/sme_spec_v8.md:244-275` (`full_snapshot` vs `semantic_snapshot`). But **no `view` param in code**: all 10 adapters are `get_graph_snapshot() -> tuple[...]` (`base.py:151`, `ladybugdb.py:829`, `mempalace.py:315`, `corpus.py:114`, …). No `class View`, no `views_are_equivalent`. Distinction wired ad-hoc per-category (git `438f5da`, `6bd1426`, `3e02fed`). |
| **A7** Governor (MAPE-K consolidation) | **phantom in SME — lives in another repo** | All three loops are REAL but in `~/Projects/hybrid-OG-vault-rag`, **not** SME (0 source hits) and **not** kg-common. Loop 1 `vault_rag/diagnostics/heartbeat.py:28-37`; Loop 2 `eval/decision_recall_canary.py:34-35`; Loop 3 `vault_rag/indexer/edge_spool.py:35` (`RESPOOL_LIMIT=3`). `git log --grep governor` = 0. No Governor anywhere. |
| **B** SKILL.md index restructure | **phantom/net-new to SME** | `find . -iname SKILL.md` in the SME repo = **empty**. The SKILL.md concept lives in the separate `skill-delta` project. No prior decision to re-litigate; also nothing to restructure here yet. |

---

## 2. Re-litigation flags (do NOT rebuild)

- **A4 — DROP.** Directly contradicts two settled decisions: levels demoted to "decoration" (`ideas.md:258`) and the mismatch-guard logic already exists as the "trustworthy null" finding in `skill-delta`. Re-promoting levels to a first-class axis re-litigates a closed call. **Recommendation: drop; if any part survives, it is only "reuse the trustworthy-null unmasking discipline," not new tagging.**
- **A1 — thresholds are VALIDATED; do not re-pick.** `_NORM_ENTROPY_HEALTHY=0.80/_WARN=0.50` validated across three graphs 2026-04-10 (`project_sme_entropy_validated.md`). RVR may be **added as a reporting lens over the existing metric**, but must not introduce different bands. Also honor the observed-vs-declared normalization mismatch (audit flags the 0.8 boundary flips).
- **A6 — the two-view MODEL is decided; only the OBJECT is open.** Any A6 design that invents view definitions other than `full_snapshot`/`semantic_snapshot` contradicts `sme_spec_v8.md:244-275`. Scope A6 strictly as "promote the decided string param into a dataclass + `views_are_equivalent` flag," replacing ad-hoc real-KG/scaffold wiring — not new semantics.
- **A3 — must not duplicate Cat 5 and must NEVER carry the storage-corruption claim.** The word "blind spot" is currently attached to the *debunked* LadybugDB-corruption story in this repo. Hard constraint from `industry_benchmark_gap_analysis_2026.md:103` + memory `feedback_no_ladybug_corruption_claim_in_public_docs.md`.
- **A5 — overlaps `counterfactual.py` + phantom-edge detector.** Frame as "unify existing checks into a presence/absence witness," not net-new machinery, per `feedback_guard_real_bug_differentiator.md` ("new finding vs elegance").
- **A2 — respect the diagnostic-vs-benchmark line.** Prior framing: confidence/error-bars are a *ranking* concern, not required for controlled mechanism deltas (`ideas.md:352-356`, `feedback_diagnostic_vs_benchmark.md`). A per-claim confidence field is acceptable *as measurement-completeness metadata*; do not let it re-open "mechanism deltas need statistical power."

---

## 3. Detailed plan per surviving subset

### A2 — Confidence-of-measurement on the status discriminant

- **Goal (2nd-order cybernetics):** make the instrument report the confidence of its own reading, so a "pass" that rests on a proxy is distinguishable from one resting on direct measurement.
- **Real-code anchor:** `sme/categories/ontology_coherence.py` — `ClaimResult` dataclass (96-104) + `Cat8Report.to_dict()` serializer (153, emit at 187-197). Console renderer `cli.py:606-613`; JSON writers `cli.py:679`, `cli.py:1050`.
- **Concrete steps:**
  1. Add `confidence: float = 1.0` and `expected_evidence: ExpectedEvidence` (new `str, Enum`: `GRAPH_STRUCTURE|VOCABULARY_MATCH|RETRIEVAL_DELTA|NONE`) to `ClaimResult` in `ontology_coherence.py`.
  2. Thread both into `to_dict()` comprehension (188-195): add `"confidence"` and `"expected_evidence": c.expected_evidence.value`.
  3. Set real values at the **12 constructors** (544,685,709,797,807,828,841,889,916,926,936,952) and **3 mutations** (557/559/561): `confidence=0.0, expected_evidence=NONE` at untestable/skipped sites; measured value at 892,939.
  4. Console marker at `cli.py:606-613` may optionally append confidence; defer to keep the change inside one file.
- **Gate:** existing Cat8 tests stay green; a new assertion that `--json` output for a known untestable claim emits `confidence == 0.0` and a known measured claim emits `expected_evidence != "none"`. Round-trip `to_dict()` schema test.
- **Dependencies:** **maintainer must answer E1 open-question** — per-CLAIM (recommended, the only real anchor) vs a NEW per-CATEGORY status abstraction (large, does not exist). Proceed on per-claim; if per-category is required, this becomes design-only.
- **Concurrency:** locks `sme/categories/ontology_coherence.py` (and only optionally `cli.py`). Disjoint from A5-corpus-fix. **Do not** let A1 also edit `cli.py` in the same wave, or serialize on `cli.py`.

### A5 — Edge-type witness lint ("difference that makes a difference")

- **Goal (Bateson):** prove each declared edge type is load-bearing — its removal must change some registered query's result set; an edge that changes nothing carries no information.
- **Real-code anchor:** new file `tests/test_edge_type_witnesses.py` (or `sme/categories/witness.py`). Reads `good-dog-corpus/ontology.yaml` + builds the in-memory graph via `CorpusAdapter.get_graph_snapshot()` (`sme/adapters/corpus.py:114`). Near-miss reference: `sme/categories/counterfactual.py` (re-type, not ablation).
- **Concrete steps:**
  1. **Prerequisite (corpus-green):** resolve `validate.py` failures (see §5). Includes the ontology decision on `grouped_under`/`subclass_of`. `validate.py` must go green first.
  2. Build a `WITNESSES` registry: one query per declared type returning a comparable result set (frozenset of ids / answer).
  3. Ablate by filtering the projected Python edge list (`[e for e in edges if e.edge_type != t]`) — **never** DELETE from a store (graph-sins).
  4. Lint asserts per type: `counts[t]>0` (else **ghost**), `t in WITNESSES` (else **unwitnessed**), `full != ablated` (else **inert**).
  5. Add `test_no_undeclared_edge_types()` guard (`present <= declared`) that pairs with `validate.py`.
- **Gate:** the lint must **flag something real** — with witnesses stubbed it must report all 11 types `unwitnessed` and (pre-fix) fail `test_no_undeclared_edge_types` on `{subclass_of, grouped_under}`. A lint that flags nothing = witness coverage too thin. Once witnesses are authored, at least the low-count types (`member_of=3`, `cites=6`) must show `healthy` (result changes) or be honestly reported `inert`.
- **Dependencies:** corpus-green (step 1) blocks the lint. Maintainer answers A5 open-questions: adopt-or-reject undeclared types; `member_of` two-direction shapes (may need 2 witnesses); whether human-grounded types (`contradicts`, `subject_of`) are in scope; witness substrate = the in-memory CorpusAdapter graph (no persisted DB in repo — confirmed).
- **Concurrency:** corpus-fix locks `ontology.yaml` + vault notes; lint locks the new test file and **reads** `corpus.py`. Disjoint from A2's files. **Collides with A6** (A6 rewrites `corpus.py:get_graph_snapshot`) — serialize A5 before A6, or have A6 keep a `view="full"` default so A5's no-arg call still works.

### A1 — Requisite-Variety Ratio (reporting lens only)

- **Goal (Ashby):** report graph variety vs an estimated domain variety, so a monoculture or an over-provisioned schema is visible as a ratio.
- **Real-code anchor:** metric already exists in `sme/categories/ingestion_integrity.py:85-86,135`; entropy/Hill computed by the A1 audit's scratch script. Add a **reporting** field, likely in `scripts/run_ckg_diagnostics.py:71-78` (or a new `rvr()` helper). No `proposed_changes` was returned — this is deliberately thin.
- **Concrete steps:**
  1. Reuse the existing `edge_type_entropy_normalized`; do NOT introduce new bands.
  2. Emit `V_graph` (Hill order-1 = `2^Shannon`) and RVR **as a range across the declared denominators**, never a single number — audit shows 0.19–1.64.
  3. Fix/annotate the normalization denominator mismatch (`log2(#observed)` in code vs `log2(#declared)`); report both so the 0.8-boundary flip is explicit.
  4. Compute on the **semantic snapshot** (mentions removed) per validated guidance, alongside full.
- **Gate:** a test asserting RVR is reported as an interval with its denominator named (not a scalar), and that the numeric matches the audit's recomputation (V_graph≈17.06 semantic / 18.00 full) within tolerance.
- **Dependencies:** **maintainer must pick which V_domain estimator is canonical** (the audit's central open question) — until then A1 stays a multi-denominator report, not a single verdict. Depends on corpus-green (undeclared types inflate any declared-schema denominator → spurious RVR>1).
- **Concurrency:** locks `scripts/run_ckg_diagnostics.py`. Disjoint from A2/A5 unless it also touches `cli.py` — if so, serialize with A2.

### A6 — First-class View object (refactor)

- **Goal (2nd-order cybernetics / Cyc microtheories):** make the observation frame (`full` vs `semantic`) an explicit declared object rather than ad-hoc per-category wiring.
- **Real-code anchor:** all 10 adapters' `get_graph_snapshot()` (`base.py:151`, `ladybugdb.py:829`, `mempalace.py:315`, `corpus.py:114`, `flat_baseline.py:166`, …) + the spec model at `sme_spec_v8.md:244-275`.
- **Concrete steps:**
  1. Add `get_graph_snapshot(view: Literal["full","semantic"] = "full")` across all 10 adapters (backward-compatible default).
  2. Introduce a `View` dataclass + `views_are_equivalent` flag as the spec prescribes.
  3. Replace the ad-hoc real-KG/scaffold routing (git `438f5da`/`6bd1426`/`3e02fed`) with the object — no new semantics.
- **Gate:** all existing adapter/category tests green with the defaulted param; a test that `view="semantic"` excludes `mentions`-class edges and `views_are_equivalent` is set where appropriate.
- **Dependencies:** must conform to the decided two-view model (re-litigation flag). Justified only if it de-risks the ad-hoc wiring.
- **Concurrency:** **wide file lock** — touches all 10 adapters incl. `corpus.py`. Serialize **after** A1 and A5 (both consume `CorpusAdapter.get_graph_snapshot()`); the `="full"` default keeps their no-arg calls valid if order slips.

### A3 — Blind-spot / negative-space report

- **Goal (Bateson / Nora Bateson warm-cold):** report what the corpus/graph structurally does NOT cover — ghost edges, flattened context, throttled lookups.
- **Real-code anchor:** design-only against existing Cat 5 Gap Detection (`sme_spec_v8.md:567`, `gap_detection.py`). No dedicated audit found an anchor beyond Cat 5.
- **Concrete steps:** (1) Scope explicitly as an *additive* framing over Cat 5, not a duplicate detector. (2) Reuse the A5 ghost/unwitnessed output as one negative-space input. (3) **Hard exclusion:** no storage-corruption content anywhere in the framing.
- **Gate:** report enumerates zero-coverage categories/edge types on good-dog and passes a lint asserting the string `corrupt`/`reconstruct-and-swap` never appears.
- **Dependencies:** A5 (ghost/unwitnessed data) is the natural feeder; resolve Cat 5 overlap with maintainer before building.
- **Concurrency:** if it reuses A5's output, serialize after A5. New file; otherwise disjoint.

---

## 4. Overarching coordination plan

### Waves

**Wave 0 — verify (DONE).** E1/A5/E4/A1/E5 already executed the read-only verification the brief asked for. Remaining prereq task: **corpus-green** — but see §5: this is NOT the 2-line fix the audit assumed. It is 17 `validate.py` failures across 3 classes, several requiring ontology/content decisions.

**Wave 1 — independent CONFIRMED real code, disjoint files (safe concurrent agents):**
- **A2** — locks `sme/categories/ontology_coherence.py` only.
- **corpus-green (A5 prereq)** — locks `good-dog-corpus/ontology.yaml` + the failing vault notes (see §5).
- These lock **disjoint** files → run concurrently. **Watch:** keep A2 out of `cli.py` this wave; reserve `cli.py` for one owner.

**Wave 2 — gated changes:**
- **A5 witness lint** — gate: corpus-green + witness-substrate/`member_of` decisions. New test file; reads `corpus.py`.
- **A1 RVR report** — gate: maintainer picks canonical V_domain estimator (else stays a multi-denominator report). Locks `scripts/run_ckg_diagnostics.py`; must reuse validated bands.
- A5 and A1 lock **disjoint** files → concurrent. **Collision risk:** if A1 wires into `cli.py` and A2 (Wave 1) also touched `cli.py`, serialize on `cli.py`.

**Wave 3 — refactors:**
- **A6 View object** — wide lock across all 10 adapters incl. `corpus.py`; **must run after A1+A5** (both consume `CorpusAdapter.get_graph_snapshot()`), or ship the `view="full"` default first. Cannot run concurrently with anything touching an adapter.
- **A3 blind-spot** — after A5 (consumes its ghost/unwitnessed output). New file; concurrent with A6 only if it does not touch adapters.

**Wave 4 — deferred / out-of-repo (see boundary below):**
- **A7 Governor** — design + cross-repo pivot.
- **B SKILL.md** — net-new, no anchor.

### Per-repo / cross-repo boundary

- **A7 is a CROSS-REPO WRITE.** All three control loops live in `~/Projects/hybrid-OG-vault-rag`, **not** in the SME anchor repo (0 source hits) and **not** in kg-common (its "quarantine" is a different fabrication-rate gate). Building the Governor there is a **repo-pivot**: it needs the ceremony (announce leaving SME → hybrid-OG-vault-rag with scope; `log_session_decision` on both sides; isolated worktree/branch; named return), **not** a silent continuation of SME work. Do not open SME code for A7 — there is nothing to open.
- Everything else (A1, A2, A3, A5, A6, B) is in-repo — no pivot.

### Checkpoint cadence (each verified subset = one commit, explicit `git add` paths)

- corpus-green: `git add` the specific ontology + vault notes touched (after `validate.py` green).
- A2: `git add sme/categories/ontology_coherence.py tests/test_ontology_coherence*.py` (after Cat8 tests green).
- A5: `git add sme/categories/witness.py tests/test_edge_type_witnesses.py` (after lint flags the known unwitnessed/undeclared set).
- A1: `git add scripts/run_ckg_diagnostics.py tests/test_rvr*.py`.
- A6: `git add sme/adapters/*.py` (after full adapter suite green).
- Run the repo gate (`make pre-push` / `pre-push` skill) as the fail-closed step in each checkpoint; push the working branch `ckg-benchmark-experiment` as offsite backup. No AI-attribution lines (repo policy). Publishing (main/PR) stays gated on an explicit user nod.
- **Multi-agent note:** a sibling claude session (pid `467539`, pts/0) shares this main checkout. Use explicit `git add` paths only; `git status --short` before every commit.

### Kill / deprioritize list

- **A4 — DROP.** Re-litigation of "levels are decoration" + the settled trustworthy-null finding. Do not implement.
- **A7 — design, not refactor.** No anchor in SME; real code is in another repo. Do not implement in SME. If built, do it in `hybrid-OG-vault-rag` under the repo-pivot ceremony, preserving the VALIDATED entropy bands and the two open-loop (`correct()` = no-op) adapters.
- **B — design, not refactor; do not implement until an anchor exists.** No `SKILL.md` in the SME repo. Confirm scope (SME docs index vs `~/.claude` skills ecosystem) before any work.
- **A3 — design-gated.** Build only after Cat 5 overlap is scoped and only with the hard no-storage-corruption exclusion enforced by a lint.

**Revision vs the brief's staging:** brief said `A2+A3 → A5+A1 → A6+A7 → SKILL.md`. Revised: **Wave 1 = A2 + corpus-green** (A3 is design-gated, not a Wave-1 real-code change); **Wave 2 = A5 + A1** (kept); **Wave 3 = A6 + A3** (A7 removed from this wave — it is cross-repo/design); **A7 and B are deferred design/pivot items, and A4 is killed outright.**

---

## 5. Wave 0 corpus-green — actual state (verified 2026-07-08, `python3 validate.py`)

The audit (looking only at the edge-type inventory for A5) reported "2 undeclared
types." Running `validate.py` in full shows **17 failures across 3 classes** — the
"tiny fix" premise does not hold. Each class needs a different kind of decision:

**Class 1 — Unregistered edge types (3 edges, 2 types) — ONTOLOGY DECISION**
- `grouped_under` ×2 — `vault/breed_standards/akc-danish-swedish-farmdog-202nd-recognition-2025.md:48,52` (breed → breed-group node). **Overlaps existing `member_of`** ("Breed group membership", itself flagged "for review in v0.2"). Decision: register as a distinct type, or remap to `member_of`?
- `subclass_of` ×1 — `vault/nutrition_safety/2011-wsava-nutritional-assessment-guidelines.md:54` (is-a/subsumption). **Genuinely new** — no subsumption edge exists. Decision: does an is-a edge earn a slot (OntoClean-style call, `ONTOLOGY.md §3`)?

**Class 2 — Missing required frontmatter (8 failures, 2 TRACKED notes) — CONTENT AUTHORING**
- `vault/community_journalism/2023-11-09-mid-america-pet-food-salmonella-recall.md` — missing `note_id`, `source_title`, `source_publisher`, `domain`.
- `vault/community_journalism/2024-11-06-aurora-pit-bull-repeal-sentinel.md` — same 4 fields.
- These are already committed; `validate.py` (modified/uncommitted) tightened the rules.

**Class 3 — Orphan entities (6 failures) — CORPUS AUTHORING (connect or drop)**
- `breed_group_fci_system` (`fci-akc-kennel-club-comparative-structure.md`)
- `concept_dog_aging_project` (`2020-watowich-dognition-cognitive-aging-uniform-trajectory.md`)
- `event_performance_dog_recall_2019` (`2018-02-22-fda-raw-pet-food-safety-study.md`)
- `org_aspca` (`2012-bollen-horowitz-safer-validity-limits.md`)
- `org_nrc` (`2014-aafco-nutrient-profiles-cnes-proposed-revisions.md`)
- `pub_aurora_v_acf` (`bsl-court-challenges.md`)

Plus 8 non-blocking WARNs (entity re-introduced across notes; "later definition wins").

**Recommendation.** corpus-green is entangled with the in-progress v0.3→v0.4 corpus
expansion (a sibling session shares this checkout) and requires ~5 ontology/content
decisions on tracked files. It is a *corpus-authoring* task, not a mechanical
unblock. Resolve Class 1 (ontology) with the maintainer as part of the A5 lane;
route Class 2/3 to the corpus-expansion track. Do not bulk-fix silently.
