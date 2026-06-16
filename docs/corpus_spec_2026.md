# SME Corpus Specification 2026 — `corpus_spec_2026.md`

> Status: draft for human review
> Replaces: `docs/sme_spec_v8.md` § "Seeded Corpus: v0.1 Specification"
> alongside `docs/cross_validation_2026.md` question-count commitment.

---

## 1. Corpus Goals

The SME corpus exists to answer one question that existing benchmarks (LongMemEval, LoCoMo, EverMemBench, MemoryAgentBench) cannot answer: **what does structural organization of memory buy you, compared to flat retrieval, at each reasoning depth?**

The gap between "find a memory" (what existing benchmarks test) and "find a memory efficiently because the graph earns its keep" (what SME tests) requires three things no existing corpus provides:

**1. Controlled A/B/C condition measurement.** Every question runs against the same system in three modes: flat vector retrieval, full structured pipeline, and the same index with structure disabled. The delta between modes isolates the structural contribution. No existing benchmark runs this triple condition.

**2. Per-hop-depth breakdown from the same question set.** Multi-hop reasoning is where structured retrieval should pull ahead of flat — intermediate entities at depth 2-3 are not semantically similar to the query, only reachable via typed edges. LongMemEval tests multi-hop in aggregate; it does not report recall-by-depth curves that show *where* structure earns its keep. SME's Cat 7d (tokens-per-correct-answer by hop depth) and Cat 2c (recall by depth) require enough questions at each depth to produce stable per-depth readings. The statistical floor for per-depth claims is n ≥ 30 per depth bin.

**3. Intra-corpus defect seeding with known answers.** Categories 4 and 5 test whether the system detects or avoids damage — not just whether it retrieves correctly. This requires seeded defects (duplicate evidence, ghost entities, monoculture edge batches, structural gap communities) with known ground-truth positions. The corpus must carry both the defect and the diagnostic in the same artifact.

**What the corpus does NOT need to be:** The SME corpus does not need to be the largest, most diverse, or most representative memory benchmark. Its job is to produce *reproducible controlled comparisons* between structured and flat retrieval on questions that stress structure specifically. Scale claims come from running the same question set across multiple corpus shapes, not from having more questions than LongMemEval.

---

## 2. Question Distribution — 200 Questions

The allocation reflects three constraints: (a) Cat 1 is the baseline and needs enough to establish stable recall; (b) Cat 2c and Cat 7 need n ≥ 30 per hop-depth bin for valid statistical claims at each depth; (c) Cat 4 and Cat 5 need enough questions to cover their sub-tests independently, not just as appendages to retrieval categories.

