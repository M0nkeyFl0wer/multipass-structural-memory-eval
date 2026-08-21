export const meta = {
  name: 'good-dog-recall-vs-gt',
  description: 'Measure matched edge-recall of the subagent extraction against the corpus ground-truth frontmatter edges, per note + per type',
  phases: [ { title: 'Match', detail: 'one agent per note classifies each GT edge: recovered / diff-type / missing' } ],
}
const NOTES = (typeof args === 'string' ? JSON.parse(args) : args)
if (!Array.isArray(NOTES)) throw new Error('args not array')
const POOL = '/tmp/gd_recall/all_extracted_edges.txt'

const SCHEMA = {
  type: 'object', required: ['gt_total','items'], additionalProperties: false,
  properties: {
    gt_total: { type: 'number' },
    items: { type: 'array', items: {
      type: 'object', required: ['from','type','to','status'], additionalProperties: false,
      properties: {
        from: { type: 'string' }, type: { type: 'string' }, to: { type: 'string' },
        status: { type: 'string', enum: ['recovered','present_diff_type','missing'] },
        matched: { type: 'string', description: 'the extracted edge that matched (or empty)' },
      } } },
  },
}

const match = (n) => agent(
`You are measuring EDGE RECALL of an LLM extraction against a hand-authored ground-truth answer key.

Read the per-note file: ${n.path}
  - "gt_edges": the GROUND-TRUTH edges for note "${n.relative_path}" (each: from, from_aliases, type, to, to_aliases). THIS IS THE ANSWER KEY.
  - "our_edges": the edges OUR extractor produced for this note (source, type, target).
Also read the global pool of ALL extracted edges (across every note): ${POOL}

For EACH ground-truth edge, classify whether our extraction recovered it:
  - "recovered": our extraction contains an edge of the SAME relationship type between the SAME two real-world entities.
      * Entity identity is what matters, NOT label form: match a GT entity to our entity if they are the same real-world thing,
        allowing canonical-vs-alias, acronym-vs-full-name, casing, punctuation, and title paraphrase differences
        (use from_aliases/to_aliases to help). Check our_edges FIRST, then the global pool.
      * For symmetric relations (contradicts, alias_of) a direction flip still counts as recovered.
  - "present_diff_type": our extraction has an edge between the same two entities but with a DIFFERENT relationship type
      (e.g. GT says 'mentions' but we have 'subject_of'; GT says 'regulates' but we have 'mentions'). Endpoints match, type doesn't.
  - "missing": no edge between those two entities exists in our extraction at all.

Be STRICT about entity identity (different real entities = not a match) but LENIENT about label spelling/form.
Set "matched" to the exact extracted edge string you matched against (or "" for missing).

Return gt_total (count of GT edges) and one item per GT edge.`,
  { label: n.relative_path, phase: 'Match', schema: SCHEMA, agentType: 'general-purpose' }
)

const results = await parallel(NOTES.map(n => () => match(n).then(r => ({ rel: n.relative_path, r }))))

// aggregate
const byType = {}
let total = 0, recovered = 0, diff = 0, missing = 0
const missingList = []
for (const x of results.filter(Boolean)) {
  if (!x.r) continue
  for (const it of (x.r.items || [])) {
    total++
    const t = it.type || '?'
    byType[t] = byType[t] || { gt: 0, recovered: 0, diff: 0, missing: 0 }
    byType[t].gt++
    if (it.status === 'recovered') { recovered++; byType[t].recovered++ }
    else if (it.status === 'present_diff_type') { diff++; byType[t].diff++; missingList.push({ rel: x.rel, edge: `${it.from} --${it.type}--> ${it.to}`, status: 'diff_type', matched: it.matched }) }
    else { missing++; byType[t].missing++; missingList.push({ rel: x.rel, edge: `${it.from} --${it.type}--> ${it.to}`, status: 'missing' }) }
  }
}
log(`recall: ${recovered}/${total} exact-type recovered; ${diff} present-but-diff-type; ${missing} missing`)
return { total, recovered, present_diff_type: diff, missing, byType, missingList }
