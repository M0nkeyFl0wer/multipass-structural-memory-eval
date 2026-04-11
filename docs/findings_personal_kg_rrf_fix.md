# Personal KG hybrid retrieval fix — weighted normalized RRF

## Summary

On 2026-04-10, ran a full three-condition retrieval benchmark against
a personal knowledge graph system using 12 climate-research questions.
Found that `mode=hybrid` scored 0/12 full recall while `mode=semantic`
scored 7/12. Identified the root cause, tested two proposed fixes (one
failed, one succeeded), and produced a clean patch that rescues hybrid
mode from 0/12 to 7/12 — matching semantic mode and leaving graph
traversal as a neutral tax rather than an active harm.

This writeup is shared as a worked example of what the diagnostic
framework can surface on a real system. The actual patch against the
author's personal KG codebase is not distributed; the essential code
change is inlined below under "The core of the fix."

## What we measured

All benchmarks use the same 12 hand-authored questions grounded in a
cross-topic research directory, indexed in both a fresh MemPalace
palace and in the personal KG's live LadybugDB index. Every research
file is present in both systems. n_results=5 for all conditions.

```
condition                                full   partial   tokens   t/correct
─────────────────────────────────────    ────   ───────   ──────   ─────────
flat ChromaDB                            8/12   12/12       796      1,194
MemPalace routed                         3/12    6/12       801      3,203
MemPalace no-route                       8/12   12/12       829      1,244
personal KG hybrid (original)            0/12    0/12       619          ∞
personal KG hybrid (AFS α=0 β=1 γ=0)     0/12    0/12       619          ∞
personal KG graph-only                   0/12    0/12       745          ∞
personal KG semantic                     7/12    9/12       568        973
personal KG hybrid (max+semantic only)   7/12    9/12       566        971
personal KG hybrid (RRF equal weights)   2/12    3/12       612      3,670
personal KG hybrid (RRF 0.3/0.5/0.2)     6/12    8/12       570      1,139
personal KG hybrid (RRF 0.2/0.6/0.2)     7/12    9/12       566        971
personal KG hybrid (RRF 0.15/0.7/0.15)   7/12    9/12       568        974
```

## Experiment 1: AFS weight tuning (failed)

**Hypothesis:** The AFS scorer's trust term (γ · trust = 0.123 for
session logs, 0.096 for research) was favoring session logs. Setting
γ=0 would remove the trust bonus.

**Test:** Edited the personal KG config to `AFS_ALPHA=0, AFS_BETA=1,
AFS_GAMMA=0` — pure similarity, no freshness or trust contribution.
Restarted API. Reran benchmark.

**Result:** Byte-identical to default weights. 0/12, same tokens,
same question ordering.

**Conclusion:** AFS rescoring runs AFTER the merge in `hybrid_search`.
By the time AFS gets called, session-hub notes already dominate the
top-K. AFS can only reorder within the already-ranked list — it cannot
pull in new results that were pushed below the cutoff in the merge
step. **AFS weight tuning cannot rescue hybrid on this corpus.**

## Experiment 2: Disable FTS and graph entirely (diagnostic)

**Hypothesis:** The bug is in the three-way merge of FTS + semantic +
graph results. Max-merging their scores lets whichever signal has the
largest numeric range dominate. If semantic alone is competitive,
disabling FTS and graph should restore semantic-mode performance.

**Test:** Stubbed `fts_results = []` and `graph_results = []` in
`hybrid_search`, leaving only semantic.

**Result:** 7/12 recall, 566 mean tokens, 971 tokens/correct — exactly
matching the personal KG's own `mode=semantic` within rounding.
Confirmed the max-merge of FTS/graph/semantic is where accuracy is
lost.

## Experiment 3: Reciprocal Rank Fusion with normalized scores (succeeded)

