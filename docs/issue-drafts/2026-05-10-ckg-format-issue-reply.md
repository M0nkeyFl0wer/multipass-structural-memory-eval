On #3 — we ran the format experiment. Added Condition B2 (hierarchical nested tree, matching your ckg-mcp output) alongside B (typed triples). Same graph, same traversal, same nodes retrieved — only the rendering format differs. Full results across your 5 domains (877 queries, committed): https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval/tree/ckg-benchmark-experiment/results/ckg_benchmark

**Token efficiency:** B2 uses 77-92% fewer tokens than B on every domain. This is consistent and large.

**Recall by query type:**
- T1_entity: B wins on dense graphs (us-geography 76% multi-parent: B 0.901 vs B2 0.858), ties elsewhere
- T2_dependency: Perfect tie on all 5 domains (1.000 vs 1.000) — same answer, different format
- T3_path at depth 3+: **B2 wins** — calculus hop 5: 0.500→0.833, moss hop 3: 0.750→1.000, theory-of-knowledge hop 4: 0.633→0.900
- T4_aggregate: B beats B2 on some queries — but this is not a format finding, see below

**On the confabulation finding:** the noise at hop 3/5 appears to be partly a format artifact, not purely a retrieval precision problem. Triples expose every cross-link explicitly — at hop 3 in a 39%+ multi-parent DAG the subgraph is enormous. B2's nested tree keeps each concept's prerequisite scope bounded. Same graph, same nodes retrieved, less noise in the output.

**On the delivery format question:** B2 uses the hierarchical nested-tree format your ckg-mcp actually returns, not typed triples. The right question is whether this format should be the benchmarking default for CKGs. If so, we should update Condition B to match ckg-mcp's output format going forward.

**On T4_aggregate specifically:** we investigated why B beats B2 on T4 queries. It's not actually a format finding — it's a retrieval strategy mismatch. T4 queries ("List all STATE concepts") need taxonomy-filtered global retrieval: return ALL entities of a taxonomy type across the entire graph, not a neighborhood around a matched target. Neither B nor B2 does this correctly. B's higher recall on T4 is an accident of its broader neighborhood (more entities fall in by proximity) while B2's tighter scope (prerequisites only) accidentally excludes most. We need a dedicated T4 handling mode that detects aggregate queries and returns the full taxonomy list. What does ckg-mcp return for aggregate queries — does it have a special mode, or is this outside its current scope?

**Cat 1/2/8 diagnostics on your domains** (all clean by construction):

| Domain | Phantom edges | Duplicates | Orphans | Observed (child_tax, parent_tax) pairs | Multi-parent % |
|--------|--------------|------------|---------|--------------------------------------|----------------|
| calculus | 0 | 0 | 0 | 65 | 39% |
| us-geography | 0 | 0 | 0 | 62 | 76% |
| moss | 0 | 0 | 0 | 75 | 66% |
| glp1-obesity | 0 | 0 | 0 | 49 | 66% |
| theory-of-knowledge | 0 | 0 | 0 | 72 | 72% |

Zero ingestion errors across all five. This is the "clean by construction" baseline — what we expect from hand-authored DAGs. Cat 2 will fire on extraction-built graphs.

The Cat 8 finding is more interesting: 1 declared edge type (DEPENDS_ON) but 49-75 observed (child_taxonomy, parent_taxonomy) pairs in each domain. The schema collapses genuinely different relations under one label — FOUND→CONT vs CONT→ANAL vs DERIV→FOUND are all DEPENDS_ON. This is a missed opportunity at no token cost: typed edges like `--[PREREQUISITE_FOR]--> ` vs `--[INSTANCE_OF]--> ` would carry richer signal without more tokens.

**On craftsmanship:** your CKGs are at the high-quality end of a spectrum — clean by construction, not extracted. Worth separating this from the format question, since the format analysis (B vs B2) applies to both crafted and extracted KGs, while the craftsmanship question (Cat 1/2/8 diagnostics) primarily tells us what the extraction-pipeline pathologies look like by contrast.

What other tests did you want to run with this?
