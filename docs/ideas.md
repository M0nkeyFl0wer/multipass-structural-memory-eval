# ideas.md — Structural Memory Evaluation (SME)

*What should a memory system know about its own structure, and how do you test whether it does?*

Status: beta instrumentation. Working CLI + 3 adapters + 2 implemented categories in the [`multipass-structural-memory-eval`](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval) toolkit. Surfaced a real retrieval bug in my own personal KG (RRF fix, 0/12 → 7/12 on two corpora) and an observable routing behaviour on MemPalace that the maintainer can characterize. Mode B (structural diagnostics) works on the graph shapes I have tested. Mode A (retrieval benchmarks) is producing readings that have already changed how my own stack is built, with explicit caveats about the substring-on-filename matcher, small n per hop bucket, and the hop-annotation-is-corpus-not-system problem.

---

## What this framework can credibly claim (and what it cannot)

**The delta is the product, the levels are decoration.** The reproducible findings are controlled before/after deltas under identical conditions (same matcher, same corpus, same questions) and within-system ablations (route on vs off, merge A vs B). Absolute recall numbers are downstream of a substring-on-filename matcher with known biases and should be read as diagnostic readings, not scores. The 0/12 → 7/12 RRF-fix delta is the strongest claim in the project because it is a controlled experiment with one variable changed. The Canadian politics 12/12-across-all-systems result is the weakest because it mostly reads filename overlap, not retrieval quality.

## The headline finding

**Corpus composition determines retrieval quality more than system architecture.**

A clean biographical corpus (Canadian politics, 45 files) makes every retrieval strategy score 12/12. A messy daily-driver KB (personal KG, 70K chunks) exposes merge bugs. A cross-topic research corpus (climate research, 19 files) exposes routing failures. You need multiple corpus shapes to say anything meaningful. Every existing benchmark uses one corpus.

```
                      climate-research  personal-kg-pkm  canadian-politics
                      (content)         (second brain)   (biographical)
Flat ChromaDB         8/12              —                12/12
MemPalace routed      3/12              —                12/12
MemPalace no-route    8/12              —                12/12
personal KG hybrid    0/12              0/12             —
personal KG RRF fix   7/12              5/12             —
personal KG semantic  7/12              5/12             —
```

Two systems tested end-to-end. Two different failure modes surfaced. One specific fix produced (the RRF patch for my own personal KG — unambiguously my bug, my code, my 15-line fix). One observable routing reading on MemPalace that the maintainer can evaluate (not a claim I have standing to call a "bug" in a third-party tool). Neither reading is visible without multi-corpus benchmarking.

---

## What a single corpus would have missed (methodology)

The reason I trust both sets of findings — and believe they're not an artifact of "my benchmark happens to be mean to palace systems" or "SME is biased toward flat retrieval" — is that the same framework produced three very different conclusions on three corpora in one run. Here's the counterfactual for each single-corpus reading:

- **Canadian-politics-only:** Every system scores 12/12. Conclusion: *"retrieval strategy doesn't matter, everything works equally, the framework found nothing interesting."* That would overstate the reading. The 12/12 is partly an artefact of filenames containing their subjects (a plain `grep` would score the same), and the other two corpora surface specific failure modes in both systems that are invisible here.

- **climate-research-only:** MemPalace routed is 25%, flat is 67%, personal KG hybrid is 0%. Conclusion: *"MemPalace routing is broken, personal KG hybrid is broken, use semantic mode."* Oversimplified. The personal KG hybrid failure is a bug I can point at in my own code. The MemPalace reading is a behaviour on a corpus type MemPalace is not primarily designed for — adversarial to its routing ontology by construction, and the maintainer is the right person to decide whether it's a bug or expected behaviour.

- **personal-kg-pkm-only:** Hybrid 0/12, semantic 5/12. Conclusion: *"the personal KG hybrid mode is broken, no signal from MemPalace, no comparison possible."* Missing the corpus that shows both systems CAN work when the data permits.

**Only the three together give the real finding:** *both systems have default behaviours (max-merge for the personal KG, room-based routing for MemPalace) that work fine on clean data and produce surprising readings on corpora that don't match their happy-path assumptions.* Canadian politics is clean (entity-per-file with subjects in filenames). Climate research has cross-topic vocabulary that collides with room names. Personal-kg PKM has long hub files that dominate any merge strategy letting one signal outweigh others. Each corpus triggers a different failure mode, none of the failures are visible on the other corpora, and the three readings are mutually compatible — the framework is not just breaking on one corpus and calling that a bug.

