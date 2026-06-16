# CKG-Benchmark experiment

Run SME's structural diagnostics over Yarmoluk's `danyarm/ckg-benchmark`
dataset (HuggingFace). Goal is a contribution back, not a critique:
his benchmark proves *pre-structured graphs beat flat retrieval at scale*
(F1 0.471 vs 0.123, 269 vs 2982 tokens/query). It cannot answer whether
the **structure** earned the score or whether the same content in flat
text would have scored similarly. SME's A/B/C isolation can.

## What the benchmark contains

- 53 domains, each with a hand-authored DAG in
  `domains/{domain}/learning-graph.csv`
  (schema: `ConceptID, ConceptLabel, Dependencies (pipe-separated), TaxonomyID`)
- 47 of the 53 ship `queries/queries_{domain}.jsonl` with five query
  types — `T1_entity, T2_dependency, T3_path, T4_aggregate, T5_cross_concept`
  — and an explicit `hop_depth` field (0–5)
- Yarmoluk's published comparison: CKG vs RAG vs GraphRAG, all systems
  fed the same 47-domain × ~7,928-query corpus

CKGs are hand-built by a domain expert. There is no extraction pipeline,
no LLM ingestion, no enrichment cycles. That is a fundamentally different
cost model than vault-rag-style automated graph construction, and it
matters for how Cat 1/2/8 should be interpreted (see "What we expect to
*not* fire" below).

## Domains selected (5 of 47)

Picked deliberately for shape diversity, not random sample. Every column
below is grounded in the actual CSV.

| Domain | Nodes | Edges | Multi-parent % | Roots | Taxonomy kinds | Archetype |
|---|---|---|---|---|---|---|
| `calculus` | 380 | 538 | 39% | 2 | 17 | DEEP prereq chain (math textbook); Yarmoluk's headline domain |
| `us-geography` | 200 | 357 | **76%** | 1 | 13 | SHALLOW DENSE taxonomy — opposite of calculus |
| `moss` | 400 | 671 | 66% | **24** | 13 | LARGE FRAGMENTED FOREST — 24 disconnected roots is structurally unusual |
| `glp1-obesity` | 146 | 271 | 66% | 2 | 13 | MEDIUM medical with cross-deps (proxy for `drug-interactions`, which has no queries file) |
| `theory-of-knowledge` | 275 | 490 | **72%** | 1 | 12 | DENSE ABSTRACT — stress-test for "is this even a DAG" |

The shape spectrum is intentional:
- Deep+sparse vs shallow+dense → `calculus` vs `us-geography`
- Single-rooted vs forest → `us-geography` (1 root) vs `moss` (24)
- Concrete vs abstract → `us-geography` vs `theory-of-knowledge`
- One real-world medical → `glp1-obesity`

## What we run

Three conditions per domain × per query (SME's standard A/B/C):

- **A — flat baseline.** Serialize the CSV as plain text ("Concept X
  depends on Y, Z. Concept Y depends on …"); retrieve via vector / BM25;
  no graph traversal. Implements `SMEAdapter.get_flat_retrieval()`.
- **B — CKG structured retrieval.** Load the DAG. For a query about
  concept C, traverse to depth = max(`hop_depth` in queries) and inject
  the resulting subgraph as typed triples. Implements
  `SMEAdapter.query()`.
- **C — flat-text equivalent of B's content.** Take the *same nodes*
  B retrieves and serialize them as prose, no edges. Isolates whether
  the structure (typed edges, traversal order) earns the score, or
  whether the content alone explains the result.

The B−C delta is the single most defensible contribution this experiment
can make to Yarmoluk's work. He compared CKG to RAG cross-system; he
cannot say what fraction of his 4× F1 improvement comes from "the
relevant content was retrieved" vs "the structural form mattered."
B−C answers exactly that.

## Diagnostics applied to each CKG

Run on the loaded graph (not on retrieval output):

- **Cat 1 — Ontology coherence (monoculture).** Distribution of
  `TaxonomyID` values; entropy of edge-type usage.
- **Cat 2 — Ingestion integrity.** Phantom edges (deps to non-existent
  ConceptIDs), orphaned concepts, cycles (none expected — DAG by claim).
- **Cat 7 — The Abacus (token efficiency).** tokens-per-correct-answer
  for B vs A. Direct replication target for Yarmoluk's 11× claim.
- **Cat 8 — Schema vs shape.** What the CSV header *says* (single
  Dependencies column, single TaxonomyID column) vs what the graph
  actually exhibits (multi-parent? mixed taxonomy semantics?).

## What we expect to *not* fire (and why that's the result)

Cat 1 / Cat 2 / Cat 8 were designed to surface pathologies in
extraction-built graphs (LLM-generated edges, fragmented entities,
ghost types). Hand-authored expert DAGs are likely to come back
clean on these probes. That is a useful finding: it characterizes
the floor of what "good" looks like, against which extraction-built
graphs can be compared. The framing for the contribution is

> Here is what SME's diagnostics report on a graph built carefully by
> hand. Here is what the same diagnostics report on a graph built by
> our extraction pipeline. The gap is the actionable thing.

Not "I found problems in your CKG."

## Falsifiable predictions (worth pre-registering)

1. **B will beat A on T2_dependency / T3_path queries (hop_depth ≥ 1).**
   That is what the structure is for.
2. **B will not beat A on T1_entity (hop_depth = 0) queries.** Lookup
   is lookup. If B *does* beat A here, something is wrong (contamination,
   eval bug, or the flat baseline is weaker than it should be).
3. **B−C delta will be positive but smaller than B−A delta.** The
   structural contribution is real but partial; content matters too.
4. **Cat 1 will report low monoculture (high taxonomy diversity).**
   Hand-authored DAGs distribute edge types deliberately.
5. **Cat 7 will reproduce Yarmoluk's token-efficiency direction
   (B uses fewer tokens than A) but the magnitude may diverge from his
   11× headline** — his RAG baseline was a specific implementation;
   ours is the SME `flat_baseline.py` adapter, which is not the same
   system.

If any of these flips, that is the result worth writing up.

## Out of scope (this pass)

- Cat 3 contradiction surfacing — CKGs are static DAGs, no temporal /
  stance flips by construction
- Cat 9 harness integration — CKGs are not invoked through a hook surface
- Re-running all 47 of his domains — pick deliberately, go deep
- Calling Yarmoluk's exact RAG / GraphRAG baselines — comparison is
  to SME's `flat_baseline.py`, which is documented as such

## Outputs

`results/ckg_benchmark/<domain>/`:
- `shape.json` — graph statistics (Cat 1, 2, 8 inputs)
- `runs.jsonl` — one row per query, columns
  `query_id, type, hop_depth, condition, tokens, retrieved_ids, score`
- `summary.md` — per-domain table: B−A and B−C deltas bucketed by
  query type and hop depth, plus the Cat 7 abacus number

`results/ckg_benchmark/_overall.md` — the cross-domain story; pre-
registered predictions vs observed; framing for an external write-up.
