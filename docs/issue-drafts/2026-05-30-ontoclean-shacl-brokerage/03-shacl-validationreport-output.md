**Title:** SHACL — emit Cat 8 / EPC violations in `sh:ValidationReport` vocabulary (no pyshacl dependency, no RDF projection)

**Where this came from.** Same method-coverage review. SHACL is
already in the method — but only as a Tier-1 survey item scoped to
**Cat 4b required-field coverage** via `pyshacl`
(`industry_standards_integration.md:39,69`; `ingestigation.md:60`).
Two problems with where it sits today:

1. **Scoped to the shallowest slice.** Required-field coverage is
   `sh:minCount 1` — the least of what SHACL is for. The part that
   matches *this stack* is `sh:targetClass` + `sh:property` + `sh:class`
   / `sh:node`: "edges of type X must run type A → type B." SME already
   enforces exactly that — **imperatively and scattered** (the EPC /
   grade-locality checks, the declared edge-domain/range in Cat 8). The
   `library-skills` "scripts-as-undeclared-ontology" reference names
   this anti-pattern; SHACL is its declarative home. So SHACL's natural
   target in SME is **Cat 8 + EPC**, not Cat 4b.

2. **The RDF impedance mismatch is undersold.** `pyshacl` (and Apache
   **Jena**'s SHACL engine, and TopBraid) validate **RDF triples via
   SPARQL**. SME's substrates are **property graphs** (LadybugDB /
   Cypher). You cannot point `pyshacl` at a `.ldb` snapshot without
   first projecting it to RDF. The current plan's "single light dep"
   framing hides that projection cost.

**Proposal — the pragmatic middle path.** Decouple the *output
vocabulary* from the *validation engine*. Keep SME's own (fast,
property-graph-native) EPC / Cat 8 checker; have it **emit its
findings in SHACL's `sh:ValidationReport` shape**. You get
interoperable, standard-named output that any SHACL-aware consumer
understands — with **zero** RDF projection and **zero** new
dependency. The property graph stays a property graph; only the report
speaks SHACL.

```json
// Cat 8 / EPC violations, re-expressed as a SHACL ValidationReport
{
  "@context": {"sh": "http://www.w3.org/ns/shacl#"},
  "sh:conforms": false,
  "sh:result": [
    {
      "sh:focusNode": "Entity:token-based-identity",
      "sh:resultPath": "PART_OF",
      "sh:sourceConstraintComponent": "sh:ClassConstraintComponent",
      "sh:resultSeverity": "sh:Violation",
      "sh:value": "Entity:driftwood-project",
      "sh:resultMessage": "PART_OF expects parent in {pattern, system}; got project (grade-locality / EPC)."
    }
  ]
}
```

The mapping from SME's existing checks to SHACL constraint components:

| SME check (today, imperative) | SHACL constraint component |
|---|---|
| EPC edge domain/range (`A --rel--> B` legal types) | `sh:ClassConstraintComponent` (`sh:class`) |
| grade-locality (edge crosses an illegal grade boundary) | `sh:NodeConstraintComponent` (`sh:node`) |
| Cat 4b required field | `sh:MinCountConstraintComponent` (`sh:minCount`) |
| edge cardinality (not yet checked — see below) | `sh:MaxCountConstraintComponent` |

**Optional follow-on (flag, don't adopt yet): a real shapes graph +
engine.** If interop demand grows, the heavier path is: project the
snapshot to RDF and run a stock validator — `pyshacl` (light) or
**Apache Jena**'s SHACL (heavier; bundles RDF store + SPARQL + OWL
inference, so it doubles as the OWL-reasoner path that
`industry_standards_integration.md:215` defers to HermiT/Pellet).
Keep this as a documented Tier-2/3 pointer; the constitution favours
the no-dep report format first.

**Why this is small.** SME already *computes* the violations; this is
a serializer over existing results — a `--report-format shacl` flag on
`sme-eval cat8` (and `check`). No engine, no triples, no SPARQL.
~half day including a golden-file test of the report shape.

**Why this matters.**
- **Interop without lock-in.** Findings become consumable by any SHACL
  tooling / dashboard, and align SME's output with the W3C vocabulary
  it already claims kinship with (`industry_standards_integration.md:256`).
- **It re-homes the SHACL plan** from Cat 4b (trivial) to Cat 8 / EPC
  (where SME's real constraint logic already lives), correcting the
  current mis-scoping.
- **It makes the RDF decision explicit** instead of buried under "light
  dep": report-format now, projection + engine only if interop demand
  justifies it.

**Watch-outs.**
- This is *output conformance*, not *engine conformance* — be precise
  in the spec that SME emits SHACL-shaped reports, it does not run a
  certified SHACL processor. Don't claim "SHACL validation"; claim
  "SHACL-vocabulary violation reports."
- Cardinality (`sh:minCount` / `sh:maxCount`) on edges is something SME
  doesn't check yet — worth noting as a natural next constraint once
  the report format exists, but out of scope for this draft.
- Pairs with draft 02: OntoClean answers "is the shape sound," this
  answers "does the graph obey the shape, reported in the standard
  vocabulary."