This is the single most important methodology point in the whole exercise: **no single benchmark corpus can tell you whether your retrieval is any good.** Every published memory benchmark I'm aware of — LongMemEval, LoCoMo, MINE, GraphRAG-Bench — uses one corpus shape. The sampling bias is enormous and invisible.

---

## The comparative advantage: A/B/C isolation

What SME does that existing memory benchmarks don't is isolate the contribution of the structural layer from the contribution of the underlying index. Every Cat 2c / Cat 7 run executes the same system in three conditions on the same questions:

- **Condition A (flat baseline)** — no structure, top-K cosine similarity on the raw index
- **Condition B (full pipeline)** — structural layer enabled, the thing users actually experience
- **Condition C (structure disabled, same index)** — same underlying index as B, with the router / filter / scoper turned off

LongMemEval, LoCoMo, GraphRAG-Bench, and BEAM can tell you which system scored higher on a fixed corpus. They cannot tell you whether the structure that system added is what earned the score, or whether the raw index would have scored the same without it. The B−C delta is the structural contribution. The C−A delta is whatever metadata, rendering, or scoping overhead the pipeline adds on top of the same index. Reporting both separately turns "structure earns its complexity" from a vibe into a testable claim.

This is also what made the MemPalace finding legible: "route=None recovers flat behavior exactly on this corpus" is a B vs C comparison on the same ChromaDB index, not a cross-system score comparison. It isolates the router as the variable that moved the readings. No published benchmark produces that kind of reading.

---

## What the diagnostic surfaced

**Personal KG — a real bug I found, fixed, and can point at in my own code.** MAX-merge of incommensurable scores. FTS BM25 scores (4-5) always beat semantic cosine scores (0.7-0.9) in the max-merge, regardless of relevance. Session-log hub notes dominate every query. Fix: weighted normalized RRF merge (0.15 FTS / 0.70 semantic / 0.15 graph). Moves hybrid from 0/12 to 7/12 on two corpora, zero regressions under identical conditions. Patch applied.

The deeper problem underneath: 60% of questions fail in ALL modes including semantic. Hub-file pollution — session-log hub notes dominating top-3 for unrelated queries. Index quality, not merge strategy. Planned fixes: re-chunk hub files, IDF reweighting, MMR diversity, path-based boost.

**MemPalace — an observable routing reading on an adversarial corpus.** On the climate research corpus, 9 of 12 questions contain the word "climate" verbatim, and the router sends all 9 to the `climate_evidence` room regardless of what the query actually asks. Only 1 of those 9 had its expected source file in that room. The 3 queries without "climate" fall through to unscoped ChromaDB search and all recover. Net result on this corpus: 3/12 full recall routed vs 8/12 full recall flat. Full recall by hop depth verified 2026-04-11: flat 7/7, 1/3, 0/2 across 1/2/3-hop; routed 3/7, 0/3, 0/2. Routing hurts at 1-hop (where flat succeeds cleanly) and is neutral at 3-hop (where nothing succeeds). The `retrieval_path` field in the benchmark JSON shows every routing decision. I have not read the router source, so what I can report is the observable effect (every climate-adjacent query lands in `climate_evidence`), not the internal mechanism. Proposed investigation direction: embed room names, route by cosine similarity to multiple top-N rooms instead of whatever one-room rule is currently firing, and fall through gracefully when the top-K rooms are close. ~30–50 lines sketched against the observable behaviour. Additional readings from the Blueprint test: halls 0% populated on the project-mining path I tested, closets absent from the ChromaDB metadata I queried, tunnels at 1.1% density (string-match only). **Important caveat**: this corpus is adversarial to MemPalace's primary design target (conversational memory with "my {room} stuff" queries); a router designed for that distribution will underperform on cross-topic research queries by construction. The reading is diagnostic, not a benchmark claim about MemPalace in general.

Both readings are invisible to structural diagnostics (The Threshold, The Missing Room, The Blueprint) in isolation. Both are visible only through retrieval readings (The Stairway, The Abacus). You need both modes.

---

## The diagnostic loop

Hypothesis → prediction → experiment → confirmation → fix → verification.

