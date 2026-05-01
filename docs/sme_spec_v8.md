# Structural Memory Evaluation (SME) Framework — v8

> **Version note.** Originally `sme_spec_v5.md`; content level matches v8
> (Category 8 ontology coherence, multi-hop 2c sub-test, introspection/external
> splits on Categories 4/5/8, operationalized claim library, use-case profiles,
> snapshot views, live DB lock handling, Category 7 three-condition requirement).
> Renamed 2026-04-10 so downstream docs (ideas.md, MemPalace PR build kit,
> structural_claims.yaml) reference the same filename.
>
> **2026-04-11 addendum.** Each category now carries a descriptive name
> with a spatial subtitle that nods to MemPalace's metaphor: The Lookup (1),
> The Crossing / The Registry / The Stairway (2, 2b, 2c), The Dissonance (3),
> The Threshold (4), The Missing Room (5), The Archive (6), The Abacus (7),
> The Blueprint (8). The names are for external writing and docs. Internal
> category numbers and CLI slugs are unchanged to avoid breaking config.

**One question: what should a memory system know about its own structure, and how do you test whether it does?**

Standard benchmarks (LongMemEval, LoCoMo, EverMemBench) test: "can you find a memory?" That's necessary but not sufficient. A filing cabinet can find a memory. The question is what the structure gives you beyond retrieval.

SME adds six structural categories on top of factual retrieval, plus a graph-vs-no-graph baseline and an ontology coherence layer that measures whether the system's schema matches its claims. Eight categories total. No system will score 90%+ across all eight today. The framework reveals where each architecture excels and where it doesn't.

---

## Prior Art and Positioning

The memory evaluation landscape has matured rapidly since 2024. SME builds on — and explicitly extends beyond — the following open benchmarks and evaluation methodologies:

### Retrieval and QA Benchmarks

**LongMemEval** (Wu et al., ICLR 2025) — 500 curated questions testing five core memory abilities: information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention. Publicly available (GitHub, HuggingFace, MIT license). The de facto standard — Zep, MemPalace, ENGRAM, EverMemOS, Mem0, and Emergence AI all benchmark against it. Key finding: even with perfect retrieval, reading accuracy is non-trivial; structured JSON + Chain-of-Note improves reading by up to 10 points. SME adopts LongMemEval's judge methodology (GPT-4o, >97% human agreement) for Category 1.

**LoCoMo** (Maharana et al., 2024) — earlier longitudinal conversation memory benchmark. Insufficient for modern models due to limited context size and lack of knowledge update testing. Retained as a secondary baseline for breadth comparisons.

**EverMemBench** (Hu et al., Feb 2026) — tests multi-party dialogue failures that LongMemEval misses: confusion about who said what, interference across related topics, inability to update beliefs when plans change. Open source.

**MemoryAgentBench** (Hu et al., ICLR 2026) — evaluates memory via incremental multi-turn interactions. Open source (GitHub + HuggingFace).

### Knowledge Graph Quality Benchmarks

**KGGen MINE** (Stanford, NeurIPS 2025) — first benchmark for text-to-KG extraction quality. MINE-1 measures extraction fidelity (does the KG capture 15 ground-truth facts per article?). MINE-2 measures downstream usefulness (does the KG improve QA via WikiQA?). KGGen outperforms OpenIE and GraphRAG by up to 18%. Open source (`pip install kg-gen`, MIT license). SME uses MINE's extraction fidelity methodology to validate the seeded corpus.

**GraphRAG-Bench** (Xiang et al., ICLR 2026) — comprehensive benchmark evaluating nine GraphRAG methods across fact retrieval, complex reasoning, summarization, and creative generation. Tests the full pipeline: graph construction → knowledge retrieval → answer generation. Open source (GitHub + HuggingFace). SME borrows the pipeline-wide evaluation approach.

**Microsoft BenchmarkQED** — open-source toolkit for benchmarking RAG systems. AutoQ synthesizes queries across a local-to-global spectrum. AutoE evaluates via LLM-as-judge pairwise comparisons. SME can adopt AutoQ's query synthesis for generating diverse test queries at scale.

**Structural Quality Metrics** (Semantic Web Journal) — six structural quality metrics applied to Wikidata, DBpedia, YAGO, Freebase, and Google KG. Measures ontology expressiveness and property usage. Intrinsic structural quality, not retrieval performance.

**KG Quality Management Survey** (IEEE TKDE 2023) — comprehensive survey covering quality assessment, problem discovery (finding inherent wrong assertions and deriving error patterns), and quality improvement. Notable: KGist system uses compression-based anomaly detection to find graph errors.

### Industrial Memory Systems and Their Evaluation Gaps

**Zep/Graphiti** — temporal knowledge graph engine. 94.8% on DMR, up to 18.5% accuracy improvement on LongMemEval, 90% latency reduction. Reports token savings (< 2% of baseline tokens) as a marketing metric, not a formal benchmark. No structural graph quality metrics. No ingestion integrity testing. Graphiti is open source.

**ENGRAM** (Patel et al., Nov 2025) — typed memory with minimal routing. Claims SOTA on LoCoMo, surpasses full-context baselines on LongMemEval. Reduces input token budget by 95.5%, reasoning tokens by 77.8%. No structural evaluation. Open source.

**EverMemOS** — engram-inspired three-phase memory (episodic, semantic, reconstructive). 83.0% accuracy on LoCoMo, 82% on LongMemEval-S. Bio-inspired architecture. No graph quality metrics. Open source.

**LiCoMemory** (Huang et al., Nov 2025) — outperforms Mem0, Zep, A-Mem, LoCoMo-RAG. 73.8% accuracy on LongMemEval with 10-40% latency reduction. Largest gains in multi-session (+26.6pp) and temporal (+15.9pp).

### Topological Data Analysis in Graph Contexts

Persistent homology is extensively applied in molecular science, protein structure, materials science, and graph neural networks. Localized persistent homology has been used for graph classification and node-level representation learning. However, **no published work applies TDA to knowledge graph quality evaluation** — using Betti numbers, persistence diagrams, or structural diffs to detect ingestion damage, gap detection, or monoculture in knowledge graphs. This is SME's novel contribution.

### What SME Uniquely Tests

| SME Category | Tested by existing benchmarks? | Notes |
|---|---|---|
| 1. Factual Retrieval | Yes (LongMemEval, LoCoMo, DMR) | Table stakes. SME adopts existing methodology. |
| 2. Cross-Domain Discovery | Partially (LongMemEval multi-session) | LongMemEval tests multi-session reasoning but not canonicalization-dependent discovery. No benchmark distinguishes "traversal failed" from "entity resolution failed." |
| 3. Contradiction Detection | Partially (LongMemEval knowledge-update) | LongMemEval tests whether the system returns updated facts, not whether it explicitly flags contradictions. |
| 4. Ingestion Integrity | **No** | No benchmark tests whether a system detects its own pipeline corruption. MINE tests extraction quality from the outside. SME tests it from the inside. Completely novel. |
| 5. Gap Detection | **No** | No benchmark tests proactive discovery of structural gaps. Topology-driven gap detection via persistent homology is unique to SME. |
| 6. Temporal Reasoning | Partially (LongMemEval temporal) | LongMemEval tests time-point queries. SME adds provenance chain integrity — tracking which enrichment process produced an edge and whether it was superseded. |
| 7. Token Efficiency | **No (as formal benchmark)** | Zep reports token savings as a side metric. GraphRAG-Bench compares GraphRAG methods. No benchmark formalizes tokens-per-correct-answer with same corpus/LLM/judge across flat vs. graph vs. graph+topology. |
| 8. Ontology Coherence | **No** | Palantir tests ontology operationally (simulation, branching, evals) but not structurally. No benchmark tests whether a system's actual graph matches its declared or implied ontology. Semantic Web Journal structural metrics are closest but measure static KGs, not live memory systems. |

### What SME Borrows

- LongMemEval's GPT-4o judge methodology (>97% human agreement) → Category 1
- MINE's extraction fidelity methodology → corpus calibration
- GraphRAG-Bench's pipeline-wide evaluation (construction → retrieval → generation) → all categories
- BenchmarkQED's AutoQ query synthesis → test query generation at scale
- Structural quality metrics from Semantic Web Journal → ontology coherence in calibration
- KGist's compression-based anomaly detection concept → Category 4 inspiration

