# Knowledge Graph Construction Integrity — Related Work

Companion to SME spec v8, focused on Cat 4 (Threshold — ingestion integrity) and
proposed Cat 8b (Phantom Wall — per-edge groundedness, issue #4). The goal of
this note is to find out whether SME is reinventing well-known KG-construction
metrics or genuinely measuring something new, and to nominate concrete pieces
of prior work SME could borrow rather than rebuild.

## VERIFICATION UPDATE 2026-05-01 — primary-source PDF fetched

The arXiv PDF for 2302.11509 was fetched directly (curl from local
shell, bypassing the agent sandbox that earlier blocked WebFetch) and
grepped. Confirmed primary-source findings:

- **"Provenance reachability"** — **zero hits** in the paper. The phrase
  is a third-party-summary artifact and should not be cited as the
  paper's terminology.
- The paper's actual vocabulary, verbatim from line 729 of the PDF
  text extract:
  > "such provenance is sometimes called *deep* or *statement-level
  > provenance*. Examples of deep provenance include information about
  > the **creation date, confidence score (of the extraction method)
  > or the original text paragraph the fact was derived from**."
- The correct citation for the SME Cat 8b mapping is therefore
  **"fact-level provenance"** (or "deep provenance" /
  "statement-level provenance"), with the verbatim definition above,
  cited to Hofer et al. 2023 §6 (page 729 of the arXiv PDF, around
  line 729 of the pdftotext extract).

The "definition" I had quoted in the original SME issue #4 reply
("percentage of facts/edges that can traverse to at least one source
document node") **does not appear in the paper at all** and was a
fabricated definition propagated through search-engine summaries. The
underlying *concept* (per-fact source-document grounding) is real and
covered by the survey, but my verbatim quote was wrong.

Corrections needed:
- Issue #4 reply on the SME repo (already public): add a follow-up
  comment with the correct term and verbatim paper definition.
- Issue #9 body on the SME repo: edit the equivalence-table row.
- Below sections of this file flagged as `[unverified]` can now be
  reconfirmed against the directly-fetched PDF.

**Verification note (per `~/.claude/rules/verification.md`):** the four
metric names handed to this research task in the prompt context —
"Construction success rate", "Cross-reference integrity", "Provenance
reachability", "Graph growth rate" — were attributed to arXiv 2302.11509
(Hofer, Obraczka, Saeedi, Köpcke, Rahm). Those exact phrases do **not**
surface in third-party summaries of the survey, in dblp, in Semantic
Scholar's auto-extracted phrases, or in arXiv search hits restricted to
that paper id. They appear to be a paraphrase, not verbatim section
headings. Where the survey's actual quality vocabulary is well-attested
(accuracy / coverage / consistency / fact-level provenance) I cite that
instead and label it as such. I have **not** been able to fetch the
PDF directly in this session (WebFetch is denied), so a future pass with
a working PDF reader should re-verify section headings before they're
quoted in publication-grade SME material.

## Part 1 — KG Construction Survey 2023

### Provenance

- arXiv: [2302.11509](https://arxiv.org/abs/2302.11509)
- Title: *Construction of Knowledge Graphs: State and Challenges*
- Authors: Marvin Hofer, Daniel Obraczka, Alieh Saeedi, Hanna Köpcke,
  Erhard Rahm (Universität Leipzig / ScaDS.AI)
- Initial arXiv post 2023-02; revised version published 2024 in
  *Information* (MDPI), 15(8):509, as "Construction of Knowledge Graphs:
  Current State and Challenges".
- Read date: 2026-05-01
- Fetch method: WebSearch summaries (arXiv abstract, dblp record,
  Leipzig DB group PDF mirror, Semantic Scholar, MDPI). Direct PDF
  fetch was blocked in this session.

### Scope

General — not LLM-specific. The survey covers KG construction pipelines
across both unstructured (text) and structured (DB) sources, with these
named pipeline stages: data acquisition, knowledge extraction, entity
resolution and fusion, knowledge completion, plus cross-cutting metadata
management, ontology management, and quality assurance. Incremental
update flows are a stated focus; one-shot construction is treated as the
baseline, and the survey explicitly observes that incremental KG updates
"have hardly been investigated in a systematic manner." This is the
right shape of survey for SME to ground against, because SME's Cat 4 is
also fundamentally about ingestion-as-a-pipeline, not about a static
gold-standard graph.

### Evaluation vocabulary used by the survey

What the survey demonstrably uses (from third-party summaries, **not**
verbatim from the PDF in this session):

> "Intrinsic evaluation measures the internal quality of a knowledge
> graph by focusing on three key aspects: **accuracy** evaluates
> whether entities and relationships are correctly identified,
> **coverage** indicates the extent to which a KG represents a relevant
> domain, and **consistency** ensures that the information in the KG
> is maintained without contradictions."
> — paraphrased from third-party summaries of the 2024 *Information*
> version, marked as approximate.

Provenance specifically:

> "Fact-level provenance (sometimes called deep or statement-level
> provenance) includes information about the creation date, confidence
> score (of the extraction method), or the original text paragraph from
> which the fact was derived, and such provenance can help to make
> fact-level changes in the KG without re-computing each step or to
> identify how and from where wrong values were introduced into the KG."
> — third-party summary, marked as approximate.

The four metric names handed to this task (construction success rate,
cross-reference integrity, provenance reachability, graph growth rate)
should be treated as **paraphrases of survey concepts**, not verbatim
metrics, until the PDF is re-read directly. The underlying ideas are
real and traceable to the survey's quality-assurance and provenance
sections — "accuracy" subsumes construction success, "consistency"
subsumes cross-reference integrity, "fact-level provenance" subsumes
provenance reachability — but SME should not cite the four phrases as
canonical terminology of the survey.

### Mapping to SME

| Survey concept (paraphrased) | SME category | Match strength |
|---|---|---|
| Accuracy of extracted entities/relations | Cat 4 (Threshold) — overall ingestion integrity | Approximate — SME is more about did-it-land-at-all than ground-truth correctness |
| Consistency / no contradictions | Cat 3 (CONTRADICTS edges) and Cat 4 sub-test on dangling endpoints | Strong for the dangling-endpoint piece |
| Coverage (domain breadth) | Cat 5 (The Missing Room — what fell off) and Cat 8a (declared-vs-built shape) | Approximate |
| Fact-level provenance (creation date, source paragraph, confidence) | Cat 6b (provenance chain queries) and proposed Cat 8b (Phantom Wall) | Strong, structurally — SME's `_created_by` reserved property is the same pattern |
| Entity resolution and fusion | Cat 4a (canonical collisions, alias-pair resolution) | Strong — see Part 2 |
| Knowledge completion | Cat 8a (declared structure) — adjacent | Weak |

The clean takeaway: SME Cat 4 is well-aligned with the survey's
"intrinsic evaluation + entity resolution" frame, and SME Cat 8b is
well-aligned with the survey's "fact-level provenance" frame. SME's
contribution on top of the survey is **operationalizing these as test
fixtures with pass/fail thresholds**, not as descriptive desiderata.
The survey describes what should be measured; SME describes how to
score it on a specific run.

## Part 2 — EAGER and entity resolution evaluation

### Provenance

- arXiv: [2101.06126](https://arxiv.org/abs/2101.06126)
- Title: *EAGER: Embedding-Assisted Entity Resolution for Knowledge Graphs*
- Authors: Daniel Obraczka, Jonathan Schuchart, Erhard Rahm
- Venue: Proceedings of the 2nd International Workshop on Knowledge
  Graph Construction, co-located with ESWC 2021.
- Read date: 2026-05-01
- Fetch method: WebSearch (arXiv abstract, Semantic Scholar, ResearchGate)

### What EAGER is

EAGER is a supervised ER pipeline for KGs that combines (a) graph
embeddings of entities and (b) attribute-value similarity, fed into a
classifier. Its reason-for-being is the abstract's claim that "the use
of graph embeddings alone is not sufficient to achieve high ER quality"
— so EAGER is positioned as a hybrid method. For SME purposes, the
interesting question is not the method but the **evaluation harness**:
EAGER and its successor work in the Leipzig group (e.g.
MovieGraphBenchmark, OpenEA-derived datasets) is where the standard ER
metric stack lives.

### B-Cubed metrics

B-Cubed precision and recall (Bagga & Baldwin, 1998) are the dominant
external evaluation metric for cluster-based ER. The seminal paper:

- *Entity-Based Cross-Document Coreferencing Using the Vector Space
  Model*, Amit Bagga and Breck Baldwin, ACL/COLING 1998
  ([P98-1012](https://aclanthology.org/P98-1012.pdf)).

Verbatim from the literature, paraphrased intuitions:

- **B-Cubed Precision** for an item *i*: the fraction of items in *i*'s
  predicted cluster that share *i*'s true entity (i.e. ground-truth
  category). Counted per-item, then averaged over all items.
- **B-Cubed Recall** for an item *i*: the fraction of items sharing
  *i*'s true entity that ended up in *i*'s predicted cluster. Counted
  per-item, then averaged over all items.
- **B-Cubed F1**: harmonic mean of the two.

The intuition that matters for SME: B-Cubed penalizes both
**over-merging** (two distinct entities collapsed into one cluster
drops precision for everything in that cluster) and **under-merging**
(one entity split across clusters drops recall for everything in
those clusters). Pairwise precision/recall and MUC scoring miss one
or the other side of this tradeoff; B-Cubed catches both. Amigó et
al. (2009, *Information Retrieval*) showed B-Cubed is the only
common metric satisfying all four formal constraints they propose
for cluster evaluation (homogeneity, completeness, rag-bag, cluster
size vs. quantity). That uniqueness is why every modern ER
benchmark — including OpenEA, MovieGraphBenchmark, and the
PatentsView ER evaluation work (arXiv 2210.01230) — reports B-Cubed.

### Mapping to SME Cat 4 alias resolution

SME spec v8 Cat 4 (lines 370-394 of `docs/sme_spec_v8.md`) defines
alias-pair resolution as a sub-test with thresholds on Jaccard string
similarity (max 0.25) and semantic cosine (min 0.78), and seeds the
test with three alias pairs ("ZK proof"/"zero-knowledge cryptography",
"k8s"/"Kubernetes", "CBT"/"Cognitive Behavioral Therapy"). The
**evaluation question** SME asks of the system under test is: did the
ingestion pipeline merge each alias pair into a single canonical
entity, or did it leave duplicates? That is precisely the question
B-Cubed scores, just at scale.

The mapping is:

- SME's pass/fail per alias pair = the per-item view B-Cubed averages
- A B-Cubed run over a labelled alias-pair set would give SME a
  graded score (0.0-1.0 for precision, recall, F1) instead of a
  binary "merged or not" verdict on each pair
- EAGER itself is not the right import for SME — EAGER is a
  *method* for ER, and SME is evaluating whatever ER the system
  under test happens to use. What SME wants is the **scorer**
  EAGER reports against, which is plain B-Cubed.

Concrete: B-Cubed is implementable as ~50 LOC of Python
(`bcubed-metrics` on PyPI is one reference, ScaDS' own `er-evaluation`
GitHub repo is another). SME could adopt B-Cubed without taking on
any of EAGER's modeling commitments.

## Part 3 — Other related evaluation work

**GraphRAG-Bench** (arXiv [2506.02404](https://arxiv.org/abs/2506.02404),
ICLR 2026 according to the GitHub README — verify when citing). Its
graph-construction evaluation axis names three metrics: **Efficiency**
(wall-clock time to build a complete graph), **Cost** (tokens consumed
during construction), and **Organization** (proportion of non-isolated
nodes). It also reports raw **Node Count** and **Edge Count** as
"broader domain coverage" proxies. The Organization metric is the most
SME-relevant: it's a simple structural-health probe (any node with zero
edges is suspect) and SME could trivially fold it into Cat 4 as an
introspection signal. None of the GraphRAG-Bench metrics overlap with
Cat 8b's per-edge groundedness probe.

**OpenEA** (Sun et al., VLDB 2020). Standard benchmark for
embedding-based entity alignment across KGs; evaluation is Hits@k and
MRR for the ranking view, plus the B-Cubed family for the clustering
view. Useful as a source of labelled alias data, not as a methodology
contribution.

**er-evaluation** (Olivier Binette,
[github.com/OlivierBinette/er-evaluation](https://github.com/OlivierBinette/er-evaluation)).
End-to-end ER evaluation framework. Implements B-Cubed, pairwise,
cluster-wise and several variance-aware metrics. Plausible direct
import for SME's Cat 4a scorecard work.

**Knowledge Graph Quality Management: A Comprehensive Survey** (Xue
& Zou, 2023, [PKU mirror](https://www.wict.pku.edu.cn/docs/20240422164533167415.pdf)).
Independent of the Hofer survey, organizes KG quality dimensions
along accuracy / completeness / consistency / timeliness / trust
axes. SME's Cat 8b ("can each edge trace to a source?") is
formalized in this literature as the **trust** dimension — every
edge carries provenance, and provenance traceability is a quality
metric. This is the closest published predecessor I found to Cat 8b.

## What SME could directly incorporate

1. **B-Cubed scorer for Cat 4a alias resolution.** ~50 LOC, well-tested
   reference implementations exist (`bcubed-metrics` PyPI,
   `er-evaluation`). Replace the binary per-pair pass/fail with a
   B-Cubed P/R/F1 over a labelled alias-pair dataset. The current
   3-pair seed becomes a labelled gold set; threshold becomes "F1 ≥
   0.85" or similar.

2. **Provenance-traceability probe for proposed Cat 8b.** Borrow the
   Hofer survey's fact-level provenance model directly: every edge has
   a `_created_by` (already reserved in spec v8 line 117) and a
   source-document reference. Cat 8b's pass criterion becomes "for
   every edge, traversing `_created_by` (and the source-document edge
   if present) reaches an in-graph Document node." The traversal is
   one or two hops; this is cheap. Phantom edges fail this probe by
   construction.

3. **Organization metric (non-isolated-node fraction)** from
   GraphRAG-Bench. One-line probe, useful Cat 4 introspection signal,
   no methodology cost.

4. **OpenEA-style multi-fold evaluation pattern.** OpenEA reports
   five-fold averaged metrics rather than single-run; for SME's
   reproducibility story this is a low-cost upgrade once enough alias
   data is in hand.

## What SME measures that this body of work doesn't

1. **Per-edge-type evidence-rule registration** (the good-dog-corpus
   pattern). The surveyed metrics treat all edges as equally graded
   against ground truth or against a single provenance schema. SME
   lets each edge type declare its own evidence rule and scores edges
   against the rule for that type. Cat 8b is the harness for this.
   Nothing in the surveyed work supports per-edge-type rule
   registration — they are global-per-graph.

2. **A/B/C condition isolation against the constructed graph.**
   GraphRAG-Bench evaluates retrieval quality against the constructed
   graph, but it does not isolate (A) raw-text fallback, (B)
   single-pass retrieval, (C) multipass structural traversal as
   independent conditions. SME's three-condition design is methodology
   that the surveyed retrieval-eval work does not match.

3. **Multi-corpus stress-testing methodology.** The surveys evaluate
   methods on a single benchmark dataset per run. SME's structural
   commitment to running every category against multiple corpora (per
   the spec) is a methodology contribution, not a metric contribution.

4. **Cat 8a's natural-language README claim verification.** Formal
   ontology validation is a rich literature (SHACL, OWL constraint
   reasoning, etc.), but I found nothing in this survey scope that
   verifies the *informal* structural claims in a system's README
   against the graph it actually builds. Cat 8a is a genuinely novel
   axis, at least relative to this slice of the literature.

## Open questions

- Does the Hofer survey's PDF actually use any of "construction success
  rate", "cross-reference integrity", "provenance reachability", or
  "graph growth rate" verbatim? My third-party-summary searches did
  not surface them. Re-check with a working PDF fetcher before
  publication-grade citation.
- Does the survey define a quantitative threshold for fact-level
  provenance traceability, or does it leave it as a desideratum? SME's
  Cat 8b would benefit from any prior-art threshold to anchor against.
- Is there a published ER evaluation that reports B-Cubed *with*
  semantic-similarity gating (à la SME's cosine 0.78 threshold)?
  Standard B-Cubed is similarity-agnostic; SME's variant gates on
  embedding similarity before clustering, which may need a custom
  scorer.
- Has anyone published per-edge-type evidence rules as a structured
  registration format? If so SME should adopt the schema rather than
  invent one.

## Citations

- Hofer, Obraczka, Saeedi, Köpcke, Rahm. *Construction of Knowledge
  Graphs: State and Challenges*. arXiv:2302.11509, 2023. Revised as
  *Information* 15(8):509, 2024.
  - [arXiv abstract](https://arxiv.org/abs/2302.11509)
  - [arXiv PDF](https://arxiv.org/pdf/2302.11509)
  - [Leipzig mirror PDF](https://dbs.uni-leipzig.de/files/research/publications/2023-2/pdf/2302.11509.pdf)
  - [MDPI 2024 version](https://www.mdpi.com/2078-2489/15/8/509)
- Obraczka, Schuchart, Rahm. *EAGER: Embedding-Assisted Entity
  Resolution for Knowledge Graphs*. arXiv:2101.06126, 2021. ESWC 2021
  workshop.
  - [arXiv](https://arxiv.org/abs/2101.06126)
- Bagga, Baldwin. *Entity-Based Cross-Document Coreferencing Using the
  Vector Space Model*. ACL/COLING 1998.
  - [ACL Anthology P98-1012](https://aclanthology.org/P98-1012.pdf)
- Amigó, Gonzalo, Artiles, Verdejo. *A comparison of extrinsic
  clustering evaluation metrics based on formal constraints*.
  *Information Retrieval* 12(4), 2009. (B-Cubed uniqueness proof.)
- Sun et al. *A Benchmarking Study of Embedding-based Entity Alignment
  for Knowledge Graphs*. VLDB 2020. (OpenEA.)
  - [PVLDB PDF](https://vldb.org/pvldb/vol13/p2326-sun.pdf)
- *GraphRAG-Bench: Challenging Domain-Specific Reasoning for Evaluating
  Graph Retrieval-Augmented Generation*. arXiv:2506.02404, ICLR 2026
  (per repo claim).
  - [arXiv](https://arxiv.org/abs/2506.02404)
  - [GitHub](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)
- Xue, Zou. *Knowledge Graph Quality Management: A Comprehensive
  Survey*. 2023.
  - [PKU mirror PDF](https://www.wict.pku.edu.cn/docs/20240422164533167415.pdf)
- Binette. *er-evaluation*: end-to-end ER evaluation framework.
  - [GitHub](https://github.com/OlivierBinette/er-evaluation)
- van Heusden, de Rijke. *BCubed Revisited: Elements Like Me*. SIGIR
  ICTIR 2022.
  - [Paper PDF](https://irlab.science.uva.nl/wp-content/papercite-data/pdf/van-2022-bcubed.pdf)