1. "AFS weight tuning fixes hybrid." Predicted no (AFS is downstream of merge). Tested pure-similarity config. Byte-identical 0/12. Prediction confirmed.
2. "Bug is in the merge step." Stubbed FTS and graph to empty. 7/12 — matches semantic exactly. Merge confirmed as failure point.
3. "RRF merge rescues hybrid." Five variants tested. Normalized weighted RRF at 0.15/0.70/0.15 hits 7/12. Hybrid rescued.
4. "RRF might regress on PKM queries." Retested on the personal KG corpus. 0/12 → 5/12, matches semantic. Hypothesis falsified — RRF is safe on both query types.

Scientific method, applied to retrieval engineering. This is what the framework enables.

---

## What SME is

Nine tests. Not a hierarchy, a menu. Pick the tests that match your use case. Each test has a descriptive name with a spatial nod to the palace metaphor (so "Cat 2c" is no longer the shorthand that everyone has to decode).

| # | Name | Category | Novel? | What it tests |
|---|---|---|---|---|
| 1 | **The Lookup** | Factual Retrieval | No | Finding a known fact in a known room. |
| 2 | **The Crossing** | Cross-Domain Discovery | Partial | Walking between rooms that do not name each other. |
| 2b | **The Registry** | Canonicalization | Partial | How many names does one thing have, and are they all registered as the same resident? |
| 2c | **The Stairway** | Multi-Hop by Depth | Partial | One flight, two flights, three — does recall hold at each step up? |
| 3 | **The Dissonance** | Contradiction Detection | Partial | When two drawers disagree, does the system notice or silently pick a side? |
| 4 | **The Threshold** | Ingestion Integrity | **Yes** | What crosses the front door intact, and what gets mangled on the way in. |
| 5 | **The Missing Room** | Gap Detection | **Yes** | Persistent homology finds chambers that should exist and do not. |
| 6 | **The Archive** | Temporal Reasoning | Partial | Current truth versus historical truth, respecting provenance chains. |
| 7 | **The Abacus** | Token Efficiency | **Yes** | Tokens per correct answer, multi-condition, counting beads live. |
| 8 | **The Blueprint** | Ontology Coherence | **Yes** | Graph vs declared schema / README claims / inferred structure. |
| 9 | **The Handshake** | Harness Integration | **Yes** | Does the model actually reach for the memory through its harness — tool call, MCP, hook, slash command — and does the returned context land in a form it can use? Does the same system work across models and harnesses? |

### The category we nearly missed — why Cat 9 exists

Categories 1–8 all measure **offline retrieval**: given this query, does the retriever return the right document? Every published memory benchmark I am aware of (LongMemEval, LoCoMo, MINE, GraphRAG-Bench, BEAM) makes the same design choice. And so did the first eight tests in this framework — until partway through writing this overview, when it became obvious that we had not measured the thing that matters most in practice: **does the model actually reach the memory when it runs**?

In production, no memory system is ever reached in isolation. It is reached through an invocation surface — a tool call, an MCP resource, a Claude Code hook, a slash command, a custom GPT action, a file watcher. The effective memory for a specific deployment is roughly:

```
effective_memory  ≈  retrieval_quality  ×  invocation_rate  ×  call_through_success  ×  result_usage
```

Categories 1–8 measure only the first factor. They assume the other three are 100%. That assumption is almost never true, and it is the first thing a deployment engineer notices when they move a memory system from benchmark to production. A RAG scoring 95% on offline Cat 1 that gets called 20% of the time in production is a 19% effective memory for that specific deployment. And the gap is strongly a function of **which model** is at the wheel and **which harness** mediates the call. Claude Sonnet 4.5, Claude Opus 4.6, GPT-4, Gemini, and Llama have different tool-use priors, and the same memory system reached through an MCP server, a Claude Code hook, a LangChain tool, and a ChatGPT custom GPT action can produce wildly different call-through rates on the same corpus.

**Cat 9 (The Handshake) measures this directly.** See the spec for full sub-test definitions (9a-9g). The short version: run the same question set twice. Once offline (the Cat 1/7 baseline, which gives the ceiling of what the memory *can* answer). Once in-harness, reaching the memory through its actual production invocation surface with a specific target model running in its native harness. The delta is the harness-integration gap. Report per-(model, harness) so you can see which combinations work.

This category is spec'd but not implemented yet. It is the highest-priority next addition because it is the thing that turns every other measurement in the framework into a claim about a **specific build** — your memory system, your harness, your model — rather than a claim about a retriever in isolation. That is the question every deployment engineer actually has, and no existing benchmark answers it.

