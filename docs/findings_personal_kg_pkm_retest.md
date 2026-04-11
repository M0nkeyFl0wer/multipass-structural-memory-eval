# Personal KG PKM corpus retest — falsifying the "hybrid for PKM" hypothesis

## Why this retest

The climate-research benchmark (see `findings_personal_kg_rrf_fix.md`)
tested the personal KG on content-retrieval queries — "what does X say
about Y" — which isn't the personal KG's actual use case. The correct
objection was:

> "The personal KG is my day-to-day tool for tracking what I'm doing.
> Like it's supposed to be the equivalent of MemPalace — a personal
> knowledge base or whatever. Second brain."

So the previous benchmark was testing the wrong thing. The personal
KG is supposed to be a **personal knowledge base**, and the "correct"
queries are things like "what did I decide about X", "what did I
commit today", "what's my preference for Y", "what was on the April 8
task backlog".

For PKM queries specifically, the hypothesis was: the personal KG's
`hybrid` mode (with session-hub boosting from graph_search) might
actually be the right choice, because session-end notes *are* the
answer to "what did I do" questions. The RRF patch that rescued
hybrid on content retrieval may be the wrong fix for the real use
case.

This retest runs 12 PKM-flavored questions grounded in real notes
from the author's own source tree and compares original hybrid vs
semantic vs RRF-hybrid.

## The corpus

`sme/corpora/personal_kg_pkm_v01/questions.yaml` — 12 questions:

- **2 preference lookups** (approved agent notes)
- **8 substantive session documents**
- **2 recent temporal queries** (session-end notes from 2026-04-10)

Every question has a ground-truth file verified present on disk before
authoring. Expected sources are filename substrings to handle path
differences (e.g. `approved/` vs `unreviewed/`).

All 12 questions are 1-hop factual lookups. No multi-hop in this
corpus — the point is to test "can the personal KG find the specific
note I know exists," not "can it synthesize across multiple notes."

## Results

| Condition | Full recall | Partial | Mean tokens | Tokens per correct |
|---|---|---|---|---|
| **Personal KG hybrid (original max-merge)** | **0/12** | 1/12 | 356 | ∞ |
| **Personal KG semantic** | **5/12** | 6/12 | 575 | 1,380 |
| **Personal KG hybrid (RRF patch)** | **5/12** | 6/12 | 608 | 1,460 |

**Original hybrid is 0/12 on PKM queries.** Zero full recall. One
partial hit. Four of the twelve queries timed out (30s) entirely,
likely due to graph_search slowness on specific terms.

**Semantic is 5/12, matching the RRF patch exactly.** Both rescued
modes answer the same 5 questions correctly. Both modes also get one
more question to partial recall.

## What this falsifies

**The "hybrid mode is correct for PKM queries" hypothesis is dead.**

If hybrid were genuinely optimized for PKM — if session-hub boosting
were the correct retrieval strategy for "what did I do" queries —
original hybrid should have beaten semantic on this corpus. Instead
it's catastrophically worse (0/12 vs 5/12), with the same pattern
observed on the content-retrieval corpus (0/12 vs 7/12 on climate
research).

**Original max-merge hybrid is broken for both query types**, not
just one. The failure mode is consistent: graph_search's raw scores
(4–5 range on session hubs) dominate the MAX merge, pushing
semantically-relevant results below the top-K cutoff. Same bug, same
symptom, across two different corpora with two different query
styles.

Even the quintessential "what did I commit today" query — the *exact*
kind of PKM lookup hybrid was supposedly built for — gets only
partial recall in original hybrid, and only because it happened to
match a generic project name substring. The specific session-end
note from 2026-04-10 is not surfaced.

## Cross-corpus summary

Comparing both benchmarks:

| | Climate research (content retrieval) | Personal KG PKM |
|---|---|---|
| Original hybrid | 0/12 | 0/12 |
| Semantic | 7/12 | 5/12 |
| RRF hybrid | 7/12 | 5/12 |
| Flat ChromaDB | 8/12 | (not tested — no fresh ChromaDB index of the PKM source tree) |

**Same pattern on both corpora.** Original hybrid catastrophic,
semantic and RRF-hybrid equal to each other and much better than
the max-merge baseline. The RRF patch is safe to adopt as a default,
since it does no worse than semantic on PKM queries and dramatically
better than original hybrid on content queries.