| Category | Questions | Sub-test breakdown | Rationale |
|---|---|---|---|
| **Cat 1** — Factual Retrieval | **25** | 25 single-source | Baseline table stakes. 25 gives ±~8pp recall CI at 80% base rate. Not the ceiling — Cat 7's Condition A absorbs additional questions for token measurement. |
| **Cat 2a** — Cross-domain discovery | **15** | 15 inter-community path queries | Tests whether traversal across domain boundaries works when the connection is not semantic but structural (topic-adjacent in different communities). Enough to distinguish 0/15 from 8+/15. |
| **Cat 2b** — Canonicalization trigger | **15** | 15 alias-resolution queries | 5 alias pairs × 3 question styles (definition, relationship, co-occurrence). Three styles confirm the system surfaces aliases in retrieval, not just in a lookup table. |
| **Cat 2c** — Multi-hop reasoning by depth | **30** | 10 × 1-hop, 10 × 2-hop, 10 × 3-hop | **Statistical floor is n ≥ 30 per depth** (ideas.md: "per-hop claims at small n are directional signals"). 10 per depth bin is the minimum for an aggregate per-depth recall number that isn't pure noise. Reachability gate (spec §2c) routes unreachable questions to a separate bucket; scored questions per depth may be less than 10. |
| **Cat 3** — Contradiction detection | **15** | 8 explicit pairs + 7 implicit | 8 questions explicitly surface the contradiction pair (should flag both old and new); 7 questions test whether the system correctly returns the current state on queries where only one framing is correct (negative case for contradiction flagging). |
| **Cat 4** — Ingestigation | **20** | 4a: 5, 4b: 5, 4c: 5, 4d: 5 | One question per defect cluster, plus one diagnostic probe. Scored by defect detection rate (introspection + external separately), not by QA accuracy. The question text is a structural probe ("how many edge-type clusters does your graph have?") not a factual query. |
| **Cat 5** — Gap detection | **15** | L1: 5, L2: 5, L3: 5 | 5 questions per detection level. L1: explicit "what gaps exist?" (answerable by any system). L2: proactive health check (no explicit gap question). L3: topology analysis questions that only the external Ripser layer can answer. |
| **Cat 6** — Temporal reasoning | **20** | 6a: 12, 6b: 8 | 12 fact-state questions (what is the current state, what was the state at time T, when did X change). 8 provenance chain questions (which process created this edge, was it superseded?). |
| **Cat 7** — Token efficiency | **30** | 10 × 1-hop, 10 × 2-hop, 10 × 3-hop | Same depth bins as Cat 2c — the 30 questions are the same corpus as Cat 2c's multi-hop set, run in Condition A vs B vs C for token measurement. Per-hop bins allow the 7d efficiency-by-depth curve. |
| **Cat 8** — Ontology coherence | **0** | (graph snapshot analysis, no questions) | Scored from the graph snapshot directly. Type coverage, edge vocabulary completeness, type distribution entropy, claim pass rate from `implied_ontology.yaml`. |
| **Cat 9** — Harness integration | **15** | 9a: 8, 9d negative control: 7 | 8 positive-set questions (system contains answer, measures invocation rate). 7 negative-control questions (system has no answer, measures unnecessary invocation rate). 9b/9c/9f/9g require harness infrastructure, not additional questions. |
| **Total** | **200** | | |

**Distribution principles applied:**
- Category 8 contributes no questions because it measures the graph's structure, not the system's retrieval performance.
- Categories 2c and 7 share the same 30-question multi-hop set — Cat 2c measures recall-by-depth, Cat 7 measures tokens-per-correct-answer-by-depth on the same question set. This is intentional; it keeps the two dimensions correlated.
- Cat 4 and Cat 5 questions are intentionally non-standard: Cat 4 asks "what defects exist?" (the system should detect its own damage); Cat 5 asks "what is missing?" (the system should surface structural gaps). These are not factual QA questions.
- Cat 9 uses 15 questions because 9b/9c/9f/9g are infrastructure measurements against the same positive/negative set, not additional question burden.

---

## 3. Question Template Types

Each question is classified by its **structural form** — the retrieval pattern it exercises. The form determines which metric it maps to and what counts as a correct answer.

### L1: Single-hop entity lookup

**What it tests:** Direct retrieval of a named entity or fact from a single source.

**Question pattern:** `What [is/was/are/were] [entity] [relationship]?`

**Examples:**
- "What issue did Kai debug?"
- "What was the initial voluntary recall date for Hill's vitamin D?"
- "When did Aurora repeal its pit bull ban?"

**Ground truth:** Single `expected_sources` substring verified present in exactly one vault note. Answer is the entity or fact stated in that note.

**Scoring:** Substring match on `context_string`. Metrics: Recall@K, Answer Accuracy (judge-scored for cross-validation).

---

### L1-T: Single-hop with temporal filter

**What it tests:** Retrieval filtered by a time constraint.

**Question pattern:** `What [is/was] X [during/in/since] [temporal expression]?`

**Examples:**
- "What database were we using during session 23?"
- "What was the FDA's framing of diet-DCM in 2019?"

**Ground truth:** Answer is the state at the specified time. Multiple notes may have temporal bounds; the answer is the one whose `_created_at` or `valid_from/valid_to` covers the query time.

**Scoring:** Substring match on `context_string` + temporal consistency check.

