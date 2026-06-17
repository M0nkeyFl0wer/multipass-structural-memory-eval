**Title:** Cat 8 — add OntoClean meta-property validation (is the *declared* taxonomy coherent?)

**Where this came from.** Same method-coverage review. Cat 8
(`ontology_coherence.py`) checks **declared-vs-actual**: do the types
and edges the README/schema *claims* actually appear in the graph
(8a–8e: type coverage, edge vocabulary, schema-data alignment, drift,
claim verification). It never checks whether the declared taxonomy is
**logically sound** in the first place. The new `taxonomy-validation`
skill (OntoClean: rigidity / identity / unity) is exactly that missing
layer, and it explicitly notes that EPC / grade-locality violations
are often *symptoms* of an unsound taxonomy, not independent bugs.

The clean framing:

> **OntoClean** (is the ontology coherent?) → **SHACL** (does the graph
> obey it?) → **Cat 8 drift** (has it decayed since?).

SME has the third, plans the second (draft 03), is missing the first.

**The gap, concretely.** Cat 8 will happily certify a taxonomy where a
*role* masquerades as a *kind*. Example with this stack's vocabulary:
if `pattern` is anti-rigid (`~R` — an entity can stop being a pattern)
and `project` is rigid (`+R` — a project is essentially a project for
its whole life), then:

- `pattern --IMPLEMENTS--> project` is fine.
- `project --PART_OF--> pattern` (subsuming a rigid kind under an
  anti-rigid role) is an **OntoClean violation** — and it's the
  *structural reason* an EPC / grade-locality check keeps flagging
  those edges. Today SME *counts* the violations; OntoClean *explains
  why they're violations*, which tells the maintainer whether to fix
  the extractor or widen the schema.

**Proposal.** A new Cat 8 sub-check (`8g`, OntoClean), not a new
category. The 80/20 from the skill is two meta-property tags per type
and two checks per subsumption edge:

1. Tag each declared `entity_type` with **Rigidity** (`+R` / `~R`) and
   **Identity** (`+I` sortal / `-I` non-sortal). Source the tags from a
   small sidecar (so they live *with* the ontology, not in code):

   ```yaml
   # ontology meta-properties (sidecar to schema / ontology.yaml)
   entity_types:
     person:  { rigidity: "+R", identity: "+I" }
     project: { rigidity: "+R", identity: "+I" }
     pattern: { rigidity: "~R", identity: "+I" }   # a role
     concept: { rigidity: "~R", identity: "-I" }
   ```

2. For each subsumption-like edge (`IS_A`, `PART_OF`, `SUBCLASS_OF` —
   whichever the declared edge vocab marks as taxonomic), normalize to
   *parent-over-child* and check:
   - **Rigidity rule:** `~R` parent over `+R` child = **forbidden**
     (a role can't be the kind of a thing).
   - **Identity rule:** `-I` parent over `+I` child = **forbidden**;
     parent/child with *incompatible* identity criteria can't be in an
     is-a relation at all.

Report shape (additive):

```json
{
  "8g_ontoclean": {
    "typed_coverage": 0.85,            // fraction of declared types tagged
    "violations": [
      {"edge_type": "PART_OF", "parent": "pattern", "child": "project",
       "rule": "rigidity", "detail": "~R parent over +R child",
       "instances": 142}
    ],
    "untagged_types": ["hall", "drawer"]
  }
}
```

Human reading (mechanism language, per the skill):

```
● OntoClean: 1 subsumption rule violated. `pattern` (~R, a role) sits
  as a PART_OF parent over `project` (+R, a kind) on 142 edges. A role
  can't be the kind of a thing — this is why those edges recur as EPC
  violations. Fix: re-type the edge, or re-tag `pattern` if it's
  actually rigid here.
```

**Why this is the right scope.** It's a *deepening of Cat 8*, reusing
the declared-ontology loader Cat 8 already has. It does **not** try to
auto-correct — it surfaces the consequence of a type choice and a
human decides (identical posture to `taxonomy-validation`, which
forbids auto-delete). Unity (`~U` cannot subsume `+U`) is an optional
third check; Dependence is explicitly deferred (lowest yield).

**Why this matters.** It connects two things SME currently treats as
unrelated: *declared-ontology coherence* and *recurring EPC / grade
violations*. Right now a maintainer sees "14.5K EPC violations" as a
count to grind down. OntoClean reframes a chunk of them as a single
unsound subsumption decision — fix one type tag, a whole violation
class explains itself. That's leverage the current Cat 8 can't give.

**Watch-outs.**
- "Direction is the #1 mistake" (per the skill): always normalize to
  parent-over-child before applying the rule. Pin it with the worked
  examples in `taxonomy-validation/references/ontoclean.md`.
- Coverage honesty: report `typed_coverage` and list `untagged_types`
  so an under-tagged ontology reads as "incomplete check," never as
  "clean."
- Don't require RDF/OWL — this runs on the declared type list + edge
  vocab SME already parses. (The OWL-reasoner path — HermiT/Pellet — is
  the heavier, deferred version; see draft 03.)
