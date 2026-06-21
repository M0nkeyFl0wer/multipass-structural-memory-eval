# Graph Performance Benchmarks — Related Work

> **Date:** 2026-06-20
> **Scope:** `prrao87/graph-benchmark` and the LadybugDB "better graph database
> ball" optimization post, mapped against SME's structural diagnostics.
> **Purpose:** Locate the performance/latency-benchmark genre relative to SME,
> establish that they measure orthogonal axes, and identify the one method worth
> borrowing (generative dataset with known ground truth) and the one bridge worth
> writing up (topology as a workload-cost predictor).

This is the fifth benchmark family relative to the four in
`docs/industry_benchmark_gap_analysis_2026.md` (RAG Triad/TRACe, conversational
memory, NIAH, domain-specific reasoning). That doc does not cover performance
benchmarking at all; this note is the additive section, summarized there as §2.5.

## What prrao87/graph-benchmark is

A pure latency benchmark on a **synthetic** graph. Faker generates a 100K-person
social-network graph with a fixed schema (`Person FOLLOWS Person`, `LIVES_IN`,
`HAS_INTEREST`, `CITY_IN`, `STATE_IN`), then a 9-query suite is timed in
milliseconds across **four separately-versioned engines**. The dataset is
**correct by construction** — Faker does not fabricate edges, drop entities,
duplicate entities, or drift an ontology. Correctness is therefore not a variable
in the benchmark; it is an assumption.

> **Verified against the current README on 2026-06-20** (raw fetch of
> `prrao87/graph-benchmark@main`):
> - Dataset: 100,000 persons; 2,417,738 `FOLLOWS` edges (~2.4M); **500 planted
>   super-nodes**; 9 queries (q1–q9).
> - Engines and pinned versions: **Neo4j 2025.12.1, Kuzu 0.11.3, Ladybug 0.15.3,
>   lance-graph 0.5.4**.
> - q8 ("how many second-degree paths exist?"): Neo4j **2831.2 ms** vs Ladybug
>   **7.3 ms** (385.8×); Kuzu 6.5 ms (435.3×); lance-graph 126.2 ms.
> - The README itself notes RNG variance across runs, so trends — not exact
>   milliseconds — are the durable claim.
>
> **Version caveat (load-bearing for the founder).** The published numbers are
> for **ladybug-0.15.3**, which is **not** the latest release — PyPI `ladybug`
> is at **0.17.1** as of 2026-06-20, post-dating the storage work in the "ball"
> post below. Do not present these figures as reflecting current Ladybug
> performance; cite them as "0.15.3, as published." We re-ran both 0.15.3 and
> 0.17.1 ourselves on one machine to get a current, apples-to-apples delta — see
> the next section.

## Re-run on ladybug 0.17.1 — measured 2026-06-20

The published table is locked to ladybug-0.15.3, so to give current numbers we
re-ran the benchmark ourselves on **0.17.1** (latest) and, for a fair delta, on
**0.15.3** on the *same machine*. Both from PyPI wheels.

**Method (identical for both versions):** cloned `prrao87/graph-benchmark@main`,
regenerated the dataset with `generate_data.sh 100000` (RNG-regenerated, same
shape: 100K persons / 2,417,738 follows edges / 500 super-nodes), ingested via the
repo's own `build_graph.py`, ran the repo's own `benchmark_query.py` with the
documented invocation (`pytest-benchmark`, `--benchmark-min-rounds=5
--benchmark-warmup-iterations=5 --benchmark-disable-gc`). Environment:
monkey-flower desktop, 12 cores, load ~1.5–2.0, Python 3.13. Two runs per version.
The benchmark scripts ran **unmodified** on 0.17.1 (the only API drift —
`QueryResult.to_dicts()` → `.get_as_pl()` — is already absorbed inside `query.py`).

**Median latency (ms), this machine, two runs each:**

| Query | 0.15.3 (A / B) | 0.17.1 (A / B) | *published 0.15.3 (prrao87 box)* |
| --- | --- | --- | --- |
| q1 | 486.8 / 494.2 | 529.0 / 486.9 | *152.0* |
| q2 | 762.9 / 746.8 | 775.4 / 766.5 | *236.8* |
| q3 | 43.5 / 36.5 | 33.4 / 33.8 | *6.7* |
| q4 | 50.6 / 39.0 | 50.4 / 67.5 | *10.2* |
| q5 | 60.9 / 61.9 | 56.2 / 61.2 | *11.5* |
| q6 | 124.5 / 112.4 | 131.7 / 123.6 | *30.0* |
| q7 | 69.8 / 61.1 | 64.9 / 60.6 | *12.1* |
| q8 | 28.7 / 25.2 | 27.9 / 26.4 | *7.1* |
| q9 | 163.6 / 161.2 | 166.0 / 165.9 | *94.3* |

On-disk DB size: **0.15.3 = 50 MB, 0.17.1 = 45 MB (~10% smaller).**

**Findings (honest, founder-facing):**

1. **Latency: 0.17.1 ≈ 0.15.3 — no regression, no notable gain on this read-only
   suite.** The version-to-version differences are *smaller than each version's
   own run-to-run variance* (e.g. 0.17.1 q4 swings 50.4→67.5 ms between its own
   two runs), so the deltas are noise, not signal.
2. **On-disk footprint shrank ~10% (50→45 MB) on 0.17.1** — a real, repeatable
   improvement, consistent with the storage work described in the "ball" post.
3. **Absolute ms are not comparable to the published table.** This desktop is
   ~3–4× slower than prrao87's box on the *same* version (published 0.15.3 q8
   = 7.1 ms vs our 0.15.3 q8 ≈ 27 ms), so read the published numbers as *their*
   hardware and our numbers only against *each other*. Hardware/load dominates
   absolute timings; only the same-box version delta is valid here.