---

### L2: Two-hop path with relationship filter

**What it tests:** Traversal across a typed edge between two entity types.

**Question pattern:** `[entity A] → [edge type] → [entity B]?`

**Examples:**
- "Who debugged the system that blocked the Driftwood migration?" (Kai → OAuth → Driftwood)
- "Which deployment is connected to the alerting SSO integration?" (alerting → OAuth → deployment)

**Ground truth:** Two `expected_sources` substrings (one per hop), annotated with the intermediate entity type. The answer is the terminal entity.

**Scoring:** Both substrings must appear in `context_string`. Metrics: Cat 2c recall at depth=2, Cat 7 tokens-per-correct-answer at 2-hop.

---

### L2-C: Two-hop canonicalization

**What it tests:** Alias resolution composed with a traversal.

**Question pattern:** `What [container orchestration tool] is deployed?` (must surface both k8s and Kubernetes)

**Ground truth:** Two `expected_sources` substrings from different surface forms of the same entity, plus the query's alias definition in the corpus alias registry.

**Scoring:** Both surface forms must appear in `context_string`. Metrics: Cat 2b canonicalization recall.

---

### L3+: Three-hop compositional chain

**What it tests:** Multi-hop traversal where intermediate entities are not semantically similar to the query.

**Question pattern:** `[entity A] → ... → [entity Z]?`

**Examples:**
- "What project was affected by the issue debugged by someone on the infrastructure team?" (team → Kai → OAuth → Driftwood)
- "Which team member's debugging connects to the system used for deployment SSO?" (team → Kai → OAuth → alerting → SSO)

**Ground truth:** All intermediate hop entities annotated, with `min_hops_in_ground_truth_graph` = N. The answer is the terminal entity.

**Scoring:** All intermediate entities (or their `expected_sources` substrings) must appear in `context_string`. Metrics: Cat 2c recall by depth (1/2/3 separately), Cat 7d efficiency by depth.

---

### X-D: Cross-domain path query

**What it tests:** Traversal between communities that are not topically adjacent in the vector space.

**Question pattern:** `[domain A concept] → [cross-domain edge] → [domain B concept]?`

**Examples:**
- "What privacy technology connects to the token-based identity system?" (auth_engineering token ↔ privacy_research token-based identity — but no edge exists yet, this is the gap)
- "What auth-related content is discussed in the privacy research domain?"

**Ground truth:** `expected_sources` spans two domain directories. If no cross-domain edge exists in the corpus, the question is a Cat 5 gap probe (the ground truth answer is "no connection found").

**Scoring:** Cross-domain substrings present in `context_string`. Metrics: Cat 2a inter-community edge density, Cat 5 gap recall.

---

### CONTRADICT: Contradiction surfacing

**What it tests:** Whether the system flags both sides of a seeded contradiction.

**Question pattern:** `Is [claim] still current?` / `What is the current state of X?`

**Examples:**
- "What auth system are we using?" (system should flag Clerk vs Auth0 contradiction)
- "Has the FDA established that grain-free diets cause DCM?" (system should flag the 2018 investigation vs the 2022 "complex, not established" framing)

**Ground truth:** `contradiction_pair_id` annotation references the seeded pair. The answer must include *both* framings, not just the most recent. The ground truth answer is the full contradiction, not one side.

**Scoring:** Both `expected_sources` (one per side) must appear. Systems that silently return only one side score 0. Metrics: Cat 3 Contradiction Detection Rate.

---

### PROVENANCE: Provenance chain query

**What it tests:** Whether the system tracks which process created an edge and whether it was superseded.

**Question pattern:** `What process created the [edge type] edge between X and Y?` / `Was this edge superseded?`

**Ground truth:** The edge has `_created_by`, `_created_at`, and `_superseded_by` properties in the corpus ground truth. The answer requires the edge's provenance properties.

**Scoring:** Substring match on provenance metadata terms in `context_string`. Metrics: Cat 6 Provenance Accuracy.

---

