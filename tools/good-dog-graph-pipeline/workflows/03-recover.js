export const meta = {
  name: 'good-dog-edge-recovery',
  description: 'GT-guided edge recovery: per note, ground the missing ground-truth edges (incl. mentions) in prose and emit them; skip world-knowledge-only edges (non-fabricating)',
  phases: [ { title: 'Recover', detail: 'per note: verify each missing GT edge against prose, emit grounded additions' } ],
}
const NOTES = (typeof args === 'string' ? JSON.parse(args) : args)
if (!Array.isArray(NOTES)) throw new Error('args not array')

const ENTITY_TYPES = ['breed','person','organization','publication','concept','product','event','location']
const EDGE_TYPES = ['mentions','alias_of','supersedes','contradicts','cites','authored_by','affiliated_with','regulates','subject_of','member_of','grouped_under','located_in','subclass_of','conforms_to','source_of','at_risk_status']

const SCHEMA = {
  type: 'object', required: ['entities','edges'], additionalProperties: false,
  properties: {
    entities: { type: 'array', items: {
      type: 'object', required: ['label','type'], additionalProperties: false,
      properties: { label:{type:'string'}, type:{type:'string',enum:ENTITY_TYPES}, description:{type:'string'}, confidence:{type:'number'} } } },
    edges: { type: 'array', items: {
      type: 'object', required: ['source','target','type','evidence'], additionalProperties: false,
      properties: { source:{type:'string'}, target:{type:'string'}, type:{type:'string',enum:EDGE_TYPES}, evidence:{type:'string'}, confidence:{type:'number'} } } },
  },
}

const recover = (n) => agent(
`You are RECOVERING missing knowledge-graph edges for one note, guided by an answer key, WITHOUT fabricating.

Read:
  1. The note prose: ${n.prose_path}   (note "${n.relative_path}")
  2. The recall file: ${n.recall_file}  — it has:
       "gt_edges": the ground-truth edges a human author asserts for this note (from, type, to, with from_aliases/to_aliases). THE ANSWER KEY.
       "our_edges": the edges our extractor already produced (source, type, target). DO NOT re-emit these.

Your job: for each gt_edge that is NOT already in our_edges (compare by same endpoints + type, allowing label/alias/case variants),
decide if THE PROSE supports it:
  - If you can find a VERBATIM quote in the prose that semantically supports that exact relationship type between those two
    entities -> EMIT the edge, with the quote in "evidence".
  - If the relationship is only world-knowledge / NOT stated in this note's prose (many 'regulates' and 'located_in' edges are
    like this) -> SKIP it. Do NOT invent evidence. A skipped edge is correct; a fabricated one is a bug.
  - This explicitly INCLUDES 'mentions' edges (a publication mentions an entity): emit the gt 'mentions' edges the prose supports
    (the entity's canonical name or a registered alias appears in the prose).

Entity labels: REUSE the exact label our_edges already use for an entity that exists; for a genuinely new entity, use its
canonical full name (expand acronyms: FDA -> "U.S. Food and Drug Administration", AKC -> "American Kennel Club", etc.; breeds
use canonical, never an alias). Every edge endpoint must appear in your entities[] list. Allowed edge types: ${EDGE_TYPES.join(', ')}.
Respect domain->range direction.

Return ONLY the ADDITIONS (new entities + newly-grounded edges). Empty arrays are fine if nothing new is groundable.`,
  { label: n.relative_path, phase: 'Recover', schema: SCHEMA, agentType: 'general-purpose' }
)

const results = await parallel(NOTES.map(n => () => recover(n).then(r => ({ rel: n.relative_path, r }))))
const out = []; let nE=0, nG=0, fail=0
for (let i=0;i<NOTES.length;i++){
  const x = results[i]
  if (!x || !x.r) { fail++; out.push({relative_path:NOTES[i].relative_path, entities:[], edges:[]}); continue }
  const ents=x.r.entities||[], edges=x.r.edges||[]
  nE+=ents.length; nG+=edges.length
  out.push({relative_path:x.rel, entities:ents, edges:edges})
}
log(`recovery: +${nG} grounded edges, +${nE} entity-mentions across ${out.length} notes (${fail} failed)`)
return { notes: out, stats: { added_edges:nG, added_entities:nE, failed:fail } }