**The methodology point is bigger than the test.** Any memory-system evaluation that does not include a harness-integration measurement is describing a lower bound on how well the system *could* work if the model always reached for it, not an estimate of how well it *will* work when you ship. Benchmarks that stop at offline retrieval — which is all of them today, including Cats 1–8 of this framework — are measuring the wrong thing for the question deployment engineers are asking.

### Use-case profiles

| Use case | Systems | Run these | Skip these |
|---|---|---|---|
| Conversational memory | MemPalace, Mem0, Zep | 1, 3, 6, 7, **9** | 4, 5, 8 |
| Research infrastructure | personal KG, open-newsroom-graph | all | — |
| Decision support | Election Oracle, Canadian politics graph | 1, 2, 5, 6, 8, **9** | 4 |
| Content strategy | climate research corpus | 5, 8 | 1-4, 6-7 |
| Any production deployment | anything actually reached by a running model | 1, 7, **9 is essential** | — |
| Just use folders | Karpathy wiki | none — SME is overkill | all |

---

## Structural findings from four graphs

Same adapter code, no per-project changes, across three LadybugDB schemas + one MemPalace.

| Metric | personal KG | Canadian politics | re-wilding (k-core) | re-wilding (full) |
|---|---|---|---|---|
| Entities | 1,996 | 6,672 | 17,358 | 66,900 |
| Edges | 1,438 | 12,590 | 52,816 | 657,934 |
| Isolated % | 69% | 4.5% | 79% | <0.01% |
| Modularity | 0.579 | 0.642 | 0.436 | 0.458 |
| Edge entropy | 2.95 | 2.94 | 2.30 | 0.91 |

**Edge type entropy validated as monoculture detector.** 2.95 (healthy), 2.30 (concentrated), 0.91 (severe — MENTIONED_IN at 86%). Raw bit thresholds are vocabulary-size-sensitive — a graph with 2 equally-used edge types has entropy 1.0 bits, which the raw threshold would flag as "severe monoculture" even though the distribution is perfectly balanced. The fix is to normalize by `log2(len(declared_edge_types))`, yielding a [0,1] score where 1.0 is perfectly balanced across the declared vocabulary and 0.0 is a pure monoculture. Normalized thresholds (planned): ≥0.8 healthy, 0.5–0.8 concentrated, <0.5 monoculture. Raw-bit numbers remain reported alongside for back-compat with earlier runs.

**KNOWLEDGE_CORPUS pattern:** 69-79% entity isolation in semantic layer is structural, not a bug. Pipeline links entities to documents, not to each other. NARRATIVE_GRAPH (Canadian politics 4.5%) shows the opposite.

**Re-wilding ontology drift:** 11 declared edge types, 6 effective. Ghost types (INFLUENCES, OPPOSES, RESPONDS_TO) are inferential — require Claude API, not local models. Drift score 0.45.

**MemPalace Blueprint reading:** Halls 0% populated on the project-mining path tested (narrower than "halls don't work" — may be populated by a different miner I did not run). Closets absent from the ChromaDB metadata queried. Tunnels at 1.1% density (string-match only). The README's "wing filtering improves retrieval" claim reads the other direction on the climate research corpus — on this corpus, routing reduces recall, explained by the room-collapse described above. Type homogeneity passes the threshold check but trivially, because 96.9% of drawers are `drawer:untyped` — a uniform distribution is tautologically partitioned.

---

## The context engineering framing

Strip away the abstractions. Every system is a context engineering tool — it decides what goes in the model's context window.

- **Karpathy wiki:** folders + markdown + "hey Claude, read this folder." Works at ~100 articles / ~400K words. His explicit anti-pattern list: "overengineering to avoid: HTTP servers, SQLite graph databases, local embedding models."
- **MemPalace:** folders with metadata labels + ChromaDB semantic search within labels. The "palace" is a WHERE clause. The +34% is scope narrowing.
- **Personal KG:** extraction → graph → scoring → "here's what's relevant." Sophisticated pointing machine. The RRF bug was the pointing machine pointing at the wrong files.

The graph earns its keep in two places context windows can't replace:

**1. Context selection at scale.** When 70K chunks don't fit in context, something has to decide what goes in. That's retrieval. The question is whether structured retrieval beats flat retrieval. Current answer: only if the scoring layer doesn't corrupt the signal, and only on corpora with adversarial characteristics (hub files, cross-topic noise).