**Hypothesis:** Replace max-merge with Reciprocal Rank Fusion
(Cormack et al. 2009), which ranks by position within each list rather
than by absolute score. Weights let us trust semantic more than
graph_search (which biases toward hub nodes on this corpus).

**Iterations:**

1. **Standard RRF equal weights** (1/3 each) — 2/12. Better than max-
   merge but session logs still appeared in all three lists so RRF
   still favored them.
2. **Weighted RRF 0.05/0.9/0.05** — 5/12. Pre-normalization issue:
   raw RRF scores are ~0.016, which broke downstream AFS rescoring
   (trust term dominated similarity term, re-inverting the ranking).
3. **Normalized weighted RRF 0.3/0.5/0.2** — 6/12. Normalization fixed
   the AFS coupling. One question short of semantic.
4. **Normalized weighted RRF 0.2/0.6/0.2** — **7/12. Matches semantic
   exactly**, within rounding on every metric.
5. **Normalized weighted RRF 0.15/0.7/0.15** — 7/12. Plateau.

## Per-question analysis

```
Q     hops      flat       sem   rrf-hyb
Q01      1      1.00      1.00      1.00   ✓ all three full
Q02      1      1.00      1.00      1.00   ✓
Q03      1      1.00      1.00      1.00   ✓
Q04      1      1.00      1.00      1.00   ✓
Q05      1      1.00      1.00      1.00   ✓
Q06      1      1.00      1.00      1.00   ✓
Q07      1      1.00      1.00      1.00   ✓
Q08      2      0.50      0.50      0.50   partial on all three
Q09      2      0.50      0.50      0.50   partial on all three
Q10      2      1.00      0.00      0.00   ← flat wins this one
Q11      3      0.33      0.00      0.00   ← flat wins
Q12      3      0.67      0.00      0.00   ← flat wins
```

**The personal KG (both semantic and RRF-hybrid) matches flat exactly
on Q01–Q09.** The 1-point full-recall gap (7 vs 8) is Q10, and the
partial-hit gap is Q11/Q12. These are all multi-hop synthesis queries
where flat's wider ChromaDB chunking happens to find one more expected
file.

**Why flat wins Q10/Q11/Q12:** Not because of structure — flat has no
structure. It's because ChromaDB's default chunking and embedding on
this specific content happens to surface chunks the personal KG's own
chunking pipeline doesn't. This is an embedding/chunking difference
at the baseline layer, unfixable by merge strategy.

## The fix

The max-merge in the personal KG's `retrieval/hybrid.py` is replaced
with a weighted normalized RRF (code inlined in "The core of the fix"
section below):

1. Build RRF scores per note: `sum(weight × 1/(k + rank + 1))`
   across the three result lists, where `k=60` is the standard RRF
   constant.
2. Normalize the resulting scores to [0, 1] by dividing by the max.
   Without this, AFS rescoring downstream would see tiny RRF scores
   (~0.016) and the trust term (γ·trust ≈ 0.1) would dominate the
   similarity term (β·sim ≈ 0.01), re-inverting the ranking.
3. Weights default to `fts=0.15, sem=0.70, graph=0.15` — similar shape
   to the AFS_ALPHA/BETA/GAMMA weights, favoring semantic.

**Impact on the climate-research benchmark:**

- Hybrid mode full recall: 0/12 → 7/12
- Hybrid mode tokens-per-correct: ∞ → 974
- Matches the personal KG's own semantic mode on every metric
- Cat 2c verdict: "structure harmful at multi-hop" → "structure is a
  neutral tax, adds nothing beyond metadata"

**What the fix does NOT do:**

- Does not beat semantic mode. On this corpus, graph_search's
  contribution is neutralized, not made productive. To beat semantic,
  graph_search would need to STOP returning session-hub notes for
  content queries — that's a graph_search fix, not a merge fix.
- Does not close the 1-question gap vs flat ChromaDB (Q10). That's a
  baseline chunking/embedding difference, unrelated to structural
  retrieval.
