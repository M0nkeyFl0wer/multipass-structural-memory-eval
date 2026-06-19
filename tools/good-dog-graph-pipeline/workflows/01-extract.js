export const meta = {
  name: 'good-dog-v3-extract',
  description: 'Subagent-swarm edge extraction over the 54-note good-dog v0.3 corpus (extract -> adversarial review), ontology-constrained, evidence-quoted',
  phases: [
    { title: 'Extract', detail: 'one agent per note: entities + typed edges from prose' },
    { title: 'Review', detail: 'adversarial prune: evidence must support edge type + domain/range' },
  ],
}

const NOTES = (typeof args === 'string' ? JSON.parse(args) : args)  // [{idx, relative_path, prose_path, ...}]
if (!Array.isArray(NOTES)) throw new Error('args did not resolve to an array: ' + typeof args)

const ENTITY_TYPES = ['breed','person','organization','publication','concept','product','event','location']
const EDGE_TYPES = ['mentions','alias_of','supersedes','contradicts','cites','authored_by','affiliated_with','regulates','subject_of','member_of','grouped_under','located_in','subclass_of','conforms_to','source_of','at_risk_status']

const SCHEMA = {
  type: 'object',
  required: ['entities','edges'],
  additionalProperties: false,
  properties: {
    entities: { type: 'array', items: {
      type: 'object', required: ['label','type'], additionalProperties: false,
      properties: {
        label: { type: 'string', description: 'canonical full name (expand acronyms; apply alias registry)' },
        type: { type: 'string', enum: ENTITY_TYPES },
        description: { type: 'string' },
        confidence: { type: 'number' },
      } } },
    edges: { type: 'array', items: {
      type: 'object', required: ['source','target','type','evidence'], additionalProperties: false,
      properties: {
        source: { type: 'string', description: 'source entity label, must match an entity label exactly' },
        target: { type: 'string', description: 'target entity label, must match an entity label exactly' },
        type: { type: 'string', enum: EDGE_TYPES },
        evidence: { type: 'string', description: 'verbatim quote from the prose that supports THIS edge type' },
        confidence: { type: 'number' },
      } } },
  },
}

const ONTOLOGY = `
ENTITY TYPES (use exactly one per entity):
  breed         - a recognized dog breed or breed group (incl. breed-group nodes like "Herding Group")
  person        - named individual (researcher, vet, trainer, journalist, official)
  organization  - kennel club, university, vet body, municipality, regulator, manufacturer
  publication   - a study, article, bylaw, recall notice, standard, registry/dataset, report (anything authored)
  concept       - idea/methodology/status (dominance theory, positive reinforcement, BSL, "at-risk")
  product       - a specific commercial product/brand/SKU
  event         - recall announcement, council vote, study publication, attack incident
  location      - city, park, shelter, jurisdiction

EDGE TYPES (direction = domain -> range; emit ONLY edges whose endpoints match the direction):
  authored_by      publication -> person
  affiliated_with  person -> organization        (CURRENT standing, not candidacy)
  member_of        person -> organization        (CURRENT membership, not "running for")
  cites            publication -> publication     (explicit scholarly reference)
  supersedes       publication -> publication     (newer replaces older; needs explicit marker: "replaces/withdrawn/supersedes/no longer current")
  contradicts      publication -> publication     (incompatible claims on the same subject)
  regulates        organization -> product|concept (source org must hold jurisdictional authority)
  subject_of       publication -> event|concept   (the document's PRIMARY topic, not a passing mention)
  grouped_under    breed -> breed                 (registry breed-group membership, e.g. German Shepherd -> Herding Group)
  subclass_of      breed->breed | concept->concept (formal is-a / logical subsumption, e.g. an ontology DL hierarchy)
  conforms_to      product|publication -> publication (validated against a named standard, e.g. food -> AAFCO profile)
  source_of        organization|publication -> publication (a registry/dataset is a declared data source of a downstream aggregator)
  at_risk_status   breed -> concept               (a breed carries a conservation/risk category, the category is a concept)
  located_in       event|organization -> location
  alias_of         X -> X (SAME entity type)      (two surface forms of the SAME entity; use SPARINGLY, only for clear registry aliases)
  mentions         publication -> *               (LAST RESORT only — a bare reference with no more specific relation; keep < 15% of edges)

CANONICAL LABEL NORMALIZATION (critical — cross-note entity merge depends on it):
  - Always use the entity's official FULL name as the label. Expand acronyms:
      FDA -> "U.S. Food and Drug Administration"; AVMA -> "American Veterinary Medical Association";
      AKC -> "American Kennel Club"; FCI -> "Fédération Cynologique Internationale";
      AAFCO -> "Association of American Feed Control Officials"; WSAVA -> "World Small Animal Veterinary Association";
      UKC -> "United Kennel Club"; AVSAB -> "American Veterinary Society of Animal Behavior";
      CDC -> "Centers for Disease Control and Prevention".
  - Breed alias registry (use the canonical, never the alias as label):
      "German Shepherd"  <- GSD, Alsatian, German Shepherd Dog
      "American Pit Bull Terrier" <- Pit Bull, APBT, Pitbull  (do NOT merge with American Staffordshire Terrier)
      "Golden Retriever" <- Goldie, Golden
  - For a publication, prefer a stable descriptive title incl. author+year when present
    (e.g. "Mech 1999 - Alpha status in wolf packs", "2019 FDA DCM third status report").
`