**2. Structural findings the model can't derive from text.** "Your research has zero bridges." "6 of 11 edge types are ghosts." "Session logs outrank source content due to score scale mismatch." These are properties of the knowledge shape, not the knowledge content. No amount of text in the window reveals them.

### The scale question nobody has tested

```
Corpus size:  19 files → 200 → 2,000 → 20,000 → 70,000 chunks

At what scale does structured retrieval start beating flat?
At what scale does flat stop fitting in context?
At what scale is Karpathy's "just read the folder" no longer viable?
Is there a crossover, or does flat win at every scale?
```

Add Condition D (frontier model, full context, no retrieval) at each tier. If Condition D wins until context overflow, the retrieval infrastructure is a worse version of "give the smart model all the text."

---

## The categories are a menu, not a hierarchy

The industry standard metrics (LongMemEval, LoCoMo, BEAM) are right for conversational memory. They're not wrong. They're incomplete for systems where structure is the product.

SME's contribution isn't "better than LongMemEval." It's "here's the full menu, pick what matches your use case." And: "you need multiple corpus shapes to say anything meaningful." And: "the framework should find bugs and suggest fixes, not just produce scores."

---

## The philosophical question

The climate research corpus finding — "your research has zero bridges, modularity 0.734, five communities are silos" — came from NetworkX counting edges. Not thinking. Counting. But the insight — "my climate comms project treats fossil fuel money and extreme weather as strangers" — was human. The algorithm made invisible structure visible. The human decided what the structure meant.

Vector search is a compressed encoding of meaning that happens to be searchable. The graph adds a non-geometric layer: typed edges, directionality, provenance. Two entities can be far apart in embedding space but connected by a CONTRADICTS edge. The question is whether that discrete scaffold does work the continuous layers can't.

Current answer: for retrieval, the scaffold is neutral-to-positive once the scoring layer is fixed. For structural findings, the scaffold is the only option. For provenance and traceability (the application backend use cases), the scaffold is essential regardless of what happens with context windows.

The honest position: Mode B (structural diagnostics) is counting. It works. Mode A (retrieval benchmarks) found that the pointing machine was broken and fixed it. The graph's durable value may be structural findings and provenance chains, not retrieval improvement.

---

## Three value propositions, three levels of infrastructure

- **Remember:** folders + model. Karpathy wins. The personal KG is overengineered for this.
- **Prove:** typed edges + provenance + temporal validity. Graph wins. Application backends (newsroom, election oracle, Canadian politics research, Monkey Flower) live here.
- **Think:** visualization + topology + structural findings. Graph is the only option.

---

## MemPalace connection

