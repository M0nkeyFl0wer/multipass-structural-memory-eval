# Conveyor Corpus Design — Corpus-Size Sweep Methodology

This is the methodology lock for SME's **conveyor corpus**: a single
monotonically-growing corpus authored in batches, with the full SME
test suite (Cat 4 ingestigation + Cat 5 gap detection + retrieval
conditions D1/D2/structured) re-run at each checkpoint.

The point is not "run SME once on a fixed corpus." The point is to
read SME *as a function of corpus size*, across model classes, so we
can answer:

1. **Where is the elbow?** At what corpus size does Karpathy D1
   (full-context-in-prompt) stop winning, and for which model class?
2. **Does Cat 4 have predictive value?** Does an ingestigation warning
   at checkpoint K predict retrieval failure at checkpoint K+1, or is
   it descriptive only?
3. **What does structure actually buy?** Plotted as elbow-shift: how
   much further to the right does a structured retrieval system push
   the recall curve before D1 catches up?

These are sharper claims than anything SME currently makes from a
single-corpus reading.

---

## Status (as of 2026-05-01)

This is a methodology document, not an implementation. No batches
authored yet. No checkpoints recorded yet.

What exists today:

- `sme/corpora/good-dog-corpus/` — 24 notes, single batch. The first
  point on the curve, retroactively. D1 18/18 full recall at 46 K
  tokens/q; D2-stub 0/18 full / 9/18 partial at 1 K tokens/q.
- `sme/corpora/standard_v0_1/` — directory scaffolded; the 30-note /
  50-question hand-authored corpus from `docs/sme_spec_v8.md` is not
  yet authored. **This becomes batch 02 of the conveyor.**

---

## Constitutional principle

The conveyor must stay lightweight. Each batch is a hand-authored
~10-note YAML+Markdown bundle that a human can read and verify in an
afternoon. No LLM-synthesized notes; every defect is intentional.

The test suite that runs at each checkpoint is the *existing* SME
suite — `sme-eval check`, `sme-eval cat4`, `sme-eval cat5`,
`sme-eval retrieve`, `sme-eval cat2c`. No new categories invented for
the conveyor; we just re-run what we have at multiple sizes and store
the trajectory.

---

## Design knobs

### 1. Monotonic growth

The corpus at size N+1 is a **strict superset** of size N. Batches
only append; we never remove. This gives clean attribution: if D1
collapses between checkpoint 4 and 5, it is the 5th batch that pushed
it over, not topic drift between two distinct corpora.

This also means each batch's *defects and aliases* persist forever
into all later checkpoints. A duplicate-evidence note injected in
batch 02 is still a duplicate-evidence test at checkpoint n=300.

### 2. Batches, not single notes

Each batch is a coherent thematic chunk:

- ~10 notes, hand-authored
- Its own ontology slice (entity types it introduces, edge types it
  uses) merged into the corpus-level `ontology.yaml` with a version
  bump
- Its own intentional defects (1–2 per batch, declared in
  `manifest.yaml`)
- Its own ground-truth questions (~5 per batch, slotted into the
  corpus-level `questions.yaml` and tagged with `introduced_in_batch`)
- One commit per batch, reviewable as a discrete unit

### 3. Log-spaced checkpoints

Checkpoints are taken at `n ∈ {10, 30, 100, 300, 1000}` notes —
log-spaced, because the elbow is the question. Linear spacing wastes
runs in the obvious-pass region (every frontier model wins at small
N) and the obvious-fail region (every model below frontier-large
loses at huge N). Log spacing concentrates resolution where the
elbow actually lives.

The 1 K-note checkpoint is the goal, not the prerequisite. We can
ship after n=300 and add n=1 K when authoring bandwidth allows.

### 4. Three model classes

To keep the model dimension cheap and interpretable:

- **Frontier-large** — Opus 4.7 (1 M context), GPT-4 Turbo
- **Frontier-small** — Haiku 4.5 (200 K), GPT-4o-mini
- **Mid** — Sonnet 4.6, or a smaller open-weights model if we want
  to stretch the curve down

Three points anchor a curve. The frontier-small line is where the
elbow probably shows up first — these models have nominal big
contexts but degrade on retrieval-from-haystack well before they hit
the limit. That is the *interesting* finding for memory-system folks.

---

## What runs at each checkpoint

Two test suites, run together so the readings stay aligned in time.

### Ingestion-side (Cat 4 + Cat 5 + Cat 8) — the new batch's footprint

`sme-eval check` plus `sme-eval cat8` on the post-batch graph. Record
**deltas from the previous checkpoint**, not absolutes — the
trajectory is the signal:

- Δ canonical-collision rate (did the new batch introduce alias drift?)
- Δ edge-type entropy (is the extractor template-stamping `RELATED`?)
- Δ component count and Δ largest-component ratio (are bridges
  forming or fragmenting?)
- Δ required-field coverage
- Δ ontology drift score (Cat 8d) — does the *declared* ontology
  still cover the *effective* one?

### Retrieval-side (Cat 1 / 2c / 7 + D1/D2/structured)

`sme-eval retrieve` + `sme-eval cat2c` for each `(model, adapter)`
pair on the corpus's `questions.yaml`. Plot:

- Recall@K per condition (D1 full-context, D2 LLM-compiled,
  structured retrieval)
- Tokens-per-correct-answer (the cost axis builders actually decide on)
- Latency per query (D1 grows linearly with corpus tokens; structured
  stays roughly flat — diverging lines tell the story)
- Failure-mode tagging on misses: forget / hallucinate / refuse /
  mis-rank

### The validation hypothesis

For each checkpoint K with an ingestigation warning (entropy below
healthy band, collision spike, component fragmentation), check
whether retrieval recall at checkpoint K+1 drops by more than the
batch-over-batch baseline.