---

## Architecture: Plug-and-Play Adapter System

SME ships as a Python package (`sme-eval`) with a backend adapter interface. The test suite never touches a database directly — it talks to a thin adapter layer that each system implements. Same seeded corpus, same queries, same scoring runs against any backend without modifying the benchmark.

No existing benchmark offers this. LongMemEval is dataset-specific. GraphRAG-Bench is method-specific. MINE is extraction-specific. SME is architecture-agnostic by design.

### Adapter Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

@dataclass
class Entity:
    id: str
    name: str
    entity_type: str
    properties: dict = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None  # shape (768,) or similar

@dataclass
class Edge:
    source_id: str
    target_id: str
    edge_type: str
    properties: dict = field(default_factory=dict)
    # Reserved property keys for Cat 6b provenance:
    #   _created_by: str    — extraction pattern or process that created this edge
    #   _created_at: str    — ISO timestamp
    #   _superseded_by: str — edge ID that replaced this one (if applicable)

@dataclass
class ContradictionPair:
    """Optional structured response for Cat 3. Systems that don't
    surface contradictions leave this empty and score 0."""
    claim_a: str
    claim_b: str
    source_a: str  # entity/session ID
    source_b: str

@dataclass
class QueryResult:
    answer: str
    context_string: str             # the actual text injected into the LLM prompt —
                                    # SME tokenizes this itself (tiktoken, cl100k_base)
                                    # to compute Cat 7 metrics. Adapters can't game it.
    retrieved_entities: list[Entity] = field(default_factory=list)
    retrieved_edges: list[Edge] = field(default_factory=list)
    retrieval_path: list = field(default_factory=list)
    contradictions: list[ContradictionPair] = field(default_factory=list)
    error: Optional[str] = None     # if query() fails, set this instead of raising.
                                    # SME distinguishes "errored" from "answered wrong."

class SMEAdapter(ABC):
    """Implement this for your database/memory system.
    Three required methods. Two optional."""

    @abstractmethod
    def ingest_corpus(self, corpus: list[dict]) -> dict:
        """Load the seeded test corpus.
        Returns: {'entities_created': int, 'edges_created': int,
                  'errors': list[str], 'warnings': list[str]}"""
        ...

    @abstractmethod
    def query(self, question: str) -> QueryResult:
        """Run a natural language query through the full pipeline.
        Must populate context_string with the exact text sent to the LLM."""
        ...

    @abstractmethod
    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """Return full graph state for topology analysis."""
        ...

    # --- Optional methods (have sensible defaults) ---

    def get_flat_retrieval(self, question: str) -> QueryResult:
        """Vector-only retrieval with no graph traversal.
        Used as Cat 7 Condition A. If not implemented,
        SME uses its built-in FlatBaseline adapter."""
        raise NotImplementedError

    def get_ontology_source(self) -> dict:
        """Return ontology documentation for Category 8.
        Returns: {'type': 'declared'|'readme'|'inferred',
                  'schema': [...], 'documentation': str}"""
        return {'type': 'inferred', 'schema': [], 'documentation': ''}
```

Three required methods. That's the minimum viable adapter. `get_flat_retrieval` and `get_ontology_source` have defaults — SME fills in its own flat baseline and infers ontology from the graph if the adapter doesn't provide them.

### Default Adapters

```
sme/adapters/
  ├── flat_baseline.py   # Vector-only (numpy cosine sim, no dependencies)
  ├── sqlite_triples.py  # SQLite triples + ChromaDB/sqlite-vec
  ├── neo4j.py           # Neo4j via Bolt protocol
  ├── ladybugdb.py       # LadybugDB (embedded graph + native vectors)
  └── custom.py          # Template for implementing your own
```

| Adapter | Architecture | Who uses this pattern |
|---|---|---|
| `flat_baseline` | Embeddings only, no graph | Most RAG systems, vanilla LangChain |
| `sqlite_triples` | SQLite (subject, predicate, object) + separate vector store | MemPalace, many Obsidian-based tools |
| `neo4j` | Server graph DB with Cypher | Graphiti/Zep, enterprise KG systems |
| `ladybugdb` | Embedded graph DB with native vectors, Cypher, no server | personal KG systems, knowledge-corpus graphs |

### Graph Snapshot Views

A single graph has multiple legitimate structural interpretations depending on which edges and nodes you include. SME makes this explicit: adapters expose two standard snapshot views, and each category is specified to run against one or the other. Without this discipline, findings are ambiguous — the same graph looks healthy or sparse depending on what you count.

**Two standard views:**

- **`full_snapshot`** — every node table and every non-empty edge table, minus operational infrastructure (logs, caches, lifecycle events). Includes document-mention edges, chunk-of edges, tag edges, etc. Use for categories that measure retrieval performance end-to-end.

- **`semantic_snapshot`** — only the knowledge-layer nodes and edges. Typically: the Entity table plus the semantic-relationship edges that connect entities to each other. Excludes document↔entity mention edges, chunk↔note edges, tag edges, and similar infrastructure. Use for categories that measure the quality of the knowledge layer itself.

**Why this matters:** KNOWLEDGE_CORPUS-template graphs (notes indexing concepts) show dense connectivity in `full_snapshot` because document-mention edges connect everything, and sparse connectivity in `semantic_snapshot` because the entity-to-entity layer is what enrichment actually produces. Both views are correct. The `full_snapshot` answers "can retrieval reach this entity?" The `semantic_snapshot` answers "does the knowledge layer know how this entity relates to other entities?" SME categories need to commit to one view per category so results are comparable.

**Category assignments:**

| Category | View | Reason |
|---|---|---|
| 1 Factual Retrieval | full_snapshot | Retrieval uses every available edge to reach the answer |
| 2 Cross-Domain Discovery | semantic_snapshot | Cross-domain means cross-topic in the knowledge layer, not cross-document |
| 3 Contradiction Detection | semantic_snapshot | Contradictions are semantic claims, not mention frequencies |
| 4 Ingestion Integrity | both — report separately | 4c monoculture runs on both (the RELATED-in-semantic case and the MENTIONS-in-full case are both real failure modes) |
| 5 Gap Detection | semantic_snapshot | Structural holes in the knowledge layer are what Cat 5 finds; document-mention edges mask them |
| 6 Temporal Reasoning | full_snapshot | Temporal queries can traverse any edge, including document citations |
| 7 Token Efficiency | full_snapshot | Retrieval is run on the full graph — this is what the system actually does at query time |
| 8 Ontology Coherence | both — report separately | Declared schema tested against both views; drift is usually visible in full, while semantic-layer vocabulary balance is visible in the semantic view |

**Empirical basis:** Measured on three LadybugDB graphs on 2026-04-10:

- **Personal KG** (KNOWLEDGE_CORPUS template): semantic view shows 69% entity isolation, full view shows 0.03% isolation. Same graph.
- **Hybrid KG** (semantic + document layer): semantic view edge-type entropy 2.30 bits (concentrated), full view entropy 0.91 bits (MENTIONED_IN monoculture at 86%). Same graph.
- **Biographical KG** (NARRATIVE_GRAPH template): both views converge because the schema has no separate document-mention layer — all edges are semantic by construction. 4.5% isolation either way.

**Adapter implementation:** Adapters that expose both views SHOULD implement `get_graph_snapshot(view: Literal["full", "semantic"])`. Adapters that only have one view (narrative graphs, flat stores) MAY return the same data for both and set a `views_are_equivalent` flag in the returned metadata. The topology layer consumes snapshots without caring how they were produced.

### Handling Live DB Locks

Many embedded graph databases (LadybugDB among them) take a single-writer file lock on the database file. When a benchmark target has a running daemon, API server, or enrichment process, a second process cannot open the same file even in read-only mode. This is a **known operational constraint**, not a benchmark bug.

SME provides two paths around it:

1. **`sme-eval snapshot --db-path PATH --output SNAPSHOT`** — copies the database file (and any sibling WAL / shadow files) to a specified output location, preserving any on-disk consistency guarantees the target DB provides. Produces a point-in-time backup suitable for benchmarking. Call this before `sme-eval run` when the target is in active use.

2. **API-based adapters** — where the system under test exposes an HTTP search API, an adapter can read through the API rather than opening the file directly. Higher fidelity (reads the current live state) but requires the target's API to expose graph introspection endpoints.

The reference LadybugDB adapter opens with `read_only=True` by default but will surface a clear error if the writer lock blocks access, pointing the user to `sme-eval snapshot`.

### Built-in Flat Baseline

For systems without a separable flat retrieval path, SME ships a default flat adapter using the same corpus and embedding model (defaults to nomic-embed-text). Pure top-K cosine similarity. This ensures every system gets a fair Category 7 comparison.

### Obsidian / Markdown as Source Format

Many personal knowledge systems are built on Obsidian vaults or plain markdown. The seeded corpus ships in two formats:

1. **YAML** (`standard_v1.yaml`) — structured ground truth for programmatic evaluation
2. **Obsidian vault** (`standard_v1_vault/`) — markdown files with wikilinks, frontmatter, tags, folder structure

File-based systems ingest the benchmark through their actual pipeline (file watcher → extraction → enrichment) rather than a synthetic loader.

```
sme/corpora/
  ├── standard_v1.yaml
  ├── standard_v1_vault/
  │   ├── auth_engineering/
  │   │   ├── oauth-token-refresh.md
  │   │   ├── clerk-auth-decision.md
  │   │   └── auth0-migration.md
  │   ├── privacy_research/
  │   │   ├── zk-proof-overview.md
  │   │   └── zero-knowledge-cryptography.md
  │   ├── temporal/
  │   │   ├── session-005-postgresql.md
  │   │   ├── session-023-sqlite-migration.md
  │   │   └── session-041-back-to-postgresql.md
  │   └── injected_defects/
  │       ├── boilerplate-evidence-notes/
  │       ├── misattributed-evidence/
  │       └── ghost-entities/
  └── ground_truth.yaml