[Issue #101](https://github.com/milla-jovovich/mempalace/issues/101) is my feature request. Thanked as @M0nkeyFl0wer in v3.0.0 release notes. Benchmark controversy (#27, #29, #39, #125) is direct context.

PR planned: `mempalace/eval/` as a diagnostic tool. Three tests (The Blueprint, The Stairway, The Abacus). Leads with investigation directions (semantic router, hall population, semantic tunnels), explicitly framed as suggestions rather than prescriptions. Shows our own 0/12 catastrophic hybrid-merge failure alongside the MemPalace room-routing reading on the climate corpus. Framing: "we built a diagnostic, it found a bug in our own code first, and here is what it read on yours — you tell us whether it is a bug or expected behaviour." Diagnostic posture, not scoreboard.

Wait for personal KG enrichment cycles before posting, so comparison is fair.

---

## Open questions

- **Condition D (frontier model, full context) not yet tested.** At 19 files it probably wins everything. The scale crossover experiment is the thing that would make this genuinely novel.
- **The personal KG is a newborn after rebuild.** Enrichment cycles haven't run. Entity-to-entity edges haven't accumulated. Fair comparison requires maturation time.
- **Temporal dimension missing.** Snapshot systems (MemPalace) vs lifecycle systems (the personal KG). Learning rate over time is the honest comparison, not point-in-time scores.
- **Index quality > architecture.** 60% of personal KG failures are hub-file pollution, not graph bugs. Re-chunking hub files would improve daily utility more than any graph fix.
- **12 questions is thin.** Single-question flukes move the numbers. Need 30+ per corpus.
- **No LLM answer-quality judge yet.** Current scoring is substring match on expected filenames. Real Cat 7 pairwise needs GPT-4o-mini. Note that a judge is not a clean escape from the matcher — it replaces one known bias (filename overlap) with three new ones (judge model bias, judge variance across runs, judge calibration against humans). Honest upgrade path: grep-floor baseline → judge with k=3 samples → human spot-check of 20 items per corpus for calibration.
- **No grep-floor baseline condition yet.** `grep -l <keyword>` on filenames is the floor for the substring matcher — any retriever scoring at or below grep is reading filename overlap, not retrieval quality. The Canadian politics 12/12 result is consistent with a grep-floor ceiling, and we won't know how much of every other reported score is filename bias until the floor is reported alongside A/B/C. This is the highest-leverage cheap fix and lands before the LLM judge.
- **Hop depth is annotated on the ground-truth graph, not the system's graph.** Cat 2c currently assumes a question labeled 3-hop requires 3 hops in every system under test. That assumption breaks when the system's index contains a direct edge between endpoints (the question is 1-hop there) or when the intermediate edges don't exist at all (the question is structurally unreachable). Planned fix: a per-question reachability pre-test against each system's graph snapshot. Questions where no path of length ≤k exists move to a separate "unreachable in this graph" bucket and are excluded from the per-depth breakdown. Without this gate, "graph did not pull ahead at 3-hop" conflates "routing is broken" with "the edges this annotation assumed never existed."
- **Cat 9 (The Handshake) is spec'd but not implemented.** Categories 1–8 measure offline retrieval only. Until Cat 9 ships, every reading in this framework describes a lower bound on how well the system *could* work if the model always reached for it — not an estimate of how well it *will* work when plumbed into a specific harness and model. This is the largest gap in the current instrumentation and the highest-priority next build, because it is the thing that turns every other measurement into a claim about a specific deployment rather than a retriever in isolation. See Cat 9 in the spec for sub-test definitions and the harness-manifest adapter contract.

---

## Build order (updated)

1. ~~Adapter interface + flat baseline~~ ✓
2. ~~LadybugDB adapter~~ ✓
3. ~~Cat 1/2c/7 retrieval benchmarks~~ ✓
4. ~~Cat 8 ontology coherence~~ ✓
5. ~~RRF fix for personal KG~~ ✓ applied and live
6. ~~Three corpora benchmarked~~ ✓ climate research, personal-kg PKM, Canadian politics
7. Apply RRF patch permanently ← done this session
8. Fix personal KG index quality (re-chunk hub files, MMR diversity)
9. Run Canadian politics on personal KG (the clean-corpus graph test)
10. **Grep-floor baseline condition** (cheap, high-leverage, quantifies filename-matcher bias before spending on a judge)
11. **Hop-reachability pre-test gate** for Cat 2c (resolves the "router broken vs edges missing" conflation)
12. **Normalized edge-type entropy** (`entropy / log2(vocab_size)`, [0,1] scale, vocab-size invariant)
13. **Cat 9 (The Handshake) — harness integration MVP.** Adapter `get_harness_manifest()` method. Model-runner shim for Claude Sonnet 4.5 and Claude Opus 4.6 via the Anthropic API. Sub-tests 9a (invocation rate), 9b (call-through success), 9c (result usage) against a tool-call harness first; 9g (Claude Code hook-driven) after. 9e and 9f (cross-model, cross-harness reporting) added once at least two harnesses and two models are wired. This is the highest-leverage build on the list after grep-floor, because it is the thing that turns Cat 1–8 readings from "the retriever can do X" into "this deployment does X with this model in this harness."
14. MemPalace PR (diagnostic framing, with fixes)
15. Condition D (frontier model, full context) — the honest test
16. Scale crossover experiment (30 → 300 → 3,000 → 30,000 notes)
17. LLM judge for Cat 7 pairwise (with k=3 samples and 20-item human calibration per corpus)
18. Remaining offline categories (Cat 3, 6)
19. ideas.md → multipass-structural-memory-eval repo README

---

## Prior art (all open source)

- **LongMemEval** (ICLR 2025) — 500 questions, judge methodology
- **KGGen MINE** (Stanford, NeurIPS 2025) — extraction quality benchmark
- **GraphRAG-Bench** (ICLR 2026) — pipeline-wide evaluation
- **Microsoft BenchmarkQED** — automated RAG benchmarking
- **Zep/Graphiti** — temporal KG, 94.8% DMR
- **ENGRAM** — typed memory, 95.5% token reduction
- **Karpathy LLM Wiki** (April 2026) — folders + markdown + LLM. The honest baseline.

---

---

*Last updated: 2026-04-11. Living document.*
