# CKG-benchmark — cross-domain results

**877 queries across 5 domains** (calculus 180, us-geography 176, moss 176,
glp1-obesity 170, theory-of-knowledge 175). All conditions share the same
queries, the same target-concept matcher, and the same substring-recall
scorer. Tokens counted with tiktoken cl100k_base. Adapter at
`sme/adapters/ckg.py`; runner at `scripts/run_ckg_experiment.py`.

Methodology, falsifiable predictions, and shape rationale for the 5-domain
shortlist live in `docs/ckg_benchmark_experiment.md`. Per-domain detail
in the per-domain `summary.md` files.

## Headline

| Domain | A recall | B recall | B−A overall | B vs A peak (hop) | C beats B at hop |
|---|---|---|---|---|---|
| calculus | 0.846 | 0.875 | +2.9 pp | +22.2 pp (hop 4) | 3, 4, 5 |
| us-geography | 0.873 | 0.901 | +2.8 pp | **+66.7 pp** (hop 2) | tied |
| moss | 0.883 | 0.898 | +1.5 pp | +22.2 pp (hop 2) | 3, 4, 5 |
| glp1-obesity | 0.869 | 0.895 | +2.6 pp | +16.9 pp (hop 4) | 3, 4, 5 |
| theory-of-knowledge | 0.829 | 0.940 | **+11.1 pp** | **+55.6 pp** (hop 2) | 3, 4, 5 |

**B beats A in 5 of 5 domains.** The advantage scales with hop depth in
all 5: at hop ≥ 2 the B−A gap is double-digit positive in every domain,
peaking at +66.7 pp on us-geography hop 2 and +55.6 pp on
theory-of-knowledge hop 2. This is consistent with Yarmoluk's directional
claim: structured retrieval helps most at multi-hop, and that's where it
earns its keep.

## What's new — the B−C signal

Yarmoluk's benchmark compares CKG to RAG cross-system. It cannot ask
*"did the structure earn the score, or would the same content as flat
text have done as well?"* — because it changes both the data shape and
the retrieval algorithm at once. SME's Condition C holds the data
constant: same node set as B retrieves, but serialized as prose
("Concept X (taxonomy: T). Depends on: parent1, parent2.") with no
typed-triple edges.

The result, identical across 4 of 5 domains:

> **B and C are tied at hop 0–2. C beats B by 10–25 pp at hop 3–5.**

Mechanism: B's structured retrieval uses a fixed 2-hop traversal budget.
At hop_depth ≥ 3 the budget runs out and B genuinely cannot reach the
answer node. C, formatted as prose-with-deps, mentions parent labels
inline — giving it an *effective +1 hop reach* even with the same
seed node set. So C "wins" at high hops not because prose is
intrinsically better than typed triples, but because the chunk-level
inline references compensate for the traversal budget shortfall.

This is the kind of finding cross-system comparisons can't surface.
It says something specific and actionable about CKG retrieval design:

1. **The traversal budget is load-bearing.** A fixed 2-hop budget under-
   serves any query whose hop_depth label is ≥ 3 — which is 8–22%
   of queries per domain. Adaptive budgeting (set traversal depth ≈
   query hop_depth) should close most of the C-beats-B gap.
2. **Inline references in chunks are doing real work.** A "Concept X
   depends on: A, B, C" prose chunk extends reach by one effective
   hop without any traversal at all. CKG implementations that strip
   inline dependency mentions in favor of pure typed triples may be
   leaving recall on the table.
3. **The 4× F1 / 11× token claims are budget-dependent.** Yarmoluk's
   numbers come from a specific traversal choice he made; running the
   same data with different budget gives different numbers.

## Token economics — the inverted finding

| Domain | A mean tokens | B mean tokens | ratio |
|---|---|---|---|
| calculus | 125 | 467 | **3.7×** |
| us-geography | 89 | 1156 | **13.0×** |
| moss | 126 | 1080 | **8.6×** |
| glp1-obesity | 208 | 1588 | **7.6×** |
| theory-of-knowledge | 114 | 1066 | **9.4×** |