```

### Expected Scorecard by Architecture (predictions to be falsified)

These are predictions based on architectural analysis, not findings. Real results may differ. The benchmark exists to test these predictions, not confirm them.

**Palace-structure systems (MemPalace pattern):**
- Architecture: SQLite triples `(subject, predicate, object, valid_from, valid_to)` + ChromaDB vectors. Fixed ontology — Wings (person, project, concept), Halls (facts, events, discoveries, preferences, advice), Rooms (topic instances), Tunnels (cross-wing links).
- Ontology is spatial (where things are filed) not semantic (how things relate).
- Expected strengths: Category 1 (34% retrieval boost from wing+room filtering), Category 6 (temporal — native `valid_from`/`valid_to`), Category 3 (entity-level contradiction via temporal invalidation).
- Expected weaknesses: Category 2 (tunnels are manually declared, no semantic canonicalization), Category 4 (no pipeline self-monitoring), Category 5 (no topology).

**Typed graph systems (knowledge-corpus pattern):**
- Architecture: LadybugDB (or equivalent embedded graph DB) with typed edge tables, native FLOAT[768] vectors, Cypher queries. Semantic ontology — edge types encode relationship meaning. Maturation lifecycle tracks extraction pattern quality. Nightly topology (NetworkX + Ripser).
- Expected strengths: Category 4 (lifecycle evaluator, monoculture monitoring, runaway pattern detection), Category 5 (persistent homology), Category 2 (typed edge traversal + canonical entity resolution), Category 7 (structured retrieval).
- Expected weaknesses: Category 6b (provenance chain queries are expensive), Category 3 (CONTRADICTS edges exist but aren't systematically generated).

**Server graph systems (Neo4j/Graphiti pattern):**
- Architecture: Neo4j via Bolt, often with separate vector index. Concurrent writes, production-grade.
- Expected strengths: Category 1 (mature hybrid search), Category 2 (battle-tested Cypher path queries), Category 7c (scales to millions of entities).
- Expected weaknesses: Category 4 (most deployments lack lifecycle monitoring), Category 5 (no topology unless explicitly added).

**Flat systems (vanilla RAG):**
- Architecture: Vector store only. Top-K cosine similarity.
- Expected strengths: Category 1 (optimized for exactly this).
- Expected weaknesses: Categories 2-6 (no structural capabilities). Category 7 control group.

---

## Topology Layer

Backend-agnostic module operating on `get_graph_snapshot()` output. Converts any adapter's graph to NetworkX and runs analysis.

```python
from sme.topology import TopologyAnalyzer

class TopologyAnalyzer:

    def __init__(self, entities: list[Entity], edges: list[Edge]):
        self.G = self._build_networkx(entities, edges)

    def betti_numbers(self, max_dim: int = 2,
                      filtration: str = "confidence") -> dict:
        """Persistent homology via Ripser.
        Filtration: 'confidence', 'temporal', 'edge_type_weight'.
        Returns Betti numbers and persistence diagrams."""
        ...

    def community_structure(self, method: str = "louvain") -> dict:
        """Community detection. Returns communities, modularity,
        inter-community edge density."""
        ...

    def structural_health(self) -> dict:
        """Quick diagnostic: connected_components, largest_component_ratio,
        edge_type_distribution, isolated_node_count,
        avg_clustering_coefficient, degree_distribution_entropy."""
        ...

    def diff(self, other: 'TopologyAnalyzer') -> dict:
        """Compare two snapshots. Returns H0 delta, H1 delta,
        community membership changes, edge type ratio shift.
        Used by Category 4 for ingestion damage detection."""
        ...

    def filtered_subgraph(self, edge_types: list[str]) -> 'TopologyAnalyzer':
        """Subgraph with specified edge types only.
        Used by Category 4c for monoculture detection."""
        ...

    def centrality_retrieval(self, query_entities: list[str],
                              hops: int = 2, top_k: int = 20) -> list[Entity]:
        """Retrieve by graph centrality from seed nodes.
        Used by Category 7 Condition C (topological pre-filtering)."""
        ...
