export const meta = {
  name: 'good-dog-entity-resolution',
  description: 'Stage-8 entity resolution: per-type LLM clustering of co-referent labels (conservative, merge-only) over the good-dog v0.3 graph',
  phases: [ { title: 'Resolve', detail: 'one agent per entity type clusters same-entity labels' } ],
}

const TYPES = (typeof args === 'string' ? JSON.parse(args) : args)  // [{type, path, n}]
if (!Array.isArray(TYPES)) throw new Error('args not array: ' + typeof args)

const SCHEMA = {
  type: 'object', required: ['clusters'], additionalProperties: false,
  properties: {
    clusters: { type: 'array', items: {
      type: 'object', required: ['canonical','members'], additionalProperties: false,
      properties: {
        canonical: { type: 'string', description: 'the chosen canonical label (official full name; expand acronyms)' },
        members: { type: 'array', items: { type: 'string' }, description: 'all labels that are the SAME entity, including the canonical; length >= 2' },
        reason: { type: 'string' },
      } } },
  },
}

const GUARD = `
You are doing ENTITY RESOLUTION for a knowledge graph. You merge labels that are the SAME real-world entity
written differently (variant titles, abbreviations, casing, acronym vs full name).

MERGE ONLY when the two labels are UNAMBIGUOUSLY the same single real-world entity. Examples of correct merges:
  - "U.S. Food and Drug Administration" + "FDA" + "Food and Drug Administration"
  - "Mech 1999 - Alpha status, dominance, and division of labor in wolf packs" + "Mech 1999 - Alpha status in wolf packs"  (same paper)
  - "American Staffordshire Terrier" + "AmStaff"
Pick the most complete/official label as canonical (expand acronyms to full names).

NEVER MERGE entities that are genuinely different, even if closely related. HARD must-NOT-merge cases:
  - Distinct breeds: "American Pit Bull Terrier" must stay separate from "American Staffordshire Terrier".
  - Contradiction / supersession pairs are DIFFERENT publications: "Schenkel 1947" must NOT merge with "Mech 1999".
  - Different temporal versions are DIFFERENT entities: a 2018 report vs a 2019 report; "Montreal 2016 enactment" vs
    "Montreal 2018 repeal" (they have supersedes edges between them — merging would destroy the temporal chain).
  - Different organizations that share a parent or topic. Different products/SKUs. Different events on different dates.
When in doubt, DO NOT merge. A missed merge is harmless; a wrong merge is unrecoverable and destroys real distinctions.

Output ONLY clusters with >= 2 members (the merges). Singletons need not be reported.`

const resolve = (t) => agent(
`Read the candidate entity list (JSON array of {label, description, count}) at: ${t.path}
These are ${t.n} distinct entities of type "${t.type}" extracted from a dog-domain corpus.

${GUARD}

Cluster the labels of type "${t.type}" that are the same real-world entity. Return only merge clusters (>=2 members each),
each with a canonical label and the full member list.`,
  { label: `resolve:${t.type}`, phase: 'Resolve', schema: SCHEMA, agentType: 'general-purpose' }
)

const results = await parallel(TYPES.map(t => () => resolve(t).then(r => ({ type: t.type, clusters: (r && r.clusters) || [] }))))

const out = []
let nClusters = 0, nMerged = 0
for (const r of results.filter(Boolean)) {
  for (const c of r.clusters) {
    if (!c.members || c.members.length < 2) continue
    nClusters++
    nMerged += c.members.length - 1
    out.push({ type: r.type, canonical: c.canonical, members: c.members, reason: c.reason || '' })
  }
}
log(`resolution: ${nClusters} merge clusters, ${nMerged} labels folded into canonicals`)
return { clusters: out, stats: { clusters: nClusters, labels_folded: nMerged } }
