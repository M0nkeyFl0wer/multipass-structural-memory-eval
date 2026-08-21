export const meta = {
  name: 'good-dog-group-c-e-authoring',
  description: 'Author the 8 remaining good-dog corpus sources (Group C Cat-7 dense docs + Group E supplementary) with WebFetch-verified ground-truth frontmatter',
  phases: [ { title: 'Author', detail: 'one agent per source: verify substring, write prose + GT frontmatter' } ],
}
const SOURCES = (typeof args === 'string' ? JSON.parse(args) : args)
if (!Array.isArray(SOURCES)) throw new Error('args not array')

const SCHEMA = {
  type: 'object', required: ['relative_path','note_id','markdown','expected_source_verified','entities','edges','questions'],
  additionalProperties: false,
  properties: {
    relative_path: { type: 'string' },
    note_id: { type: 'string' },
    markdown: { type: 'string', description: 'the COMPLETE note file: YAML frontmatter (--- ... ---) then prose' },
    expected_source_verified: { type: 'boolean' },
    verification_note: { type: 'string' },
    entities: { type: 'array', items: { type: 'object', additionalProperties: true } },
    edges: { type: 'array', items: { type: 'object', additionalProperties: true } },
    questions: { type: 'array', items: { type: 'object', additionalProperties: true } },
  },
}

const ONT = `
ENTITY TYPES: breed, person, organization, publication, concept, product, event, location.
EDGE TYPES (domain->range): authored_by(pub->person), affiliated_with(person->org), member_of(person->org),
  cites(pub->pub), supersedes(pub->pub), contradicts(pub->pub), regulates(org->product|concept),
  subject_of(pub->event|concept), grouped_under(breed->breed), located_in(event|org->location),
  subclass_of(breed->breed|concept->concept), conforms_to(product|pub->pub), source_of(org|pub->pub),
  at_risk_status(breed->concept), alias_of(X->X same type), mentions(pub->*).
REUSE canonical labels + ids for shared entities so notes cross-link: American Kennel Club (org_akc),
  Fédération Cynologique Internationale (org_fci), United Kennel Club (org_ukc), The Royal Kennel Club (org_rkc),
  U.S. Food and Drug Administration (org_fda), Association of American Feed Control Officials (org_aafco),
  American Veterinary Medical Association (org_avma), Centers for Disease Control and Prevention (org_cdc),
  World Small Animal Veterinary Association (org_wsava). Breeds: canonical AKC name (never an alias).`

const FORMAT = `
FRONTMATTER SCHEMA (YAML, between --- fences), matching the existing corpus exactly:
  note_id: <type>_<snake_case>          # e.g. pub_avma_breed_bite_review
  source_url: <url>
  source_title: "<title>"
  source_date: "<YYYY or YYYY-MM-DD>"
  source_publisher: "<publisher>"
  license: fair_use_excerpt
  accessed_on: "2026-06-18"
  domain: <domain>
  # Ontology-aligned entity declarations introduced by this note.
  entities:
    - id: <type>_<snake>     # e.g. org_avma
      type: <entity_type>
      canonical: "<Official Full Name>"
      aliases: ["...", "..."]   # optional
  # Edges introduced by this note (the GROUND TRUTH the graph is measured against).
  edges:
    - from: <entity_id>
      type: <edge_type>
      to: <entity_id>
      evidence: "<verbatim or close quote from the source supporting THIS edge type>"
  tags: [<domain>, ...]
PROSE STRUCTURE (after frontmatter, ~450-700 words): '# <Title>' then sections
  '## Summary', '## What the source reported', '## Why this fits the corpus'
  (name the SME categories it serves), '## Provenance and limitations', '## Sources' (list URLs).
QUESTIONS (1-2): {id, text, expected_sources:[<substrings present in your prose>], min_hops, sme_category,
  and contradiction_pair_id ONLY for cat_3/cat_6}. expected_sources must be substrings you actually wrote.`

const author = (s) => agent(
`Author ONE knowledge-corpus note for the good-dog SME corpus from this source.

SOURCE:
  id: ${s.id}   relative_path: ${s.relative_path}
  url: ${s.url}
  title: ${s.title}
  publisher/date: ${s.publisher} / ${s.date}
  domain: ${s.domain}    target SME categories: ${s.cats}
  tier: ${s.tier}
  REQUIRED expected_source substring (must end up verbatim in your prose): "${s.expected_source}"
  Manifest-verified facts to use (already fact-checked; use these, cite the source): ${s.facts}
  Entity/edge hints: ${s.hints}

STEPS:
1. Use WebFetch on the url to confirm the source and that the REQUIRED substring "${s.expected_source}" appears
   on the live page. Set expected_source_verified=true if confirmed; if the URL is a PDF or unfetchable, author
   from the manifest facts above, set expected_source_verified=false, and explain in verification_note.
   EITHER WAY, include the exact substring verbatim in your prose so the smoke test passes.
2. Write the note (frontmatter + prose) per the format below. Ground-truth edges must be real relationships the
   source supports, each with an evidence quote. Be accurate — these edges are the test answer key.
3. NON-FABRICATION: assert only what the source / manifest facts support. For the grain-free/DCM and breed-bite
   topics, do NOT imply settled causation (FDA states no causal link; CDC disclaims policy use of breed data).
${ONT}
${FORMAT}

Return the structured object: relative_path, note_id, the COMPLETE markdown (frontmatter+prose),
expected_source_verified, verification_note, entities[], edges[], questions[].`,
  { label: s.id, phase: 'Author', schema: SCHEMA, agentType: 'general-purpose' }
)

const results = await parallel(SOURCES.map(s => () => author(s).then(r => ({ id: s.id, r })).catch(() => ({ id: s.id, r: null }))))
const out = []; let ok = 0, ver = 0
for (const x of results.filter(Boolean)) {
  if (!x.r) { out.push({ id: x.id, failed: true }); continue }
  ok++; if (x.r.expected_source_verified) ver++
  out.push({ id: x.id, ...x.r })
}
log(`authored ${ok}/${SOURCES.length} notes; ${ver} substring-verified live`)
return { notes: out, stats: { authored: ok, verified: ver, total: SOURCES.length } }