```

### Corpus Calibration (codetopo method)

`sme-eval calibrate` verifies the seeded corpus against a frozen reference, not exploratory analysis. The reference ships as `sme/corpora/standard_v1/calibration.json`:

```json
{
  "version": "v0.1",
  "corpus_sha256": "a1b2c3...",
  "computed_at": "2026-04-12T03:00:00Z",
  "betti_0": 5,
  "betti_1": 3,
  "communities": 4,
  "gap_communities": [["auth_engineering", "privacy_research"]],
  "disconnected_threshold": "shortest_path > 4 hops",
  "alias_pairs_string_similarity": {"max_jaccard": 0.25},
  "alias_pairs_semantic_similarity": {"min_cosine": 0.78},
  "defect_cluster_component_id": "runaway_ner_001",
  "monoculture_betti0_divergence_expected": ">2.0"
}
```

`sme-eval calibrate` first checks `corpus_sha256` against the actual corpus tree (YAML + vault). If the hash doesn't match, calibration is stale — someone edited the corpus without re-running calibration. The tool aborts with a specific diagnostic. Then it re-computes structural properties and diffs against the frozen reference. If any value drifts beyond threshold, calibration fails with a specific diagnostic. Calibration results are versioned with the corpus — anyone can reproduce.

**Thresholds:**
- "Disconnected" = shortest path > 4 hops between gap communities (no accidental bridges)
- Alias pairs must have Jaccard string similarity < 0.25 AND cosine semantic similarity > 0.78 (confirms testing canonicalization, not fuzzy match)
- Runaway cluster must be in its own connected component

**On failure:** `sme-eval calibrate --repair` attempts automated fixes (removing accidental bridge edges, adjusting defect placement). If repair fails, manual intervention required. The tool outputs exactly which property failed and why.

### Seeded Corpus: v0.1 Specification

The benchmark is only as good as its corpus. Ship v0.1 before writing adapter code — cheap, throwable, validates the full pipeline.

**v0.1 scope (starter corpus):**
- **30 notes** across 4 domains (auth_engineering, privacy_research, infrastructure, temporal)
- **50 ground-truth questions:** ~8 per category (Cat 1-6), plus 10 multi-hop queries (Cat 2c) each annotated with `min_hops_in_ground_truth_graph: int` (3 at depth 1, 4 at depth 2, 3 at depth 3 — hop count fixed at corpus design time, not measured per system), plus 8 token-efficiency queries (Cat 7)
- **5 injected defects:** 2 duplicate-evidence notes, 1 misattributed-evidence note, 1 ghost-entity trap (YAML frontmatter bait), 1 monoculture batch (10 RELATED-only edges)
- **3 alias pairs:** "ZK proof" / "zero-knowledge cryptography", "k8s" / "Kubernetes", "CBT" / "Cognitive Behavioral Therapy"
- **2 contradictions:** auth system choice (Clerk vs Auth0), database choice (PostgreSQL vs SQLite)
- **1 temporal evolution:** 3-session fact change (PostgreSQL → SQLite → PostgreSQL)
- **1 structural gap:** auth_engineering and privacy_research share "token-based identity" topic but have zero cross-domain edges
- **Generation method:** hand-authored. Not LLM-synthesized, not adapted from existing datasets. Hand-authoring at this scale ensures every ground-truth answer is verified and every defect is intentional.
- **Format:** YAML + Obsidian vault (both, from v0.1 onward)
- **Defect density:** 5/30 = 17% of notes contain defects. Realistic enough to be meaningful, concentrated enough to be testable at small corpus size.
- **Held-out split:** v0.1 is all dev. v1.0 introduces a held-out split: separate YAML file, hash-locked, downloaded separately, not in the main repo.

**Domain coverage note:** v0.1 is tech/dev focused (auth, infrastructure, privacy). v1.0 should add personal knowledge domains (health, travel, relationships) to avoid biasing against non-technical memory systems. This is a known limitation of v0.1.

**Category slugs** (used in CLI and config):
`factual`, `cross_domain`, `contradiction`, `ingestion`, `gap`, `temporal`, `tokens`, `ontology`

---

## Category 1: Factual Retrieval — The Lookup (baseline)

**What it tests:** Can the system find a specific memory given a natural language query?

Equivalent to LongMemEval's information extraction category. Every memory system must pass this.

**Test design:** N questions with known ground-truth answers. Measure Recall@K and answer accuracy via calibrated judge (GPT-4o, following LongMemEval's methodology with >97% human agreement).

**Metrics:** Retrieval Recall@K, Answer accuracy (judge-scored)

---

## Category 2: Cross-Domain Discovery — The Crossing, The Registry, The Stairway

**What it tests:** Can the system find connections across domains that the user never explicitly linked?

LongMemEval's multi-session reasoning is adjacent but doesn't test canonicalization-dependent discovery. No existing benchmark distinguishes "traversal failed" from "entity resolution failed."

**Test design:** Seed memories across domains with structural (not semantic) connections.

Example: Domain A: "Kai debugged the OAuth token refresh issue." Domain B: "The Driftwood auth migration was blocked by token expiry." Query: "what blocked the auth migration?" should surface Kai's session.

**Sub-test 2b: Canonicalization-dependent discovery.** Alias pairs where connection only resolves with entity merging. "ZK proofs" / "zero-knowledge cryptography", "CBT" / "Cognitive Behavioral Therapy", "k8s" / "Kubernetes", "LLM" / "large language model."

**Sub-test 2c: Multi-hop reasoning by depth.** Seed queries requiring 1-hop, 2-hop, and 3-hop traversal. Measure recall at each depth separately. A flat vector store may match graph performance at 1-hop (the answer chunk is semantically similar to the query). At 2-3 hops, the graph should pull ahead because intermediate entities aren't semantically similar to the query — they're only reachable via typed relationships. The hop-depth breakdown shows exactly where structure starts earning its keep.

Examples at increasing depth:
- 1-hop: "What auth system is Kai working on?" (direct entity lookup)
- 2-hop: "Who debugged the system that blocked the Driftwood migration?" (Kai → OAuth → Driftwood)
- 3-hop: "What project was affected by the issue debugged by someone on the infrastructure team?" (team → Kai → OAuth → Driftwood)

**Reachability pre-test (hop-depth gate).** Hop depth is a property of the corpus-as-annotated, not the system-as-built. A question labeled 3-hop in the ground-truth graph may be 1-hop in a system whose index contains a direct edge between the endpoints, or structurally unanswerable in a system whose graph does not contain the intermediate edges at all. Before scoring a question at depth k on a given system, run a reachability check against that system's graph snapshot: does a path of length ≤k exist between the entities referenced by the expected-source set? If yes, score the result at depth k. If no, move the question to a separate `unreachable_in_graph` bucket and exclude it from the per-depth recall breakdown (it is still reported in the bucket so the reader sees the exclusion count). Without this gate, "graph did not pull ahead at 3-hop" conflates two distinct failures — "the router or traversal is broken" and "the edges this annotation assumed never existed in this graph" — and they require different fixes. The reachability snapshot is taken once per (system, corpus) and cached alongside `implied_ontology.yaml`.

GraphRAG-Bench tests multi-hop reasoning across different graph architectures (RAPTOR, HippoRAG, community-based). SME adds: does the *same system's* advantage over flat retrieval scale with hop depth, restricted to questions its graph can in principle answer at that depth?

**Topology integration:** Community detection after ingestion. Seeded cross-domain connections should produce inter-community edges. If they don't, topology detects it before query tests run.

**Metrics:** Cross-domain Recall@K, Canonicalization Recall, Multi-hop Recall@K by depth (1/2/3-hop), Inter-community edge density, Baseline delta vs flat adapter

---

## Category 3: Contradiction Detection — The Dissonance

**What it tests:** Does the system detect and surface conflicting facts?

LongMemEval tests knowledge updates (returning the latest fact). SME tests whether the system explicitly flags the contradiction, not just returns the most recent value.

**Test design:** Contradictory memories in different sessions. Query should surface both AND flag the conflict.

**Metrics:** Contradiction Detection Rate, Contradiction Precision

---

## Category 4: Ingestigation — The Threshold

(Renamed 2026-05-01 from "Ingestion Integrity." See [`docs/ingestigation.md`](ingestigation.md)
for the rationale, the existing-tools survey — SHACL, W3C PROV-O, ProVe, Splink,
OpenLineage, Great Expectations — and the proposed Cat 4d/4e/4f sub-test additions
informed by that research. Implementation module retains the file name
`sme/categories/ingestion_integrity.py` for import stability.)

**What it tests:** Can structural damage from the ingestion pipeline be detected — either by the system itself or by external analysis of its graph?

**Position vs prior art.** [Hofer et al. 2023 (arXiv 2302.11509)](https://arxiv.org/abs/2302.11509)
surveys KG-construction quality vocabularies (accuracy / coverage /
consistency / fact-level provenance). [GraphGuard (SemIIM 2023)](https://ceur-ws.org/Vol-3647/SemIIM2023_paper_5.pdf)
integrates the W3C-PROV / DCAT / DQV stack. SHACL has been the W3C-recommended
constraint language since 2017. [KGist / KGGen MINE (Stanford, NeurIPS 2025)](https://arxiv.org/abs/...)
test extraction quality from outside. SME's distinctive contribution at this
layer is **per-edge-type evidence-rule registration at corpus-design time**
(see `good-dog-corpus/ontology.yaml#edge_types` for the worked example),
the **A/B/C/D condition isolation** that pairs ingestigation readings
against the corpus's own gold registry, and the **lightweight registry-
and-lexical-rules-only fallback** for systems that don't run ProVe-grade
LLM verification infrastructure. See `docs/ingestigation.md` for the
full survey + the SHACL / PROV-O / Splink / OpenLineage integration
proposals.

**Critical distinction: introspection vs external.** The spec splits every sub-test into two scores:

- **4-introspection:** Does the *system under test* surface the anomaly via its own API, health checks, or logs? Most systems will score 0 here. That's the finding — it means the system has no pipeline self-monitoring. (Systems with an enrichment maturation lifecycle would score non-zero; MemPalace would score 0.)
- **4-external:** Given the graph snapshot, does *SME's topology layer* detect the injected defect? This measures how legible the system's graph is to external analysis — a useful property even if the system itself is blind.

The scorecard reports both. Without this split, the benchmark conflates "good system" with "good graph shape."

**Sub-test 4a: Evidence duplication.** N edges with identical evidence strings. (Derived from: Haiku stamping 8,238 identical evidence strings.)
- *Introspection:* does the system flag duplicate evidence during or after ingestion?
- *External:* does the topology layer identify the high-density cluster of identical-evidence edges?

