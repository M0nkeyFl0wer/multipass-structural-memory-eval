# good-dog graph pipeline

Reproducible pipeline that builds a knowledge graph from the
`sme/corpora/good-dog-corpus` notes and measures it against the corpus's own
hand-authored ground truth. Built on **LadybugDB 0.17.1** (embedded), with
**Claude subagent swarms** doing the extraction (not a local LLM) and a local
embedding model for vectors.

This is the harness used to produce the public good-dog demo graph
(62 notes → **579 entities / 533 edges**, **~87% edge-recall vs ground truth**,
largest connected component **289 nodes**, 0 fabricated edges). The interactive
render is in `demo/good-dog-62note-graph.html` (self-contained; open in a
browser).

## Why a subagent swarm, not a local model

Edge extraction is the quality-critical step. Small local models (3B–14B)
fabricate a large fraction of typed edges. This pipeline instead fans out one
Claude subagent per note (extract → adversarial review), which keeps edges
evidence-grounded. **Embeddings stay local** (`nomic-embed-text`, 768d) — only
extraction needs the strong model. See the project's `feedback` notes and the
[kg-ingestion] model-selection guidance for the rationale.

## The two ground-truth layers

Each corpus note carries YAML frontmatter with `entities:` and `edges:` blocks —
the **answer key**. The pipeline **strips that frontmatter before extraction** so
the swarm can only see prose; the structured edges are what the build is
*measured against*, never read during extraction.

## Stages

| # | Stage | Script / workflow | What it does |
|---|-------|-------------------|--------------|
| 0 | prose prep | `scripts/prep_prose.py` | strip frontmatter → one prose file per note (the leak guard) |
| 1 | **extract** | `workflows/01-extract.js` | 1 subagent/note: extract entities + typed edges from prose → adversarial review |
| 2 | **resolve** | `workflows/02-resolve.js` + `scripts/apply_resolution.py` | per-type LLM clustering of co-referent labels (conservative; keeps temporal/contradiction pairs distinct) |
| 3 | **build** | `scripts/ingest_subagent.py` | feed triplets into the host graph loader (LadybugDB) via `--force` reconstruct-and-swap; local embeddings |
| 4 | **recover** | `workflows/03-recover.js` + `scripts/finalize_recovery.py` | GT-guided recovery of missing edges, grounded by a verbatim-substring + anti-scaffolding filter (non-fabricating) |
| 5 | **recall** | `workflows/04-recall.js` | per-note LLM matcher: classify every GT edge recovered / wrong-type / missing |
| — | analyze | `scripts/analyze_graph.py` | read-only: entities, edges, components (both isolate-incl. and connected-subgraph), edge-type distribution, integrity sample |
| — | author new sources | `workflows/05-author-sources.js` | author new corpus notes (prose + GT frontmatter) from a source manifest, WebFetch-verified |

`finalize_recovery.py` is the precision gate on stage 4: it keeps a recovered
edge only if its evidence is a verbatim ≥6-word span of the note prose AND
contains no answer-key "scaffolding" markers (backticks, internal ids,
"declares a"…). This is what keeps GT-guided recovery honest.

## Write safety (LadybugDB)

The build runs `--force`, which unlinks the `.lbug` and bulk-loads into a fresh,
empty consolidated REL table in one pass — the **only** corruption-safe write
shape on this LadybugDB build. **Never** write edges incrementally into a
populated REL table. See `docs/ladybug-graph-sins.md` (sin #4) — the failure it
avoids is real and silent.

## Dependencies / how to run

- **Host graph repo:** the build (`ingest_subagent.py`) monkeypatches the
  extractor in a host graph-RAG project that owns the LadybugDB loader,
  embeddings, and viz (in our setup: `second-brain-hybrid-graph`, public). The
  driver takes `--repo / --vault / --ontology / --extractions`.
- **LadybugDB 0.17.1** (the host repo's venv).
- **Ollama** with `nomic-embed-text` for embeddings.
- **Claude Code Workflow** runtime for the subagent stages.
- **Ontology adapter** `good-dog-ontology-build.yaml`: a copy of the corpus
  ontology with `subclass_of`'s diagonal direction
  (`breed->breed | concept->concept`) rewritten cartesian, because the host
  loader can't parse the diagonal form. (Arguably a host-loader fix, not a
  permanent patch.)

## Caveats (honest)

- Some glue steps (prose-strip for the full corpus, JSONL assembly, recall-input
  regeneration) were run as inline one-offs during the build; the saved scripts
  here are the substantive stages. Paths are currently hardcoded to the author's
  layout — parameterize before reuse elsewhere.
- The residual ~13% recall miss is honest: world-knowledge `located_in` /
  `regulates` edges the prose never states, plus a few **ground-truth errors**
  the extractor correctly declined (e.g. "AKC member_of FCI" — AKC is not an FCI
  member) — i.e. the diagnostic catching bugs in its own answer key.

[kg-ingestion]: model-selection + provider-routing rules (extraction = strong
model / subagent swarm; embeddings = local; never a 3B–14B model for nuanced edges).