4. **Query shape is preserved across versions:** the follower-aggregation queries
   (q1/q2) are the heavy ones; the second-degree path-count (q8) stays cheap —
   the factorization/WCOJ advantage holds in both 0.15.3 and 0.17.1.
5. **Scope of this re-run:** read-query latency + load-once ingest only. It does
   **not** exercise the space-amplification tuning knobs from the "ball" post
   (hash-index-off / forward-only rels — those need config changes and on-disk
   measurement), and it does **not** reproduce the cross-engine gap (we ran
   ladybug only — no Neo4j/lance-graph on this box).

> Scratch tree for this run: `/tmp/graph-benchmark-rerun` (not committed). Anyone
> can reproduce with the method above; numbers will shift with hardware/load but
> the 0.15.3≈0.17.1 conclusion should hold.

## The core relationship: orthogonal axes

- A performance benchmark asks: **"given a correct graph, how fast does the
  engine answer?"**
- SME asks: **"given an engine, is the graph correct, complete, and coherent?"**

The performance genre *defines away* precisely the thing SME measures. Clean data
in, speed measured, correctness assumed. That is SME's differentiation expressed
against a careful, real artifact rather than as a slogan.

### Why the genre is structurally blind to construction quality

This is the founder-safe framing, and it is also the stronger one. Because the
generator emits **ground-truth-clean** data, a performance benchmark cannot
observe any failure that lives in how a *real* graph gets built from messy input:

- **fabricated edges** — an LLM extraction pipeline inventing relationships that
  aren't in the source;
- **fragmented / duplicate entities** — the same real-world thing landing as
  several nodes (or several things collapsed into one);
- **ontology drift** — entity/edge types diverging from the schema over
  successive ingests.

None of these are properties of the *engine* — they are properties of the
*pipeline that populates it*. That is exactly the axis SME measures (Cat 4
ingestion integrity, Cat 8 ontology coherence), and it is genuinely complementary
to a latency benchmark rather than a criticism of one. Clean data in, speed
measured; SME asks whether the data was clean in the first place.

A secondary, neutral observation: the load-once-then-read harness shape also
doesn't exercise incremental-write/checkpoint paths. State this only as "not
exercised," nothing more.

> **Do not assert storage corruption.** An earlier internal note framed the
> blind spot around a specific LadybugDB incremental-write corruption. As of
> 2026-06-20 that claim is **unconfirmed on the latest build**: a minimal
> standalone repro on **0.17.1** (pristine DB, single process, per-edge
> intended-state tracking, 30 trials across 6 mechanisms) found **zero
> corruption**; the original observation is best explained as a mis-measured
> dedup-merge effect (a raw before/after aggregate delta crediting none of the
> merge's intended changes). This claim must not appear in any founder-facing or
> public writeup. It is omitted from the construction-quality framing above
> deliberately, and that framing does not need it.

## What's worth borrowing: generative dataset with known ground truth

The reusable methodological move is `generate_data.sh N` — a scalable synthetic
generator whose ground truth is known by construction. SME's corpus today is
fixed and hand-built, which makes SME a *test suite*. A defect-injecting
generator —

```
generate_corpus.sh N --fabrication-rate 0.45 --missing-rate 0.1 --dup-rate ...
```

— synthesizes a graph with planted fabrications, missing entities, duplicate
entities, and ontology violations at controllable rates. Then Cat 4/5/8 can be
scored as **detection precision/recall against defects you injected**, at scale.
That is the move that turns SME from runnable into citable. (Scoped separately as
a feature; this note only records the rationale.)

## The bridge worth writing up: topology as a workload-cost predictor

The two genres meet at **topology**, not methodology. The benchmark's entire
result table is driven by graph structure: the discriminating path queries
explode specifically because the generator plants super-nodes and cliques —
hub density causes path-count explosions. The variable that determines the
performance curve *is* the degree distribution / hub presence / clique density /
fanout — exactly what SME's Cat 5 instruments measure (centrality, Louvain
communities, degree distribution, connectivity).

So a latency benchmark *observes* that a path query explodes; SME's topology
layer can *explain and predict* it from the graph's structural signature. The
unclaimed ground: **structural / persistent-homology signature as a workload-cost
predictor.** That is paper-shaped and is parked in `docs/ideas.md`, not a test.

Operationally it also pays off for free: a sparse, fragmented graph (low LCC,
low mean degree, mostly isolated entities) lacks the hub density to explode on
the path queries that discriminate this benchmark — so SME's existing
connectivity instruments already predict the performance profile without running
a latency benchmark at all.

## Context: the LadybugDB "ball" optimization post

`blog.ladybugdb.com/post/better-graph-database-ball/` — vendor-self-reported, so
discount the framing, but the substance is useful:

- **Space amplification:** default config ~2× DuckDB on this workload; disabling
  the default hash-index-as-PK and switching to forward-only rel storage closes
  most of the gap. Relevant to the production graph's footprint *only after*
  auditing whether backward traversals ("who points at this entity") are actually
  used — for a KG they often are, so do not drop them blind.
- **Health signal:** maintainer responded to a third-party benchmark that beat
  them within weeks, credited DuckDB openly, and shipped concrete PRs. Engaged,
  research-honest maintainer — a positive datapoint for depending on the engine.
- **Honest performance read:** even post-optimization, DuckDB remains multiples
  faster on every query. Not SME's bottleneck — SME's traversal/topology runs
  offline in NetworkX/Ripser and uses the engine as edge storage + projection
  source, not as a hot serving path.