**Sub-test 4b: Evidence misattribution.** Evidence references wrong domain. (Derived from: Haiku mixing note content with relationship semantics.)
- *Introspection:* does the system detect provenance mismatch?
- *External:* does embedding-based analysis of evidence strings vs entity neighborhoods flag the mismatch?

**Sub-test 4c: Edge type monoculture.** >50% generic edges forming parallel universe from typed edges. (Derived from: 16,911 RELATED edges.)
- *Introspection:* does the system report edge type distribution or RELATED-to-typed ratio?
- *External:* `filtered_subgraph()` on typed-only vs generic-only. Betti-0 divergence = monoculture severity.

**Entropy metric — normalized by vocabulary size.** Raw Shannon entropy of the edge-type distribution is reported in bits, but raw bits are vocabulary-size-sensitive: a graph with 2 declared edge types used exactly equally has entropy 1.0 bits, which a fixed-bits threshold would flag as "severe monoculture" even though the distribution is perfectly balanced across its declared vocabulary. The headline metric is therefore `normalized_entropy = H(edge_type) / log2(n_declared_types)`, a [0,1] score where 1.0 means perfectly balanced across the declared vocabulary and 0.0 means a pure monoculture. Raw-bit entropy is reported alongside for back-compat with earlier scorecards. Normalized thresholds: ≥0.8 healthy, 0.5–0.8 concentrated, <0.5 monoculture, with the raw-bit heuristics (≥2.5, 1.5–2.5, <1.5) retained as fallbacks when the declared vocabulary is unknown or the adapter reports effective-types-only. The same normalization applies to entity-type entropy when Cat 8 reports it.

**Sub-test 4d: Runaway extraction pattern.** Disproportionate low-connectivity cluster from one source. (Derived from: 8,800 ghost entities from NER false positives on YAML frontmatter.)
- *Introspection:* does the system flag the anomalous pattern or component?
- *External:* `TopologyAnalyzer.diff()` pre/post ingestion. H0 spike = runaway pattern fingerprint.

**Metrics:**
- Ingestion Anomaly Detection Rate (introspection) — fraction of defects the system itself flags
- Ingestion Anomaly Detection Rate (external) — fraction of defects SME's topology detects
- False positive rate (both)
- Time to detection — during ingestion, health check, or only when queried?
- H0 delta, Typed/generic Betti-0 divergence (external only)

---

## Category 5: Gap Detection — The Missing Room

**What it tests:** Can the system identify what's missing — either through its own analysis or through external topology?

**No existing benchmark tests this.** This is what persistent homology is for. Gaps are holes.

**Same introspection/external split as Category 4:**

- **5-introspection:** Does the system proactively surface gaps?
  - **Level 1 (L1):** Answers "what topics have no cross-references?" when explicitly asked.
  - **Level 2 (L2):** Proactively surfaces gaps in a health check or briefing without being asked.
- **5-external:** Does SME's topology layer detect the seeded gaps?
  - **Level 3 (L3):** Persistent H1 features from Ripser identify structural holes.

**Topology integration (external):** Ripser with confidence-weighted filtration. H1 features persisting across wide filtration range = stable structural gaps. Cross-reference with Louvain communities for high-confidence gap identification. A persistent H1 feature spanning two communities with shared topic keywords is a confirmed gap.

**Metrics:**
- Gap Recall (introspection) — fraction of seeded gaps the system itself identifies (L1 or L2)
- Gap Recall (external) — fraction of seeded gaps SME's topology detects (L3)
- Gap Precision (both) — fraction of reported gaps that are real
- H1 persistence range — topological confidence per detected gap
- Detection level achieved (L1/L2/L3)

---

## Category 6: Temporal Reasoning — The Archive

**What it tests:** Current vs. historical state, evolution tracking.

LongMemEval tests time-point queries. SME adds provenance chain integrity — which process produced an edge, and was it superseded?

**Test design:** Fact evolution across sessions. Sub-test 6b: provenance chain queries ("which edges were reclassified from RELATED to typed?").

**Topology integration:** Ripser with temporal filtration. Persistence diagrams at different time slices show structural evolution.

**Metrics:** Temporal Accuracy, Evolution Completeness, Provenance Accuracy, Temporal persistence stability

---

## Category 7: Token Efficiency — The Abacus (Graph vs. No-Graph Baseline)

**What it tests:** Does structure earn its overhead in tokens?

**No benchmark formalizes this.** Zep reports < 2% of baseline tokens as a marketing metric. ENGRAM reports 95.5% token budget reduction. But no standard benchmark measures tokens-per-correct-answer with same corpus, same LLM, same judge across conditions.

**Three headline conditions:**
- **Condition A (flat):** `FlatBaseline` adapter — top-K cosine similarity over the raw vector store, no metadata filtering, no structural routing.
- **Condition B (full pipeline):** System under test with its structural retrieval layer enabled. This is what users actually experience at query time.
- **Condition C (structure disabled):** System under test with its structural filter/router/scoper turned off but still reading the same underlying index. For a ChromaDB-backed system this means the same collection queried without a `where` clause. For a typed graph system this means semantic retrieval without edge-type traversal.

**Floor condition (grep baseline):** `grep -l <question_keywords>` on filenames only, no retrieval at all. Reports which expected-source filenames would be returned by a plain string match on the corpus directory listing. This is the floor for the substring-on-filename matcher — any retriever scoring at or below this number on a given corpus is reading filename overlap, not retrieval quality. Reported alongside A/B/C so the reader can see how much of every condition's score is attributable to the matcher versus the retriever. On corpora where filenames contain their subjects (biographical, entity-per-file), the floor is typically high or at ceiling; on corpora where they don't (research content, conversation logs), the floor is typically low, and `(A − floor)` is the signal the retriever contributes above the matcher's filename bias. A system whose A/B/C readings all collapse to the floor on a given corpus is being measured for filename overlap, not retrieval. The floor is computed once per (corpus, question set) and cached.

All three headline conditions (plus the floor) use the same corpus, same embedding model, same LLM, same judge. **The headline metric is A vs B vs C above the grep floor, not A vs B alone.** Without Condition C, the benchmark can't distinguish "the structural layer earned its complexity" from "the underlying index is fine and the structural layer is a tax / harmful." Without the floor, the benchmark can't distinguish "the retriever works" from "the filename matcher happened to work on this corpus."

Interpretation key for `B - C`:
- **Positive on recall and/or negative on tokens:** structure earns its complexity. The structural layer is adding measurable value beyond what the raw index provides.
- **Near zero on both axes:** structure is a neutral tax. Costs a few tokens for source labels/metadata overhead but doesn't help or hurt retrieval quality. May still be valuable for interpretability.
- **Negative on recall:** structure is actively harmful. The routing / scoping / traversal is throwing away correct answers that the raw index would have returned. Observed on the climate-research corpus + MemPalace + lexical room routing on 2026-04-10 — 47pp recall drop with no token savings, tokens-per-correct-answer 2.7x higher.

**Optional research condition:**
- **Condition D (structure + topology):** Topological pre-filtering (PageRank — chosen for stability over betweenness/degree) before embedding similarity. Reported separately as "topology-augmented retrieval (research)." Not included in headline tokens-per-correct-answer because it composes the system's structure with SME's auxiliary layer — a weaker claim than "the system's graph earns tokens."

**Token measurement:** SME computes tokens from `QueryResult.context_string` using tiktoken (cl100k_base encoding). The adapter returns the actual context it would inject into the LLM. SME tokenizes it. Adapters can't game the count.