### PHANTOM: Phantom edge detection (structural probe)

**What it tests:** Whether the system flags edges whose evidence does not match the rule registered for their type.

**Question pattern:** `How many [edge type] edges in your graph have evidence that matches their declared rule?`

**Ground truth:** Specific injected edge clusters in the corpus (duplicate-evidence batch, misattributed-evidence cluster, RELATED-only monoculture batch). The expected answer is the count of violating edges, not a factual retrieval.

**Scoring:** Defect detection rate: fraction of seeded defect clusters correctly identified by the system (introspection) or by SME's topology layer (external). Metrics: Cat 4 Ingestion Anomaly Detection Rate.

---

### GAP-L1/L2/L3: Gap detection probe

**What it tests:** Whether the system identifies topological holes (H1 cycles) in its own knowledge.

**L1:** `What topics have no cross-references in the graph?` (explicit question)
**L2:** `Run a health check on the graph.` (proactive, no gap explicitly named)
**L3:** (external topology only) — Ripser persistent H1 features detect gaps without a question.

**Ground truth:** Specific seeded gap communities in the corpus (auth_engineering ↔ privacy_research share "token-based identity" but have no cross-domain edge). The expected answer for L1 is the specific gap community pair.

**Scoring:** Gap community pair identified / total seeded gaps. Metrics: Cat 5 Gap Recall (introspection), Gap Recall (external), H1 persistence range.

---

### NEGATIVE: Negative control

**What it tests:** Whether the system correctly skips invocation when no answer exists.

**Question pattern:** `What is the capital of Lichtenstein?` (not in corpus) — but for structural testing, more specifically: `What connection exists between [gap community A] and [gap community B]?`

**Ground truth:** No `expected_sources`. The system should either return "no connection found" or correctly not invoke the memory tool.

**Scoring:** System returns null/invokes correctly. Metrics: Cat 9d Negative Control Rate, Cat 4 false positive rate.

---

## 4. Ground Truth Construction

Ground truth is established through a **reproducible hand-authoring pipeline**, not through LLM synthesis or "expert judgment" as a post-hoc label.

### Step 0 — Corpus design before questions

Before any question is written, the corpus designer commits to:

1. **Domain selection** — which knowledge domains the corpus covers (e.g., tech/dev auth infrastructure, dog-domain research, biographical). Domains must be motivated by which structural failure modes the corpus is designed to surface.
2. **Entity type and edge type schema** — declared in `ontology.yaml` before notes are written.
3. **Seeded defect map** — which defects are injected, where, and what makes them detectable. Each defect has a `defect_id`, a `defect_type`, and a `detection_method`.
4. **Alias registry** — which surface forms are aliased to the same canonical entity.
5. **Contradiction pairs** — which pairs of notes make contradictory claims, and what makes them a pair (not just "both mention X").

### Step 1 — Note authoring with ground-truth annotations

Every vault note carries metadata fields that are the ground truth:

```yaml
---
entity_types: [person, concept, tool]
session_id: "005"
created_at: "2024-03-15T10:00:00Z"
mentions_entities: [Kai, OAuth token refresh, infrastructure team]
contradiction_pair_id: null
defect_ids: []
supersedes_note: null
---
```

The **answer** to every retrieval question is grounded in the note's content, not in an external answer key. The author writes the note, then writes the question that the note answers, then verifies the question's `expected_sources` substring appears in the note. This order (note → question → verify) prevents the common failure mode of retrofitting questions to match retrieved context.

### Step 2 — Hop depth annotation