- If yes — Cat 4 has *predictive value*, not just descriptive.
- If no — Cat 4 is descriptive only, still useful but a more modest
  claim.

This is the cleanest falsifiable hypothesis SME has currently put
forward. It deserves a primary place in any paper draft.

---

## Storage shape

```
sme/corpora/conveyor_v1/
  README.md                          # batch authoring guide + status
  ontology.yaml                      # grows over time, version-stamped per batch
  questions.yaml                     # all batches' GT questions, tagged
  batches/
    01_dog_baseline/                 # imported wholesale from good-dog-corpus
      notes/
      manifest.yaml                  # defects, aliases, GT
      authored: 2026-04-30
    02_auth_engineering/             # spec_v8 starter — 10 notes
      notes/
      manifest.yaml
      authored: 2026-05-XX
    03_privacy_research/
    ...
  checkpoints/
    n10/
      sme_check.json                 # Cat 4 + Cat 5 readings
      cat8.json                      # ontology coherence
      retrieve_d1_opus.json          # Karpathy D1 with Opus 4.7
      retrieve_d1_haiku.json
      retrieve_d2_opus.json          # Karpathy D2 (compiled wiki) with Opus
      retrieve_structured_*.json     # structured-retrieval adapters
      summary.md                     # human-readable card
    n30/
    n100/
    n300/
  trends/
    cat4_entropy_over_size.json      # parsed from checkpoints, plot-ready
    elbow_per_model.json             # where each model's D1 recall crosses 0.9
    cost_per_correct_over_size.json
    predictive_value_test.json       # the validation-hypothesis result
  plots/
    elbow.png
    entropy_trajectory.png
    cost_per_correct.png
```

Each checkpoint reading carries a primary key tuple
`{corpus_size, batch_count, ontology_version, model, adapter}` so
trends compose cleanly across checkpoints and so individual readings
can be replayed in isolation when authoring the next batch.

The `trends/` JSON files are derived; they regenerate from the
`checkpoints/` directory and should not be hand-edited.

### Authoring artifacts per batch

Each `batches/NN_<slug>/manifest.yaml`:

```yaml
batch_id: 02_auth_engineering
authored: 2026-05-XX
note_count: 10
ontology_extensions:
  entity_types_added: [auth_provider, session_token]
  edge_types_added: [SUPERSEDES, MITIGATES]
intentional_defects:
  - kind: duplicate_evidence
    notes: [auth-002.md, auth-007.md]
    note: "same Auth0 vs Clerk decision, two timestamps"
  - kind: alias_pair
    canonical: "JSON Web Token"
    aliases: ["JWT", "json web token"]
ground_truth_questions:
  - id: q_auth_001
    cat: 1
    expected_sources: [auth-003.md]
predicted_sme_signals:
  cat4_collision_delta: +1     # the alias above
  cat4_entropy_change: minimal # all new edges typed
  cat5_components_delta: 0     # bridges into batch 01 expected
```

The `predicted_sme_signals` block matters: declaring expected
ingestigation deltas at authoring time gives us a built-in unit test
for SME itself when the checkpoint runs. If we predicted "+1
collision" and got "+1 collision", Cat 4 is grading itself correctly.

---

## What this buys us, concretely

- **A scaling curve** that frames every other SME reading: "X
  retrieval at corpus size N for model M" instead of "X retrieval on
  good-dog-corpus."
- **A predictive-value test for Cat 4** — does early-warning
  ingestion drift actually predict downstream retrieval failure?
- **A reusable artifact** — once authored, the conveyor becomes the
  standard regression for any new memory system or adapter someone
  contributes.
- **Defensible elbow claims** — "Haiku 4.5 elbow at N≈___, Opus 4.7
  elbow at N≈___" with replicable methodology a reviewer can rerun.
- **An ingestion postmortem trail** — the trajectory tells you which
  *batch* introduced a problem, which is far more actionable than a
  "your graph has 12% canonical collisions" snapshot.

---

## Open questions for the next iteration

1. **Does good-dog-corpus get pulled in as batch 01, or do we keep it
   as a separate non-tech corpus and start the conveyor with the
   tech-flavored `standard_v0_1`?** The non-tech axis is valuable for
   showing SME generalizes, but mixing domains may confound the
   size-elbow reading. Probably: keep good-dog-corpus separate as
   the parallel non-tech replication, and start `conveyor_v1` clean
   with `standard_v0_1` as batch 01.
2. **At what point do we lock the ontology vocabulary?** If every
   batch can introduce new entity/edge types, ontology drift
   compounds and Cat 8 readings get noisy. Probably: lock the
   ontology after batch 03 and treat further extensions as opinionated
   ontology revisions with their own diff record.
3. **Authoring cadence.** Ten notes per batch is ~2 hours of focused
   hand-authoring. One batch per week is sustainable; two per week
   is the upper bound before quality suffers.
4. **Is there an automatic-cutoff signal?** If the predictive-value
   hypothesis succeeds at n=100, do we need the n=300 / n=1000
   readings, or is the curve already shaped enough? Defer until we
   have the n=100 reading.

---

## Citations

- Karpathy on full-corpus-in-context as a baseline:
  `docs/cross_validation_2026.md` § 4.
- LongMemEval per-question vault architecture (analogous batch model):
  Wu et al. 2025, ICLR. Loader at `sme/corpora/longmemeval/loader.py`.
- Cat 4 / Cat 5 / Cat 8 readings: `docs/sme_spec_v8.md` and
  `docs/ingestigation.md`.
- Industry-standards integration plan that the predictive-value
  hypothesis depends on: `docs/industry_standards_integration.md`.