**Judge methodology for Cat 7:** Pairwise comparison (BenchmarkQED's AutoE pattern), not absolute scoring. Both conditions' answers are presented to the judge in counterbalanced order. Judge determines win/loss/tie. This removes verbosity bias — GPT-4o rewards verbose answers in absolute scoring, which is exactly the wrong bias when measuring whether fewer tokens produce equal quality.

**Four measurements:**
- **7a:** Tokens for equivalent quality (unconstrained). Pairwise: at what token count does the flat condition match the graph condition's quality?
- **7b:** Quality at fixed token budget (e.g., 4K tokens). Pairwise: which condition wins more queries?
- **7c:** Degradation at scale (10K → 50K → 200K entities). Does flat degrade faster?
- **7d:** Efficiency by hop depth. Break down tokens-per-correct-answer for 1-hop, 2-hop, and 3-hop queries (using the same queries from Category 2c). At 1-hop, graph advantage may be modest (1.5x). At 3-hop, it should be dramatic (5-10x). If it doesn't scale with depth, the traversal isn't working.
- **7e:** Structural contribution isolation. Report A, B, and C separately so readers can compute (B − C) = structural contribution and (C − A) = non-structural overhead (source labels, formatting, metadata envelopes). Without this breakdown, it's impossible to tell whether a system's full-pipeline result is driven by its structural layer or by its underlying vector index.

**Key metric: tokens-per-correct-answer.** A vs B only. Lower is better. The hop-depth curve is the structural explanation.

### Judge Configuration

```yaml
judge:
  model: "gpt-4o"
  temperature: 0.0
  method: "pairwise"           # Cat 7; other categories use "absolute"
  cost_budget_usd: 50.0        # abort if estimated spend exceeds this
  dry_run: true                # estimate cost before executing

calibration:
  human_judged_set: "sme/corpora/calibration_50q.yaml"  # 50 questions
  # Report judge-human agreement for YOUR corpus, not just LongMemEval's
```

`sme-eval run --dry-run` estimates judge cost across all categories × conditions × queries and aborts if it exceeds the budget. No surprise bills.

---

## Category 8: Ontology Coherence — The Blueprint

**What it tests:** Does the system's actual graph structure match what it claims to do?

**No existing benchmark tests this.** Palantir tests ontology operationally — simulation sandboxes for edits, branching for change management, AIP Evals for LLM function correctness against the ontology. They don't test whether the ontology is structurally sound because their ontologies are hand-built by forward-deployed engineers. Auto-extracted ontologies from ingestion pipelines need this. The Semantic Web Journal's structural quality metrics measure static KGs (Wikidata, DBpedia) but not live memory systems.

**Ontology source detection:** Most systems don't have a declared ontology. The eval suite adapts to whatever is available, in priority order:

1. **Declared schema** (if it exists) — LadybugDB typed tables, Neo4j constraints, ONTOLOGY.md. Test directly against declarations.
2. **Documentation claims** — README describes wings, halls, rooms, tunnels. Extract testable structural assertions via LLM pass over documentation.
3. **Inferred from graph** — no documentation at all. Run the graph snapshot through type distribution analysis. Report what the ontology *actually is*. No claims to test against, but coherence is still measurable.

The adapter's `get_ontology_source()` method returns whichever is available. The suite adapts: strictest for declared, informative for readme-derived, descriptive for inferred.

**Implied ontology extraction (for README-based systems):**

The extraction is a one-time tool, not part of the benchmark loop. Run it once, commit the result as `implied_ontology.yaml` in the adapter directory. SME reads the YAML during eval — no LLM call in the benchmark path.

```bash
# One-time: extract implied ontology from README
sme-eval extract-ontology --readme path/to/README.md --output implied_ontology.yaml

# The LLM call is cached by sha256(readme + configs)
# Re-running on identical input returns cached result
```

```python
@dataclass
class ImpliedOntology:
    entity_types: list[str]       # claimed entity types
    edge_types: list[str]         # claimed relationship types
    structural_claims: list[str]  # "memories organized hierarchically"
    retrieval_claims: list[str]   # "wing-based filtering improves retrieval"
    source: str                   # 'declared' | 'readme' | 'inferred'

def extract_implied_ontology(readme: str, configs: list[str]) -> ImpliedOntology:
    """LLM extracts testable structural claims from documentation.
    
    Input: 'MemPalace organizes memories into Wings (person, project, 
    concept), Halls (facts, events, discoveries), and Rooms (topics).
    Tunnels connect memories across Wings.'
    
    Output: ImpliedOntology(
        entity_types=["person", "project", "concept", "topic"],
        edge_types=["fact", "event", "discovery", "tunnel"],
        structural_claims=[
            "entities are partitioned into wings by type",
            "cross-wing connections exist (tunnels)",
            "memories are organized hierarchically (wing > hall > room)"
        ],
        retrieval_claims=[
            "wing-based filtering improves retrieval"
        ],
        source='readme'
    )
    """
```

**Sub-test 8a: Type coverage.** Do claimed entity types exist in the graph? What percentage of entities fall outside claimed types? High leakage means the extraction pipeline creates things the system doesn't claim to handle. For declared schemas, entities of undeclared types should be rejected at ingestion (LadybugDB pattern) or flagged.

**Sub-test 8b: Edge vocabulary completeness.** Do claimed edge types exist? Are the defined types sufficient for the relationships in the corpus? Seed relationships that don't fit any declared type — the system should use a generic fallback and flag it, or reject the edge. This is the inverse of monoculture: monoculture means the system *has* typed edges but doesn't *use* them; vocabulary incompleteness means it *can't* use typed edges because the right types don't exist.

**Sub-test 8c: Schema-data alignment.** Do actual type distributions match what the ontology declares? If the ontology defines 15 entity types but 80% of entities are `concept`, the ontology may be over-specified or the pipeline under-classifying. Reported descriptively as type distribution entropy — not normatively. High entropy is not inherently "better"; a research corpus *should* be concept-dominated. If the ontology declares an expected distribution (e.g., "expect 60% concept, 20% person, 20% other"), score against that expectation. Otherwise report the distribution and flag extreme concentration (>80% single type) as a warning, not a failure.

**Sub-test 8d: Ontology drift.** After ingestion, has the effective ontology (what types are actually in the graph) diverged from the declared ontology? New types appear that aren't declared (e.g., PART_OF and DEPLOYED_ON emerging from a reclassification pass). Declared types go unused. This is a temporal ontology health check.

**Sub-test 8e: Structural claim verification.** Do structural claims from the README hold in the actual graph? Claims must have operational definitions from a fixed library — no LLM interpretation of whether a graph "looks hierarchical." See `sme/claims/structural_claims.yaml` for the complete library. Claims without an operationalization in the library are rejected with a warning, not tested fuzzily.

Operationalized claim library (v0.1):

| Claim pattern | Operational definition |
|---|---|
| "hierarchical" / "nested" | Modularity > 0.5 AND degree distribution follows power-law (KS test p < 0.05) |
| "cross-X connections exist" | Inter-community edge density > 0 for the named communities |
| "partitioned by type" | >90% of entities within each community share an entity type |
| "improves retrieval" | Cat 7 A-vs-B pairwise win rate > 55% (defer to Cat 7 results) |
| "temporal tracking" | >50% of edges carry a non-null `_created_at` property |
| "conflict detection" | Cat 3 ContradictionPair count > 0 on contradiction queries (defer to Cat 3) |
| "deduplication" | Alias pairs in Cat 2b resolve (defer to Cat 2b canonicalization recall) |
| "provenance" | >50% of edges carry a non-null `_created_by` property |

Claims not matching any pattern are reported as "untestable — no operational definition" and excluded from the claim pass rate denominator. The library also defines an explicit `untestable_patterns` denylist (UX claims, vague performance claims, security claims, scalability claims without defined targets) — claims matching these are rejected even if they look superficially matchable, because they belong to other evaluation traditions and would dilute structural scoring.

**Introspection/external split (consistent with Cat 4/5):**
- **8-introspection:** Does the system surface its own type drift, vocabulary gaps, or schema-data misalignment in a health check or API? Systems with an enrichment maturation lifecycle can partially answer this; systems without a health-check API cannot answer it at all (as far as I know, MemPalace's public surface does not expose this today — corrections welcome). Score separately from 8-external so absence of introspection is distinct from a bad graph.
- **8-external:** Does SME's analysis of the graph snapshot detect these issues? This is the default path for most systems.

**For systems with no documentation (inferred mode):**

```
Ontology Discovery (no declared ontology found)
═══════════════════════════════════════════════════
Entity types found:        12
  Top 5 by count:          concept (4,201), person (891), tool (456),
                           project (312), organization (201)
Edge types found:          8
  Top 3 by count:          RELATED (16,911), SUPPORTS (8,234),
                           MENTIONS (5,102)
Type concentration:        68% of entities are 'concept'
                           (⚠ possible under-classification)
Edge type entropy:         1.4 bits (low — dominated by RELATED)
Orphan types:              3 types with <5 entities each
```

Still useful — tells the builder what their system actually built. Feeds into Category 4 (monoculture is an ontology coherence problem).

**Metrics:** Type Coverage (% of entities matching declared types), Edge Vocabulary Completeness, Type Distribution Entropy, Ontology Drift Score (declared vs actual), Structural Claim Pass Rate (for README-derived claims)

---

## Category 9: Harness Integration — The Handshake

**What it tests:** Does the model actually invoke the memory system when it has access to it, and do the returned results land in a form the model can consume?

**No existing benchmark tests this.** LongMemEval, LoCoMo, MINE, GraphRAG-Bench, BEAM — and Categories 1 through 8 of this spec — all measure **offline retrieval**: "given this query, does the retriever return the right document?" That measurement happens outside any model's runtime. In production a memory system is never reached in isolation; it is reached through an **invocation surface**: a tool call definition, an MCP resource, a Claude Code hook, a slash command, a custom GPT action, a file watcher, an IDE extension. The effective memory for a specific deployment is approximately:

```
effective_memory  ≈  retrieval_quality  ×  invocation_rate  ×  call_through_success  ×  result_usage
```

Every other category in this spec measures the first factor. Category 9 measures the remaining three. A memory system scoring 95% on offline Cat 1 that gets invoked 20% of the time in production is a 19% effective memory for that deployment. The gap is a strong function of (a) which model is at the wheel and (b) which harness mediates the call. Claude Sonnet 4.5, Claude Opus 4.6, GPT-4, Gemini, and Llama have different tool-use priors, and the same memory system reached through an MCP server, a Claude Code hook, a LangChain tool, and a ChatGPT custom GPT action can produce wildly different call-through rates on the same corpus.

**Test design:** Run the same question set through two passes on the same corpus:

- **Offline upper bound (Cat 1 / Cat 7 A-B-C baseline):** the retriever called directly, as in every existing category. This establishes the ceiling: how well the memory *can* answer the question.
- **In-harness reading:** the same memory system wired through its actual production invocation surface, reached by a specific target model running in its native harness. The model receives the user's question as a conversational turn, has the memory tool exposed via the harness, and is free to invoke it (or not). The diagnostic records what the model does.

The delta between the offline upper bound and the in-harness reading is the **harness-integration gap**. This is the category's headline metric.

**Sub-tests:**

- **9a: Invocation rate.** On questions where the memory system contains the answer (verified by the offline Cat 1 run), how often does the model actually invoke the memory tool in its response? Reported as calls-per-query or as a distribution (0 calls, 1 call, 2+ calls) per (memory_system, harness, model) tuple.

- **9b: Call-through success.** Given an invocation, does the tool call complete and return a valid result? Measures integration breakage (bad schema, timeout, wrong parameters, tool not registered, MCP server unreachable) separately from model behaviour. A low 9a with a high 9b means "the model isn't reaching for the tool"; a high 9a with a low 9b means "the model is reaching but the integration is broken." These failure modes need different fixes.

- **9c: Result usage.** When the tool returns results successfully, does the model actually use the context in its reply, or does it invoke the tool and then ignore the result? Measured by substring match of the retrieved content or expected filenames in the model's output text, or by an LLM judge at the same cost profile as Cat 7's judge. A system that gets invoked and returns correct content but has its results ignored is spending tokens without shaping the answer.

- **9d: Negative-control rate.** On questions where the memory system has no answer (seeded negative control, held out from 9a's positive set), does the model correctly skip the invocation, or does it invoke anyway and then hallucinate a citation? A useful diagnostic for tool-description specificity and system-prompt quality. A system that invokes on every query regardless of relevance is exercising the tool but wasting tokens and context.

- **9e: Per-model sensitivity.** Holding memory + harness fixed, swap the model. Report the delta table across Claude Sonnet 4.5, Claude Opus 4.6, GPT-4, Gemini, Llama (whichever the user has API access to). Non-trivial deltas are a finding about the target model's tool-use priors on that kind of memory surface — not a finding about the memory system itself. This is a reporting axis rather than a pass/fail test.

- **9f: Per-harness portability.** Holding memory + model fixed, swap the harness. The same memory system may be wired as an MCP server, a Claude Code hook, a LangChain tool, a custom GPT action, or a direct API shim. Run the same question set through each supported harness the system exposes, and report the ones where the invocation surface is broken or degraded. A system built for Claude Code hooks may silently fail as a Cursor MCP resource because the schema didn't survive the translation, and the diagnostic surfaces that.

- **9g: Hook-driven (event-driven) access.** Distinct from tool-call invocation because the model is not deciding whether to fire — a harness-level hook fires on some event (pre-tool-use, post-tool-use, session-start, user-prompt-submit in Claude Code's hook model, or the equivalent callback point in any other agent harness). The hook runs some code, which reaches the memory system, and injects context into the model's turn without the model ever choosing to invoke anything. Three things to measure: does the hook fire when expected, does it complete and return context, and does the injected context actually reach the model's input in a form it can read. Hook-driven access is architecturally different from tool-call access and should be reported separately, because the failure modes are different (for tool calls: "model didn't invoke"; for hooks: "hook didn't fire" or "hook output wasn't injected"). The Claude Code hook system is the motivating concrete example, but the pattern generalizes to any agent harness that supports pre/post callbacks: the harness is the subject, not the model.

  **9g is the least portable sub-test.** The other sub-tests (9a–9f) can plausibly be covered by a shared adapter contract — every modern agent harness that exposes tool use exposes roughly the same shape of invocation, so a `ToolCall` or `MCPResource` descriptor can be implemented once per harness and reused. Hook-driven access is different: the event model, the fire conditions, the injection mechanism, and the observability of whether a hook ran are all harness-specific, and they change with harness updates. Claude Code's hook taxonomy (PreToolUse, PostToolUse, Stop, UserPromptSubmit, SessionStart, PreCompact) is not the same as Cursor's, is not the same as LangGraph's, is not the same as whatever callback points OpenAI Assistants or the Google Gen AI Agents framework expose. Implementations of 9g will almost certainly need to live as **per-harness shims** — a `ClaudeCodeHookRunner`, a `CursorHookRunner`, a `LangGraphCallbackRunner` — rather than as a single generic adapter method. The spec's job is to define what 9g should measure (fire rate, completion rate, context-injection rate); each harness needs its own implementation of how to observe those things. Expect 9g implementations to break on harness version bumps and plan to pin harness versions in the test config.

**Metrics:**
- Invocation rate (percentage of positive-set queries where the memory tool was called)
- Call-through success rate (percentage of invocations that returned a valid response)
- Result-use rate (percentage of successful responses reflected in the model's reply)
- Unnecessary-invocation rate (percentage of negative-control queries where the tool was called)
- Harness-integration gap = offline Cat 1 recall − in-harness recall (headline metric)
- Per-(model, harness) cross-tab (reporting artefact, not a single number)
- Hook fire rate, hook completion rate, context-injection success rate (for 9g)

**Why this is novel:**

1. No published memory benchmark measures call-through rate. All of them assume the retriever is always called by construction.
2. None report per-(model, harness) results. The same memory system scoring 80% on Claude Code hooks and 20% on a ChatGPT custom GPT action is a finding the deployment engineer needs, and no current tool produces it.
3. No benchmark distinguishes "my model doesn't reach for the tool" from "the tool is broken" from "the model uses the tool but ignores the result." These are different diagnoses requiring different fixes, and conflating them is the default in every existing benchmark.
4. No benchmark measures hook-driven access at all, because hook-driven access is not a retrieval pattern most benchmarks have considered. Claude Code's hook system and equivalent callback points in other agent harnesses are increasingly how production memory systems actually get reached, and measuring their integration quality is a separate problem from measuring tool-call integration quality.

This is the category that turns "retrieval is great in principle" into "retrieval works for this specific build, with this specific model, under this specific harness." That is the question every deployment engineer actually has, and it is the question no existing benchmark answers.

**Requirements / dependencies:**

- **API keys for each target model.** Opt-in, adds cost like the Cat 7 LLM judge. Budgeted via `cost_budget_usd` with a `--dry-run` path for estimation.
- **Harness manifest per adapter.** The adapter needs to declare what invocation surfaces it supports. New optional adapter method: `get_harness_manifest() -> list[HarnessDescriptor]`, where a `HarnessDescriptor` is one of:
  - a `ToolCall` descriptor (tool name, JSON schema, backend endpoint)
  - an `MCPResource` descriptor (server URL, resource URI pattern)
  - a `ClaudeCodeHook` descriptor (hook type: PreToolUse / PostToolUse / Stop / UserPromptSubmit / SessionStart, command to run)
  - a `SlashCommand` descriptor (command name, invocation shape)
  - a `CustomAction` descriptor (arbitrary shape with a `call(query, model_context)` method)
- **Model runner shim.** A thin layer that sends a user message to the target model API with the declared harness wired in, lets the model take its turn (including any tool calls), and returns a `HandshakeTrace` containing: the model's output, the list of tool calls attempted, the list of tool calls that succeeded, the tool responses received, and any hook activity the runner can observe.
- **Matcher reuse.** The Cat 1 substring-match matcher runs against the model's *final reply text*, not against the raw tool response. The whole point of Cat 9 is that a tool response buried in a conversation the model ignores does not count as retrieval.

**Status:** Spec'd, not implemented. This is the single most important planned addition to the framework because it's the thing that turns every other category's reading into a claim about a specific deployment rather than a claim about a retriever in isolation. Listed as a Tier-1 planned refinement alongside the grep-floor baseline and the hop-reachability pre-test gate.

**Open design questions:**

1. **Can this be scored without a live model API?** Partially. 9b (call-through success) can be measured against a mock model that always invokes the tool — this tests the integration independent of model behaviour. 9a, 9c, 9d, 9e, 9g all require a real model runtime and cost real money.
2. **How to attribute hook failures?** When a Claude Code hook fails to fire or to inject context, the failure could be in the harness's hook runtime, in the hook command itself, or in the memory system the hook is reaching. The HandshakeTrace needs enough provenance to attribute each step.
3. **How much of this is model-provider-specific?** The tool-call protocol is standardizing (OpenAI tool-calls, Anthropic tool-use, MCP) but the Claude Code hook system is Anthropic-specific and the equivalent callback points in other harnesses have different names and shapes. A portable test probably needs per-harness adapters.
4. **How does this compose with Cat 7's pairwise judge?** Cat 7 judges answer quality. Cat 9 measures whether the model ever sees the context that would inform a good answer. In production these are coupled: no invocation → no context → worse answer. The reporting layer should show both numbers side by side.

---

## Visualization Layer

Results need to be seen, not just read.

### 1. Scorecard Radar Chart
Eight-category radar. Overlay multiple systems. Sub-scores as concentric rings.

### 2. Graph Snapshot
After ingestion, render what the system built. Two paths:
- **Bugscope** (LadybugDB systems): interactive force-directed graph, zero additional code.
- **NetworkX + pyvis** (all others): community coloring, edge type coloring, node size by degree.

`highlight_defects=True` overlays Category 4 results — green (caught) vs red (missed).

### 3. Topology Visualization
- Persistence diagram (birth/death scatter)
- Barcode (horizontal bars per feature)
- Community map (Louvain clusters with inter-community edges)
- H1 features mapped to entity neighborhoods (gap detection viz)

### 4. Token Efficiency Charts
- Bar: tokens-per-correct-answer by condition
- Line: quality vs token budget
- Scatter: quality vs tokens per query, colored by condition
- Scale curve: quality at corpus sizes per condition

### 5. Ingestion Diff
Pre/post ingestion structural changes. Red = new disconnected components. Orange = duplicate evidence clusters. Yellow = ghost entities.

### Report Output

```
report/
  ├── scorecard.md / .html
  ├── radar.svg
  ├── graph_snapshot.html
  ├── topology/
  │   ├── persistence_diagram.svg
  │   ├── barcode.svg
  │   ├── community_map.svg
  │   └── h1_features.svg
  ├── token_efficiency.svg
  ├── multi_hop_curve.svg          # recall and efficiency by hop depth
  ├── ingestion_diff.html
  ├── ontology_coherence.md        # declared vs actual, drift, claims
  ├── per_query_results.csv
  └── raw_scores.json
```

---

## Scoring and Reporting

```
Structural Memory Evaluation — [system_name]
═══════════════════════════════════════════════════════════════
Factual retrieval        92%    (baseline)
Cross-domain             67%    (structural contribution)
  └ Canonicalization     48%    (alias resolution)
  └ Multi-hop 1/2/3      91/74/43%  (recall by depth)
  └ Inter-community ρ    0.12   (edge density)
Contradiction            45%    (conflict awareness)
  └ Structured pairs     3/5    (ContradictionPair returned)
Ingestion integrity
  └ Introspection        12%    (system self-detected)
  └ External             78%    (SME topology detected)
  └ Type monoculture     —      (Betti-0 divergence: 4.2)
  └ Runaway patterns     —      (H0 delta: +187)
Gap detection
  └ Introspection (L1)   20%    (system answered when asked)
  └ External (L3)        60%    (SME topology detected)
  └ H1 persistent feat.  3/5
Temporal reasoning       55%    (evolution tracking)
  └ Provenance chains    42%
Token efficiency                (A vs B only; C reported separately)
  └ Tokens/correct ans.  3.2x   (graph vs flat)
  └ By hop depth         1.5x / 3.1x / 7.4x  (1/2/3-hop)
  └ Fixed-budget quality  +22%  (graph advantage at 4K)
  └ Scale degradation     0.94  (graph) vs 0.71 (flat) @ 50K
  └ Condition C (research) 4.1x (topology-augmented, not headline)
Ontology coherence       [source: declared | readme | inferred]
  └ Type coverage        88%
  └ Edge vocabulary      72%
  └ Type entropy         2.8 bits
  └ Drift score          0.15
  └ Claim pass rate      4/5

Topology summary
  └ H0 (components)       12
  └ H1 (persistent)        5    (filtration > 0.3)
  └ Modularity            0.67
  └ Isolated nodes         22
```

---

## CLI

```bash
sme-eval run --config sme_config.yaml
sme-eval run --config sme_config.yaml --category ingestion_integrity
sme-eval compare --configs ladybugdb.yaml mempalace.yaml flat.yaml --output report/
sme-eval calibrate --corpus sme/corpora/standard_v1.yaml
sme-eval viz --config sme_config.yaml --output report/graph_snapshot.html
sme-eval report --scores report/raw_scores.json --output report/
```

---

## Implementation Requirements

- Seeded corpus with known ground truth (YAML + Obsidian vault)
- Deterministic evaluation (same corpus, same queries, same scoring)
- Retrieval AND answer quality measured
- Honest failure reporting
- End-to-end system testing, not just retrieval layer
- Dev/held-out split
- Flat baseline uses same embeddings and LLM
- Category 4 requires graph state access
- Category 8 adapts to available ontology source (declared schema, README, or inferred from graph)
- Corpus calibration must pass before results are valid
- Topology runs same analysis regardless of backend
- Visualization generated for every run

---

## What This Enables

Any memory system — MemPalace, Archivist, Distillery, Graphiti, ENGRAM, EverMemOS, a personal KG, or something not yet built — installs `sme-eval`, implements the adapter (three required methods minimum), and gets a comparable scorecard with full visualization.

The adapter architecture means you don't migrate your data or change your stack. SQLite triples, Neo4j, LadybugDB, flat vectors — the benchmark meets you where you are.

The Obsidian vault corpus means file-based systems test their actual ingestion pipeline.

The visualization layer means results are legible to non-specialists.

The topology layer means structural properties invisible to queries — holes, monocultures, runaway clusters — are measured alongside retrieval performance.

Category 7 answers: "why not just use more tokens?" Category 4 answers: "how do I know my pipeline isn't corrupting my graph?" Category 5 answers: "what's missing that I haven't thought to ask about?" Category 8 answers: "does my graph match what I think I built?" The multi-hop curve in Categories 2c and 7d answers: "at what reasoning depth does structure start earning its keep?"

The prior art table makes clear: Categories 1, 3, and 6 extend existing benchmarks. Categories 4, 5, 7, and 8 are novel. Category 2's canonicalization and multi-hop sub-tests are novel. The adapter architecture, topology integration, and implied ontology extraction are novel. Everything this builds on is open source. Everything this produces will be open source.