- Does not tune for "what did I do last week" style queries, which is
  arguably what the original hybrid mode was optimized for. Session
  logs as top hits may actually be correct for those. Consider
  measuring before adopting this fix as the permanent default.

## Known limitations of the test

- **12 questions is small.** 2-hop and 3-hop subgroups have only 3 and
  2 questions respectively. Single-question flukes move the numbers.
- **No LLM answer scoring.** Scoring is substring match on expected
  filenames in the retrieved context. Doesn't grade answer quality.
- **Query set is content retrieval specifically.** The personal KG's
  hybrid mode may perform differently on temporal queries ("what did
  I do last week"), decision queries, or cross-project memory queries.
  (See the PKM retest for that follow-up.)
- **One corpus.** Applying this fix as a permanent default would need
  validation against a second corpus first. (Done — see the PKM
  retest; the result generalizes.)

## Recommendation

**Do not apply the patch as a permanent default without more testing.**
What it proves is sufficient for the SME benchmark conclusion. What it
does NOT prove is whether the same fix is correct for every query type
the personal KG handles.

Instead:

1. Add the RRF merge as an OPTIONAL mode (`mode=hybrid_rrf` or similar)
   so users can switch between the two strategies per query.
2. Build a second benchmark corpus targeting "recent activity" queries
   (the type of question hybrid mode was likely optimized for).
3. Run both modes against both corpora. Pick the default that wins on
   average, or add query classification to route dynamically.
4. Then decide whether to make RRF the permanent default.

## The core of the fix (inline)

The full patch is not distributed — it applies to a specific retrieval
module in the author's own personal KG codebase. The essential change
is small enough to inline as a worked example. Replace a max-merge
like this:

```python
# Original: max-merge across incommensurable score scales.
# BM25 scores (~0–5) dominate cosine scores (~0–1) regardless of
# whether the BM25 result is actually relevant.
merged: dict[str, SearchResult] = {}
for r in fts_results + sem_results + graph_results:
    if r.note_id not in merged or r.score > merged[r.note_id].score:
        merged[r.note_id] = r
ranked = sorted(merged.values(), key=lambda r: r.score, reverse=True)
```

With a weighted Reciprocal Rank Fusion (Cormack et al. 2009) that
ranks by position within each list rather than by absolute score,
and normalizes the final scores to [0, 1] so downstream rescoring
sees comparable magnitudes:

```python
def _rrf_merge(
    lists_with_weights: list[tuple[list[SearchResult], float]],
    k: int = 60,
) -> list[SearchResult]:
    rrf: dict[str, float] = {}
    seen: dict[str, SearchResult] = {}
    for results, weight in lists_with_weights:
        for rank, r in enumerate(results):
            rrf[r.note_id] = rrf.get(r.note_id, 0.0) + weight * (
                1.0 / (k + rank + 1)
            )
            if r.note_id not in seen:
                seen[r.note_id] = r
    out = []
    for note_id, score in rrf.items():
        r = seen[note_id]
        r.score = score
        out.append(r)
    # Normalize to [0, 1] — raw RRF scores are ~0.01–0.05 and would
    # be dominated by any downstream rescoring term (AFS, BM25, etc.)
    # with a different magnitude, re-inverting the ranking.
    if out:
        max_score = max(r.score for r in out)
        if max_score > 0:
            for r in out:
                r.score = round(r.score / max_score, 6)
    return sorted(out, key=lambda r: r.score, reverse=True)

ranked = _rrf_merge([
    (fts_results,   0.15),
    (sem_results,   0.70),
    (graph_results, 0.15),
])
```

Expected pattern on the author's climate research corpus with this
change: 0/12 → 7/12 full recall, matching the semantic-only mode.
Your numbers will differ depending on your content and question set —
the value of the test is the *delta* between the original max-merge
and the RRF version under identical conditions, not the absolute
recall.

To revert, check out the original `hybrid.py` and restart the API.