const RULES = `
EXTRACTION DISCIPLINE (kg-ingestion model-selection + edge-discipline rules):
  1. Extract REAL-WORLD domain entities and relationships only. IGNORE corpus-design / SME meta-language:
     "this note", "next note", "seeded in this corpus", "Cat 3 / Cat 6 chain", "origin node",
     "sources/*.yaml", category labels. Those describe the test harness, not the domain. Never make them entities/edges.
  2. EVERY edge needs an "evidence" field: a VERBATIM quote from the prose that SEMANTICALLY SUPPORTS that exact edge type.
     A quote that merely co-mentions two entities is NOT evidence for a typed relation. A "supersedes" quote must contain a
     replacement marker; a "contradicts" quote must show opposed claims; an "authored_by" quote must show authorship.
     If you cannot quote support, DROP the edge.
  3. Respect direction (domain -> range) exactly. Do not emit an edge whose endpoint types violate it.
  4. No fabrication. Do not invent entities or relations not grounded in THIS note's prose.
  5. source/target of every edge MUST exactly match a label in your entities[] list (same canonical string).
  6. confidence: 0.9 explicit/stated outright; 0.7 clearly implied; 0.5 inferred. Prefer 0.5 over guessing.
  7. mentions is a last resort (<15% of edges). Prefer a specific typed edge whenever one fits.
`

const extract = (note, idx) => agent(
`You are extracting a knowledge graph from ONE document's prose for the good-dog corpus.

Read the document prose with the Read tool: ${note.prose_path}
(This is the note "${note.relative_path}". Its YAML frontmatter has already been removed — you see only prose.)

${ONTOLOGY}
${RULES}

Extract:
  - entities: every real-world domain entity the prose discusses, with its type and a one-line description.
  - edges: every typed relationship the prose ASSERTS between two of those entities, each with a verbatim evidence quote.

Return ONLY the structured object. Be thorough but precise — an unsupported edge is worse than a missing one.`,
  { label: note.relative_path, phase: 'Extract', schema: SCHEMA, agentType: 'general-purpose' }
)

const review = (draft, note, idx) => {
  if (!draft) return null
  return agent(
`You are an ADVERSARIAL reviewer for knowledge-graph edges extracted from one document.

The document prose is at: ${note.prose_path}  (note "${note.relative_path}"). Read it.

Here is a draft extraction to audit:
ENTITIES:
${JSON.stringify(draft.entities, null, 0)}
EDGES:
${JSON.stringify(draft.edges, null, 0)}

${ONTOLOGY}
${RULES}

Your job — return a CLEANED extraction:
  - DROP any edge whose "evidence" quote does not semantically support its edge type (co-mention is not support).
  - DROP any edge that is not actually present verbatim-supportable in the prose (re-check the quote is real).
  - DROP any edge violating the domain->range direction, or FIX its type if a valid type clearly applies.
  - DROP entities/edges that are corpus-design meta ("this note", category labels, sources/*.yaml), not domain facts.
  - NORMALIZE labels to the canonical full names / alias registry above; ensure every edge source/target matches an entity label.
  - Keep all well-supported entities and edges. Do not add new unsupported edges.

Return ONLY the cleaned structured object (entities + edges).`,
    { label: note.relative_path, phase: 'Review', schema: SCHEMA, agentType: 'general-purpose' }
  )
}

const results = await pipeline(NOTES, extract, review)

const out = []
let nEnt = 0, nEdge = 0, nFail = 0
for (let i = 0; i < NOTES.length; i++) {
  const r = results[i]
  if (!r) { nFail++; out.push({ relative_path: NOTES[i].relative_path, entities: [], edges: [], failed: true }); continue }
  nEnt += (r.entities || []).length
  nEdge += (r.edges || []).length
  out.push({ relative_path: NOTES[i].relative_path, entities: r.entities || [], edges: r.edges || [] })
}
log(`extraction complete: ${out.length} notes, ${nEnt} entities, ${nEdge} edges, ${nFail} failed`)
return { notes: out, stats: { notes: out.length, entities: nEnt, edges: nEdge, failed: nFail } }