## What the personal KG is actually bad at

Seven of the twelve PKM questions fail in **all three modes**. Looking
at which ones fail tells a story about the personal KG's current
index quality:

- **A book-review lookup** fails everywhere. A distinctive name plus
  a specific book title should be easy, but no mode finds it.
  Possibly chunking splits the book review content unfavourably, or
  the embedding of the query isn't close to the embedding of the
  actual content chunks.
- **A project task-backlog query** fails everywhere. A long
  project-level `CLAUDE.md` file dominates this query instead.
- **A project-specific term ("evoskills") query** fails everywhere.
  The same hub file wins again.
- **A landscape-survey query** fails everywhere.
- **A "what uncommitted work do I have" query** fails everywhere.
  The specific session-end note that contains the answer is not
  found, even though it literally contains the text. Could be index
  staleness (indexing lag on very recent files).

**A single long project `CLAUDE.md` file dominates top-3 for many
unrelated queries.** This is a known noise pattern: long project-
level context files have broad topical coverage and match many
semantically adjacent queries. A handful of these "hub" files
pollute the index for everyone else.

This isn't a hybrid-vs-semantic-vs-RRF problem. It's a **baseline
index quality problem** that affects all retrieval modes. The likely
fixes are not in `hybrid_search`:

1. **Chunking**: break long hub files into smaller chunks so one
   hub document doesn't dominate many queries.
2. **TF-IDF or IDF reweighting** to penalize tokens that appear in
   many documents.
3. **MMR (maximal marginal relevance) reranking** to diversify the
   top-K away from single-file domination.
4. **Path-based boost** for notes from session directories when
   queries clearly target personal history.

## Empirical conclusions

1. **Original max-merge hybrid is broken for both content retrieval
   AND PKM queries.** The "session-hub boost is a feature for PKM"
   hypothesis is falsified: even on queries that specifically target
   session-end notes, original hybrid doesn't find them.

2. **The RRF patch is safe to adopt as a default.** On both corpora
   tested, RRF-hybrid equals semantic mode and dramatically exceeds
   original hybrid. No regression observed on either query type.

3. **The bigger problem is index quality**, not merge strategy.
   7/12 PKM questions fail in all three modes due to hub-file noise
   and possibly chunking/staleness issues. Fixing those would
   dramatically improve daily utility more than any merge-layer fix.

4. **The RRF fix should probably ship.** It costs nothing (same
   tokens as semantic), adds no regression, and closes an obvious bug
   where the top-K from three retrievers is a MAX-merge of mismatched
   scales. Even if the deeper index problems remain, landing RRF
   prevents the specific catastrophic failure mode where
   graph_search's high scores wipe out semantic's relevant hits.

## Recommendations in priority order

1. **Do not treat the RRF patch as just a content-retrieval fix.** It
   works equally well on both query types. Consider adopting it as
   the default max-merge replacement.

2. **Investigate long project-level hub files as query hubs.** Those
   single files are polluting many semantic searches. Either
   re-chunk them more finely or add a per-document length penalty in
   retrieval.

3. **Check indexing lag on recent notes.** A query targeting a
   same-day session-end note did not find it, even though the note
   exists on disk. Either the daemon hasn't indexed it yet, or the
   recent-session chunks are losing to older hub content even when
   directly queried.

4. **Consider per-directory boosts for PKM queries.** Session and
   journal notes are much more likely to be PKM answers than random
   README files. A simple path-based boost would dramatically
   improve this class of query without touching the merge strategy.

5. **Grow the benchmark corpus.** 12 questions is small. A 30+
   question corpus targeting the specific PKM query types the system
   claims to serve (decisions, temporal, preferences, session
   lookups) would give stronger statistical signal.

## Methodology note

The climate-research corpus was the wrong first test. It measured
something the personal KG isn't primarily built for and produced a
finding that looked conclusive but was actually conditional. The PKM
retest generalized the conclusion and strengthened the RRF
recommendation, but the whole sequence would have been cleaner as one
session testing both corpora together. Lesson for the next benchmark
built for another system: **author the corpus in the terms the tool
claims to serve, not in the terms the test framework happens to have
examples for**.