`min_hops` is annotated against the **ground-truth graph** (the graph implied by the corpus's own entity and edge declarations), not against any system's index. The ground-truth graph is the corpus's internal claim about which entities connect to which other entities via which edge types.

When a question requires traversing N typed edges to reach the answer entity from the query entity, `min_hops = N`. This is a property of the corpus design, not of the system being tested. (The spec's reachability pre-test gates scoring: a question labeled 3-hop in the ground-truth graph may be unreachable or 1-hop in a given system's index; that system's score is reported at its actual reachable depth.)

### Step 3 — Calibration verification

After authoring, the corpus runs through `sme-eval calibrate`:

| Property | Threshold | Why |
|---|---|---|
| `betti_0` (components) | ±1 of frozen reference | No accidental fragmentation |
| `betti_1` (persistent features) | ±1 of frozen reference | No accidental bridging |
| Gap communities | shortest path > 4 hops | Gap is structural, not reachable by accident |
| Alias string similarity | max Jaccard < 0.25 | Confirms testing canonicalization, not fuzzy string match |
| Alias semantic similarity | min cosine > 0.78 | Confirms aliases are semantically close (nomic-embed-text) |
| Monoculture cluster | Betti-0 divergence > 2.0 | Detectable split between typed and generic subgraphs |
| Runaway cluster | in own connected component | Not bridged to main graph |
| Contradiction chunk similarity | < 0.6 cosine | Contradiction pair notes are in different retrieval neighborhoods |

If calibration fails, the corpus is rebuilt rather than the thresholds adjusted. The calibration is the corpus's integrity gate.

### Step 4 — Human judge calibration for Cat 1

For Cat 1 questions, a 50-question calibration subset (`calibration_50q.yaml`) is independently judged by a human before the corpus ships. Judge-human agreement is reported alongside every evaluation run so readers know the matcher quality on *this* corpus, not just on LongMemEval's validation.

---

## 5. Corpus Sources

The 200 questions are derived from three source categories:

### Source A — Hand-authored vault (primary)

The primary corpus is a hand-authored Obsidian vault with structured frontmatter. The vault covers two domains:

**Domain 1 — Tech/Dev (auth, infrastructure, privacy):** 30 notes across auth_engineering, privacy_research, infrastructure, temporal, and injected_defects subdirectories. This domain seeds:
- Multi-hop chains (Kai → OAuth → Driftwood; infrastructure team → monitoring → alerting → OAuth)
- Alias pairs (ZK proof / zero-knowledge cryptography; k8s / Kubernetes; CBT / Cognitive Behavioral Therapy)
- Contradiction pairs (Clerk vs Auth0; PostgreSQL → SQLite → PostgreSQL evolution)
- Structural gaps (auth_engineering ↔ privacy_research share "token-based identity" with no cross-domain edge)
- Injected defects (boilerplate evidence duplication, evidence misattribution, ghost entity YAML frontmatter bait, RELATED-only monoculture batch)

**Domain 2 — Dog-domain research (community journalism, veterinary science, municipal policy):** 24 notes across breed_standards, veterinary_research, nutrition_safety, behavioral_research, municipal_policy, community_journalism. This domain seeds:
- Multi-hop chains (Schenkel → dominance theory → AVSAB position; FDA → DCM investigation → Tufts → diet recommendations)
- Alias pairs (German Shepherd / Alsatian / GSD; American Pit Bull Terrier / APBT / Pit Bull; BEG diet / boutique-exotic-grain-free)
- Contradiction pairs (grain-free/DCM causal status; alpha-wolf dominance theory pre/post 1999)
- Temporal chains (Montreal BSL bylaw 2016 → 2018 repeal; Hill's recall announcement → expansion → Warning Letter)

**Source A rationale:** Hand-authored notes with intentional structural properties (seeded chains, defects, aliases, gaps) are the only way to have a corpus where the ground truth is known at the structural level. Extracted corpora (LoCoMo conversations, LongMemEval oracle sessions) have known retrieval answers but unknown graph structure — you can't test Cat 4 or Cat 5 against them because you don't know what the graph should contain.

### Source B — LongMemEval oracle sessions (cross-validation only)

The LongMemEval-cleaned dataset (xiaowu0162/longmemeval-cleaned, MIT license) provides per-question vault directories. These are used in the cross-validation harness (`scripts/cross_validate_longmemeval.py`) to run SME scoring against LongMemEval's judge methodology, not as primary corpus sources for the 200-question set.

**Source B rationale:** LongMemEval is the industry standard for factual retrieval; running the same questions through SME's scoring pipeline and LongMemEval's GPT-4o judge produces a correlation coefficient that validates or refutes SME's substring matcher. This does not contribute questions to the 200-question corpus — it's a calibration tool.

### Source C — Synthetic structural probes (Cat 4 / Cat 5 / Cat 9 only)

The injected defect notes (boilerplate-evidence clusters, ghost-entity YAML frontmatter bait, RELATED-only monoculture batch) are synthetically authored to exercise specific structural failure modes. These notes are not derived from real-world source documents; they are constructed to have exact, measurable properties (e.g., "10 edges with identical evidence string 'Supports general architecture patterns'").

**Source C rationale:** Natural corpora don't come with known defects. To test Cat 4 (does the system detect its own pipeline corruption?), you need a corpus where the corruption is known and measurable. Synthetic notes are the only way to have a deterministic ground truth for defect detection.

---

## 6. Difficulty Tiers

Questions are stratified into three tiers. The tier is a property of the question, not of the system being tested.

### Tier 1 — Easy

**Characteristics:**
- `min_hops = 1`
- Query entity name appears in the source note's filename
- Source note is the only note in its retrieval neighborhood (no nearby chunks with similar cosine distance)
- No alias resolution required
- No temporal bounds evaluation required

**What makes it harder:** Tier 1 questions are easy because the filename itself is often a substring match. The grep-floor baseline (Condition A minus the floor) on a biographical corpus will score Tier 1 questions near ceiling. Tier 1's job is to establish the baseline retrieval floor, not to stress structure.

**Example:** "What issue did Kai debug?" → answer in `kai-oauth-debugging.md`.

---

### Tier 2 — Medium

**Characteristics:**
- `min_hops = 2`
- Query entity appears in one domain; answer entity appears in a different domain or retrieval neighborhood
- May require alias resolution (L2-C form)
- May require cross-domain traversal (X-D form)

**What makes it harder:** At 2-hop, the intermediate entity (e.g., OAuth) is not semantically similar to the query ("what blocked the migration?" → the answer is Driftwood, but "OAuth" is the intermediate). A flat vector store must retrieve the intermediate entity without it being in the query; this is structurally harder than Tier 1.

**Example:** "Who debugged the system that blocked the Driftwood migration?" → requires Kai (debugger) → OAuth (system) → Driftwood (migration victim).

---

### Tier 3 — Hard

**Characteristics:**
- `min_hops = 3` or higher
- At least one intermediate entity is in a different community (Louvain) from both the query entity and the answer entity
- May require evaluating temporal supersession chains (PROVENANCE form)
- May require contradiction flagging across multiple states (CONTRADICT form)
- Source notes may have multiple plausible but incorrect answer candidates with similar cosine distance

**What makes it harder:** At 3-hop, every hop traversal multiplies the probability of traversal failure. The flat vector store cannot chain these hops — it can only return the 10 most similar chunks. If neither the intermediate entities nor the answer entity appear in the top-10 chunks from the query, the system cannot answer. The graph system traverses the path explicitly.

**Example:** "What project was affected by the issue debugged by someone on the infrastructure team?" → team (infrastructure) → Kai (person on team) → OAuth (system Kai debugged) → Driftwood (project blocked by OAuth issue).

**Edge case — structural reachability:** A Tier 3 question in the corpus ground truth may be structurally unreachable in a given system's index (intermediate edges never created). The reachability pre-test routes such questions to the `unreachable_in_graph` bucket. They are reported separately and excluded from per-depth recall averages.

---

## 7. Scoring Alignment

Each question form maps to exactly one metric from the SME framework.

| Question form | SME metric | Category |
|---|---|---|
| L1, L1-T | Recall@K, Answer Accuracy (judge-scored) | Cat 1 |
| L2, L2-C, L3+ | Recall@K by depth (1/2/3-hop) | Cat 2c |
| X-D | Inter-community edge density, Cross-domain Recall | Cat 2a |
| L2-C only | Canonicalization Recall (alias pairs surfaced) | Cat 2b |
| CONTRADICT | Contradiction Detection Rate, Contradiction Precision | Cat 3 |
| PHANTOM | Ingestion Anomaly Detection Rate (introspection + external), B-Cubed P/R/F1 for alias resolution (Cat 4a) | Cat 4 |
| GAP-L1/L2/L3 | Gap Recall (introspection L1/L2, external L3), Gap Precision, H1 persistence range | Cat 5 |
| L1-T, PROVENANCE | Temporal Accuracy, Evolution Completeness, Provenance Accuracy | Cat 6 |
| L1, L2, L3+ (same set) | Tokens-per-correct-answer (Condition A vs B vs C), Per-hop efficiency curve | Cat 7 |
| (graph analysis, no questions) | Type Coverage, Edge Vocabulary Completeness, Type Distribution Entropy, Ontology Drift Score, Claim Pass Rate | Cat 8 |
| NEGATIVE, L1 (positive set) | Invocation Rate, Call-through Success Rate, Result Use Rate, Negative Control Rate | Cat 9 |

**B-Cubed specifically for Cat 4a:** The B-Cubed P/R/F1 metric (Bagga & Baldwin 1998, Amigó et al. 2009) applies only to the alias-resolution sub-test (Cat 4a). The gold alias clusters are the `aliases` registry in `ontology.yaml`. The system's canonical-collision output is scored against it:

- **Precision:** For each entity returned by the system, what fraction of the entities grouped with it in the system's output are in the same gold alias cluster?
- **Recall:** For each gold alias cluster, what fraction of its members were grouped together in the system's output?
- **F1:** Harmonic mean.

B-Cubed is the correct metric because alias resolution is a coreference clustering problem — the system groups entities, and the question is whether those groups match the ground truth clusters. Standard retrieval precision/recall is not appropriate because it measures document-level retrieval, not entity-level grouping.

**Cat 9 MCP-Bench alignment:** Cat 9 metrics map directly to MCP-Bench's `Execution Success Rate` (9b) and add SME-specific metrics for invocation decision (9a) and result consumption (9c):

- 9a **Invocation Rate** = fraction of positive-set questions where model invoked the memory tool
- 9b **Call-through Success Rate** = fraction of invocations that returned a valid result (MCP-Bench `Execution Success Rate`)
- 9c **Result Usage Rate** = fraction of successful responses reflected in the model's reply
- 9d **Negative Control Rate** = fraction of negative questions where model correctly skipped invocation

---

## 8. Known Limitations

### Substring-on-filename matcher biases

The `expected_sources` substring matcher is documented as a known-limited signal. It fails in both directions:

**False positive:** A system returning synthesized content that contains the right answer under a different filename scores 0. A system returning the expected filename but the wrong content excerpt scores 1.

**False negative:** A system returning correct content with semantically equivalent phrasing that doesn't include the expected substring scores 0.

The grep-floor baseline (Condition A minus `grep -l <keywords>` on filenames) partially controls for this. Systems scoring at or near the grep floor on a given corpus are being measured for filename overlap, not retrieval quality. This is particularly acute on biographical/entity-per-file corpora where filenames contain their subjects — the floor is near ceiling, and `(A − floor)` is nearly 0 for all conditions.

**Mitigation:** Report `(A − floor)` alongside raw recall numbers. Report grep-floor alongside every scorecard. The spec requires the floor condition in every Cat 7 run. Cross-validation harness (scripts/cross_validate_longmemeval.py) validates substring matcher against GPT-4o judge and reports correlation/disagreement sets.

### Corpus-specific blind spots

**Domain concentration:** The 200-question corpus derives from two hand-authored vaults — tech/dev auth infrastructure and dog-domain research. Both are heavily text-based, structured around named entities with typed relationships. This biases the corpus toward systems designed for developer knowledge and research note-taking. Systems optimized for other domains (health, relationships, daily routines, creative work) will have structural properties that this corpus does not exercise.

**v0.1 is entirely dev split:** No held-out portion. Results from v0.1 are tune-againstable. v1.0 must introduce a held-out split (separate YAML file, hash-locked, downloaded separately).

**Language:** All source notes are in English. Non-English memory systems are not tested.

**Single embedding model assumption:** Calibration thresholds (cosine > 0.78 for alias pairs) are computed with nomic-embed-text. Different embedding models will produce different semantic similarity readings; the 0.78 threshold is not portable across models.

### Structural annotation assumptions

**Hop depth is annotated on the ground-truth graph, not on any system's index.** A question labeled 3-hop in the corpus may be 1-hop in a system whose index contains a direct edge between endpoints, or structurally unreachable in a system whose graph never created the intermediate edges. The reachability pre-test gates scoring per-system, but the labeled depth in the corpus is the corpus designer's claim about the path that should exist in a correctly-ingested graph — not a universal property of the question.

**Intra-corpus defects are detectable only if the ingestion pipeline creates them.** A system that silently ignores YAML frontmatter bait (ghost entity trap) will not trigger Cat 4d — it simply never creates those entities. The defect is in the corpus design, not in the system's behavior. Systems that handle the defect correctly are scored on detection rate; systems that avoid creating the defect are scored on a different metric (ingestion fidelity, measured separately).

### Token measurement dependencies

Token counts are computed from `QueryResult.context_string` using tiktoken (cl100k_base). Adapters cannot game the count because SME tokenizes the returned string itself. However, the token count reflects the *rendered context*, not the *retrieved graph structure*. A system that retrieves a compact structured representation and expands it in the context string will show higher tokens-per-correct-answer than a system that retrieves the same information in a dense format — even if the underlying retrieval is identical.

---

## Open Questions for Human Review

1. **30 questions for Cat 2c + Cat 7 combined (same set) vs. separate question sets.** The spec above uses the same 30 questions for both categories — Cat 2c measures recall-by-depth on the multi-hop set, Cat 7 measures tokens-per-correct-answer-by-depth on the same set. This keeps the two dimensions correlated. Is this the right call, or should Cat 7 use a separate (larger) question set to avoid contaminating the depth-correlation?

2. **n ≥ 30 per depth bin for Cat 2c — minimum viable or desired?** ideas.md states "the honest statistical bar for hop-bucket claims is n ≥ 30 per depth." The proposed distribution gives 10 per depth bin (30 total), which is at the noise floor for per-depth claims, not a stable measurement. Should the allocation be increased to 15 per depth bin (45 total for Cat 2c), reducing allocation elsewhere?

3. **Cat 9 question count.** 15 questions (8 positive + 7 negative control) is enough to measure 9a invocation rate and 9d negative control rate. But 9b/9c/9f require harness infrastructure, not more questions. Is 15 questions sufficient for the Cat 9 MVP, or should the allocation be higher?

4. **Source domain expansion.** v0.1 covers tech/dev and dog-domain. The spec says v1.0 must add personal knowledge, creative, and professional domains. Should the 2026 corpus explicitly commit to a third domain (e.g., health/fitness, or biographical), or defer to v1.0?

5. **B-Cubed for Cat 4a — precision/recall/F1 or normalized entropy for the full Cat 4?** B-Cubed is the right metric for alias resolution (Cat 4a). For the other Cat 4 sub-tests (evidence duplication 4a, misattribution 4b, monoculture 4c, runaway pattern 4d), the metrics are anomaly detection rate and H0/Betti-0 delta. Should Cat 4's overall score be a weighted combination, or should sub-test scores be reported separately with no aggregate?

6. **Human judge calibration set size.** The spec calls for a 50-question calibration subset for judge-human agreement. Should this be reduced (cheaper to produce) or increased (more reliable agreement estimate)? LongMemEval uses 500 questions with their judge; 50 is a much smaller calibration. What's the minimum viable calibration set for SME?