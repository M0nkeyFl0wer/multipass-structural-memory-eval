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
## LLM-judge layer

LongMemEval-style two-stage methodology added 2026-05-05: gpt-4o-mini
reads context and answers each query in 1–2 sentences; gpt-4o-2024-08-06
grades the reader's answer against ground_truth as
CORRECT / PARTIAL / INCORRECT. 877 × 3 = 2631 reader+judge calls,
0 ERROR rows after one retry pass with longer backoff. Accuracy =
(CORRECT + 0.5 × PARTIAL) / n.

| Domain | A | B | C | winner |
|---|---|---|---|---|
| calculus | 0.539 | 0.558 | **0.592** | C |
| us-geography | 0.619 | **0.622** | 0.594 | B |
| moss | 0.585 | 0.548 | **0.599** | C |
| glp1-obesity | 0.571 | 0.553 | **0.588** | C |
| theory-of-knowledge | 0.569 | 0.654 | **0.686** | C |

**Substring-recall headline does not survive.** Under LLM judge:

- **C beats B in 4 of 5 domains overall.** Reader models extract
  answers better from prose-with-deps than from typed-triple notation
  even when the retrieval is identical.
- **B beats A meaningfully only in theory-of-knowledge** (+8.5 pp).
  Elsewhere B is within ±2 pp of A overall, and on glp1-obesity B
  *hurts* at hop 3 (−33 pp) and hop 5 (−30 pp) — pulling in the wrong
  cluster of dependencies and giving the reader something confident
  but wrong to extract.
- **theory-of-knowledge does show the predicted scaling**: B−A is
  +8.9 pp at hop 0, +41.7 pp at hop 2, +37.5 pp at hop 3. Dense
  cross-linked abstract domains are where structured retrieval most
  reliably earns its tokens.

### Predictions revisited under LLM judge

Re-checking the five pre-registered predictions with reader+judge in
hand:

1. *B beats A on hop_depth ≥ 1.*
   ⚠️ **Half-confirmed.** True for theory-of-knowledge consistently;
   true at hop=2 in moss / us-geography; mostly false elsewhere.
   The original substring-recall confirmation was the methodology
   over-crediting structure.
2. *B will not beat A on hop_depth = 0.*
   ✅ **Confirmed** (B−A at hop 0: 0.0 / −4.8 / −7.1 / +0.9 / +8.9).
3. *B−C will be positive but smaller than B−A.*
   ❌ **Falsified more strongly.** B−C is negative overall in 4 of
   5 domains.
4. *Cat 1 entropy will be high.*
   ✅ **Confirmed** (0.91–0.98 across all 5 domains).
5. *Cat 7 will reproduce Yarmoluk's 11× direction.*
   ❌ **Inverted in our setup** (B uses 3.7–13× more tokens than A
   due to baseline-design choice; not a refutation of his published
   claim).

Score: **2 confirmed, 1 half-confirmed, 2 falsified.** Falsifying our
own hypotheses is the framework working — substring-recall would have
let prediction #1 and #3 ship with the wrong sign.

## Structural diagnostics (Cat 1, 2, 7, 8)

Independent of A/B/C, ran SME's structural probes against each loaded
CKG (script at `scripts/run_ckg_diagnostics.py`, summary at
`results/ckg_benchmark/_diagnostics.md`).

**Cat 1 — monoculture.** Tax entropy 0.91–0.98 (norm), 12–17
taxonomies per domain. Hand-authored DAGs are taxonomically diverse
by intent. **Edge-type entropy is 0 by construction** — the schema
declares one edge type. Confirms prediction #4.

**Cat 2 — ingestion integrity.** All 5 domains: 0 phantom edges,
0 duplicate IDs, 0 orphan concepts, 0 ingest errors. First datapoint
for the *expert DAGs are integrity-clean* baseline.

**Cat 7 — Abacus (tokens-per-correct-answer, lower = better).**

| Domain | A | B | C |
|---|---|---|---|
| calculus | 160 | 584 | 410 |
| us-geography | 114 | 1433 | 993 |
| moss | 152 | 1302 | 812 |
| glp1-obesity | 272 | 2030 | 1394 |
| theory-of-knowledge | 148 | 1236 | 743 |

A is the cheapest in all 5 domains; C beats B in all 5; B is the most
expensive across the board. Combined with the LLM-judge accuracy
table this means **C is at-or-near the best accuracy AND cheaper than
B**. The token bill on B is real.

**Cat 8 — schema vs shape.** The CSV header declares one edge type
(Dependencies → DEPENDS_ON). Counting distinct (child_taxonomy,
parent_taxonomy) pairs in the actual graph reveals the schema's
under-specification:

| Domain | Declared edges | Observed (tax, tax) pairs | Multi-parent share | Max parents |
|---|---|---|---|---|
| calculus | 1 | **65** | 39% | 3 |
| us-geography | 1 | **62** | 76% | 3 |
| moss | 1 | **75** | 66% | 5 |
| glp1-obesity | 1 | **49** | 66% | 4 |
| theory-of-knowledge | 1 | **72** | 72% | 3 |

`moss` collapses 75 distinct relation kinds under one label. A typed-edge
upgrade (`<X> --[INSTANCE_OF]--> <Y>` vs `<X> --[BUILT_FROM]--> <Y>`)
would carry richer signal at the same token cost. This is the kind of
schema observation extraction-built graphs would benefit from too.

## What to bring to Yarmoluk

A short, direct opener (revised after LLM-judge layer landed):

> Ran 5 of your 47 domains through SME's A/B/C isolation framework
> (877 queries total). Two scoring layers: substring recall and a
> LongMemEval-style reader+judge (gpt-4o-mini reader,
> gpt-4o-2024-08-06 judge). Four findings:
>
> 1. **theory-of-knowledge is the cleanest win for CKG.** B beats
>    A by +37.5 pp at hop 3 and +41.7 pp at hop 2 under LLM judge,
>    with the predicted scale-with-depth pattern. Dense cross-linked
>    abstract domains are where structured retrieval most reliably
>    earns its tokens.
>
> 2. **The "structure beats flat everywhere" result does not survive
>    a real LLM reader.** Substring recall said B beat A in all 5
>    domains; LLM judge says B and A are within ±2 pp in 3 of 5
>    domains, and B *hurts* on glp1-obesity at hop 3 and 5 (−33 / −30
>    pp). Methodology choice changes the headline — substring recall
>    was over-crediting "label is in context."
>
> 3. **Prose-with-inline-deps (Condition C, same node set as B but
>    no typed triples) is the strongest condition overall in 4 of 5
>    domains.** Reader models extract answers better from prose than
>    from typed-triple notation. Suggests typed-triple format may be
>    over-formalized for LLM consumption — worth A/B-ing in your own
>    setup.
>
> 4. **Your CSVs come back integrity-clean.** 0 phantom edges, 0
>    orphans, 0 duplicate IDs across all 5 domains. The schema-vs-
>    shape probe also found that the single Dependencies column
>    collapses 49–75 distinct (child_taxonomy, parent_taxonomy)
>    pairs — a typed-edge vocabulary upgrade could carry richer
>    signal at the same token cost.
>
> Code, methodology, per-domain detail at <pr-link>. Happy to
> extend to the other 42 domains.

Leading with the substring-recall headline would have been an
over-claim; the LLM-judge result is more conservative, more defensible,
and more useful as a contribution back. The framework's job was to
make that distinction visible. It did.