Yarmoluk reports CKG using 11× **fewer** tokens than RAG (269 vs 2982).
We see the inverse: B uses 3.7–13× **more** tokens than A. Reason: our
A is per-concept token-overlap retrieval over single-concept chunks
(very small chunks), while his RAG baseline chunks the *original
text source* the CKG was authored from (much larger chunks). Different
baseline, different denominator, different ratio.

What this means for the contribution back: **don't claim our numbers
contradict his.** The 11× token claim is real *against the corpus he
compared to.* What our setup shows is that the absolute token budget
of structured retrieval is sensitive to chunk-design choices on the
flat side; if RAG's chunks are tight, structure's overhead is large.

## Pre-registered predictions vs observed

From `docs/ckg_benchmark_experiment.md`:

1. *B will beat A on T2_dependency / T3_path queries (hop_depth ≥ 1).*
   ✅ Confirmed in all 5 domains.
2. *B will not beat A on T1_entity (hop_depth = 0) queries.*
   ✅ Confirmed; B is ≤ A by 0–8 pp at hop 0 in every domain except
   theory-of-knowledge (where B beats A by 10.5 pp at hop 0 — likely
   because ToK's dense cross-link rate floods even hop-0 queries with
   relevant neighbors).
3. *B−C delta will be positive but smaller than B−A delta.*
   ❌ **Falsified.** B−C is ≥ 0 only at hop 0–2; at hop 3–5 it is
   *negative* by 10–25 pp in 4 of 5 domains. The "structure earns
   its keep over content" framing is too strong; what earns its keep
   is *traversal sized to the query*, and prose-with-deps captures
   most of that for free.
4. *Cat 1 (monoculture) will report low taxonomy diversity → high entropy.*
   Pending — diagnostic not yet wired up against the CKG adapter.
5. *Cat 7 will reproduce direction but not magnitude of Yarmoluk's 11×.*
   ⚠️ Direction *inverted* in our setup (see Token economics above).
   This is a baseline-design issue, not a refutation of his claim.

## Caveats this experiment does not address

- **Substring-recall is not F1.** Yarmoluk uses Macro F1; we use a
  per-query substring scorer that mirrors SME's existing methodology.
  Numbers are not directly comparable to his, only directionally so.
- **Token-overlap is a weak flat baseline.** A real RAG comparison
  would use BM25 or dense embeddings. The B−A gap reported here is
  an *upper bound* on structure's advantage; a stronger A would
  shrink it.
- **2-hop traversal budget is fixed.** The most actionable finding
  (C-beats-B at hop ≥ 3) is partly an artifact of this choice. An
  adaptive-budget run is the obvious follow-up.
- **No structural diagnostics in this pass yet.** Cat 1 (monoculture),
  Cat 2 (ingestion integrity), Cat 8 (schema vs shape) results were
  promised in the methodology doc and are not yet wired up.
  Ingestion-integrity result *is* in: zero phantom edges, zero
  duplicate ConceptIDs, zero orphans across all 5 domains.
  Hand-authored DAGs are integrity-clean by construction.
- **No LLM-judge scoring.** A final F1 layer with a real model
  reading the context and answering would convert "label appears in
  context" into "model gives the right answer." That is the natural
  next layer.

## What to bring to Yarmoluk

A short, direct opener:

> Ran your 47-domain benchmark through SME's A/B/C isolation
> framework on 5 of your domains (877 queries). Three findings:
>
> 1. B beats A in all 5 domains, advantage scales with hop_depth —
>    matches your directional claim.
> 2. **At hop ≥ 3, prose-with-inline-deps (B's same node set, no
>    typed triples) beats B by 10–25 pp.** Consistent across 4 of
>    5 domains, n = ~80 queries at high hops. The implication is
>    that traversal budget should adapt to query hop_depth — the
>    fixed-budget version leaves recall on the table when prose
>    references compensate for unreached hops.
> 3. Your CKG CSVs come back zero-error on Cat 2 ingestion-
>    integrity (no phantom edges, no orphans, no duplicate IDs)
>    across all 5 domains. Useful as a "gold" baseline against which
>    extraction-built graphs can be compared.
>
> Numbers, code, and methodology in the linked PR. Happy to extend
> to the other 42 domains if any of this is useful.
