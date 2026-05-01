# good-dog-corpus

A real-world evaluation corpus for structural memory systems, built ontology-first as a worked example of KG schema design, ingestion, and testing. Sources are public dog-related content across veterinary research, municipal policy, breed standards, and community journalism.

---

## What this is for

Every memory system — vector store, knowledge graph, hybrid retriever, structural palace — encodes assumptions about what kind of questions it expects to answer. Those assumptions are usually invisible until a corpus stress-tests them. **good-dog-corpus is a deliberately-shaped corpus designed to surface those assumptions** when run through the [SME (multipass-structural-memory-eval)](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval) framework.

It exists for three reasons:

1. **As a non-technical evaluation corpus.** Most memory benchmarks (LongMemEval, LoCoMo, GraphRAG-Bench) use tech-domain content — auth migrations, deployment decisions, API configurations. Tech corpora are convenient for engineers but exclude evaluators who don't read distributed systems. Dogs are a domain everyone has intuition about, with the same structural properties a memory eval needs.

2. **As a worked example of ontology-first KG design.** The schema in `ontology.yaml` ships with the design narrative (`ONTOLOGY.md`) that explains every entity-type and edge-type decision, including alternatives that were rejected. The corpus exists to materialize that ontology, so the relationship between schema decisions and downstream retrieval behavior becomes observable.

3. **As a feedback loop between ingestion failures and SME readings.** The kg-ingestion pipeline has a published catalogue of failure modes (hallucinated edges, entity fragmentation, fabricated descriptions). Most of those failures, when they happen, *surface as specific SME category readings downstream* — phantom edges as Cat 10, alias collapse as Cat 4, fabricated entities as Cat 8 ontology violations. This corpus is the first one designed so that each upstream failure has a corresponding downstream test, and the connection is documented.

The corpus is **backend-agnostic.** Files are markdown plus YAML. Anyone can ingest it into LadybugDB, RyuGraph, ChromaDB, Neo4j, Postgres+pgvector, or NetworkX. The reference ingestion pipeline is documented in `INGESTION.md`, but using it is optional.

---

## How it flows (end-to-end)

```
              ┌──────────────────┐
              │   ontology.yaml  │  ← the schema (8 entity types, 11 edge types,
              │                  │     evidence rules per edge)
              └────────┬─────────┘
                       │
       guides          │          guides
   ┌────────────┐  ┌───┴────┐  ┌─────────────┐
   │  source    │  │ vault/ │  │  questions  │
   │ selection  │→ │ *.md   │← │   .yaml     │
   │            │  │        │  │             │
   └────────────┘  └───┬────┘  └─────────────┘
                       │
                       │  ingestion (12-stage kg-ingestion pipeline,
                       │   reference impl in INGESTION.md)
                       ▼
              ┌──────────────────┐
              │  Knowledge graph │  (LadybugDB / NetworkX / any backend)
              │                  │
              └────────┬─────────┘
                       │
                       │  SME categories run against the graph
                       ▼
   ┌─────────────────────────────────────────────────┐
   │  Cat 1  factual retrieval                       │
   │  Cat 2c multi-hop                               │
   │  Cat 3  contradiction detection                 │
   │  Cat 4  ingestion integrity / alias resolution  │
   │  Cat 6  temporal supersession                   │
   │  Cat 8  ontology coherence (declared-vs-built)  │
   │  Cat 10 phantom edges (graph-vs-source)         │
   └─────────────────────────────────────────────────┘
```

The ontology shapes every step:

- **Source selection.** The seeded contradiction pairs (`grain-free DCM 2018→2022`, `dominance theory→AVSAB 2009`), alias chains (`GSD/Alsatian/German Shepherd`, `Pit Bull/APBT`), and temporal chains (recall lifecycles) tell us which public sources to find. Without the ontology, source selection is "anything dog-related"; with it, the search is targeted.
- **Vault structure.** The six domain directories (`veterinary_research/`, `municipal_policy/`, ...) match the ontology's natural source-types. A `breed` entity is most naturally documented from `breed_standards/`; a `concept` like dominance theory from `behavioral_research/`.
- **Chunking.** The ontology defines what a node looks like, which constrains what a useful chunk looks like. A note discussing one paper, one event, or one breed becomes one entity-anchored chunk; cross-domain articles get split per subject.
- **Edge extraction.** Each edge type's `evidence_rule` in `ontology.yaml` tells the ingestion pipeline what to look for in source text — explicit temporal markers for `supersedes`, byline matches for `authored_by`, claim-pair detection for `contradicts`.
- **Question annotation.** Every question in `questions.yaml` is annotated against the ontology — expected hop chains use registered edge types, contradiction questions point at registered `contradicts` pairs, alias questions use entries in `ontology.yaml#aliases`. This is what makes the corpus testable, not just readable.

---

## Read in this order

1. **[ONTOLOGY.md](ONTOLOGY.md)** — research-process narrative. How the schema got picked, what got rejected, what's out of scope. **Load-bearing artifact.** The corpus exists to materialize the ontology, not the other way around.
2. **[ontology.yaml](ontology.yaml)** — the schema itself. Entity types, edge types, evidence rules, alias registry, scope boundaries, SME category coverage map.
3. **[INGESTION.md](INGESTION.md)** — reference ingestion pipeline + failure-mode catalogue. *Forthcoming.*
4. **`vault/`** — source-summarized notes with frontmatter attribution, organized by source domain.
5. **`questions.yaml`** — annotated ground truth, each question bound to the ontology.
6. **`validate.py`** — corpus self-check (NetworkX-based). Runs every consistency check before merge. *Forthcoming.*

---

## Corpus shape

Six source domains, all public:

| Domain | Source types | What it tests |
|---|---|---|
| Veterinary research | PubMed abstracts, journal summaries | Contradictions (grain-free debate), temporal evolution (protocol changes) |
| Municipal policy | Bylaws, shelter reports, council minutes | Cross-domain hops (policy → enforcement → community impact) |
| Breed standards | Kennel club documents, registry records | Alias pairs (GSD / German Shepherd / Alsatian), canonicalization |
| Nutrition & safety | FDA recall notices, feeding guidelines | Temporal chains (recall announced → investigated → resolved) |
| Behavioral research | Study summaries, training methodology | Contradictions (dominance theory vs positive reinforcement) |
| Community journalism | Local reporting, park coverage, adoption stories | Unstructured real-world content, multi-topic overlap |

---

## How SME categories use this corpus

The ontology's `sme_category_coverage` section maps schema elements to categories. Summary view:

| Category | What it reads | Representative scenario |
|---|---|---|
| **Cat 1** factual retrieval | `mentions`, `subject_of` | "What recalls happened to brand X in 2023?" |
| **Cat 2c** multi-hop | `authored_by`, `affiliated_with`, `cites`, `subject_of` | Vet author → affiliation → studies cited in council policy |
| **Cat 3** contradiction | `contradicts` | Grain-free DCM (2018 finding → 2022 reassessment) |
| **Cat 4** alias resolution | `alias_of` | Does the system collapse "GSD" / "German Shepherd" / "Alsatian"? |
| **Cat 6** temporal | `supersedes` | Pet food recall lifecycle: announced → investigated → resolved |
| **Cat 8** ontology coherence | the entire schema vs the built graph | Did the system build the graph it said it would? |
| **Cat 10** phantom edges | `evidence_rule` on every edge type | Are all asserted edges grounded in source content? |

Each category reads a specific subset of the schema. A system that shines on Cat 1 but stalls on Cat 3 is telling you something the single-aggregate-recall benchmarks can't.

---

## Design principles

- **Ontology-first.** Schema and its rationale ship with the corpus, not after. The teaching artifact is the design narrative.
- **No synthetic data ever.** Every fact in the corpus traces to a public source cited in the note frontmatter. Notes can be hand-authored summaries, agent-drafted summaries, or pipeline-generated drafts — the form doesn't matter. **What matters is that no fact in the corpus is invented.** Maintainer validates before merge.
- **Multiple corpus shapes from one domain.** The same dog content produces clean entity-per-file notes (breed profiles), messy cross-topic notes (news articles), and structured research summaries. Three retrieval challenge levels from one domain.
- **Naturally occurring defects.** Contradictions, alias collisions, and temporal supersession exist in the source material. They aren't seeded — they're found and annotated.
- **Annotated ground truth.** Each question includes expected sources, hop depth, contradiction pairs where relevant, and temporal validity windows. Annotations are hand-verified against source documents *and* against the declared ontology.
- **Per-edge-type evidence rules.** Every edge type in `ontology.yaml` registers an evidence rule — first worked example for the phantom-edge category proposed in [SME #4](https://github.com/M0nkeyFl0wer/multipass-structural-memory-eval/issues/4).
- **Backend-agnostic.** Markdown + YAML. Reference ingestion pipeline is documented but not required. Anyone can run the corpus through any stack.

---

## Tooling

The corpus itself is plain text. The reference tooling around it:

- **Schema validation** — `ontology.py` (forthcoming) provides the executable form of `ontology.yaml` per [kg-ingestion](https://github.com/M0nkeyFl0wer) best practices: `NODE_TYPES`, `EDGE_TYPES`, `EDGE_DOMAIN_RANGE`, `validate_edge()`, etc.
- **Corpus self-check** — `validate.py` (forthcoming) uses NetworkX to verify alias chains close, edges satisfy their evidence rules, hop chains are traversable, and contradiction pairs are bidirectional.
- **Reference ingestion** — `INGESTION.md` (forthcoming) documents the 12-stage kg-ingestion pipeline applied to good-dog-corpus, with worked failure-mode examples mapped to SME category readings.
- **Analytics** — NetworkX is the in-corpus default for analytics (centrality, communities, bridges) since the graph is small. LadybugDB is the production backend for anyone running this at scale.

---

## Current state

🐕 **Foundation stage.** Ontology drafted, content accumulating. Contributions welcome.

- [x] Ontology design (ONTOLOGY.md + ontology.yaml)
- [x] README with end-to-end plan
- [ ] Executable ontology (`ontology.py`)
- [ ] Source-discovery pass per domain (URLs, dates, license-status)
- [ ] 10 veterinary research notes with 2 contradiction pairs
- [ ] 8 breed standard notes with 4 alias pairs
- [ ] 5 municipal policy notes
- [ ] 5 nutrition & safety notes (recall lifecycle chains)
- [ ] 5 behavioral research notes (training methodology evolution)
- [ ] 5 community journalism notes
- [ ] 12 annotated questions at 1/2/3 hop depths
- [ ] Ground truth YAML with expected sources per question
- [ ] `validate.py` corpus self-check
- [ ] `INGESTION.md` reference pipeline + failure-mode catalogue
- [ ] First end-to-end run: ingest corpus → build graph → SME categories report

---

## Relationship to standard_v0_1

`standard_v0_1` is the hand-authored tech-focused corpus contracted in AUTHORING.md. `good-dog-corpus` is a second corpus shape — non-technical, real-world, content-engine-sourced, ontology-first. The multi-corpus methodology requires both: tech corpus for one failure profile, dog corpus for another. Between them they cover the "single corpus gives misleading conclusions" finding from the three-corpus benchmark.

---

## License

All source material is from public domain or openly licensed sources. Specific attributions in each note's frontmatter (`source_url`, `source_date`, `license`, `accessed_on`).
