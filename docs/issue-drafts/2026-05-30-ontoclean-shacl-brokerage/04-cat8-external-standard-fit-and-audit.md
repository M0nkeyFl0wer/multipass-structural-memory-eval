**Title:** Cat 8 — external-standard ontology fit → auto-generated audit → counterfactual re-projection

**Where this came from.** A step-back on the same method-coverage
review. Drafts 02 (OntoClean) and 03 (SHACL) both deepen Cat 8, but
both share a hidden assumption: that the *spec to check against* is
already in hand. OntoClean needs hand-tagged rigidity/identity per
type; SHACL needs hand-written shapes; today's Cat 8 drift (8d) checks
against the **README's** declared ontology. Every yardstick is one the
maintainer authored. The question none of them asks: **is the declared
ontology the right one for this corpus in the first place — and if a
standard fits better, can that standard *supply* the spec the other
checks need?**

**The three axes of Cat 8.** Stating them plainly exposes the gap:

| Axis | Question | Status |
|---|---|---|
| Internal coherence | Does the graph match what it says about itself? | ✅ 8a–8e (`ontology_coherence.py`) |
| Logical soundness | Is the declared taxonomy well-formed? | drafted — 8g OntoClean (draft 02) + SHACL (draft 03) |
| **External fit** | **Does the ontology match what published standards say this domain looks like?** | **missing — this draft** |

The first two can both pass on an ontology that is internally tidy,
logically sound by OntoClean, SHACL-conformant — and *wrong for the
corpus*. A graph where every authored thing is one flat `publication`
type passes 8a–8e and 8g (OntoClean) cleanly while silently collapsing the
ScholarlyArticle / Legislation / recall-notice distinctions the domain
has standard names for. Internal coherence cannot see that, because the
README is both the claim and the yardstick.

**The dependency inversion (why this is the organizing draft).** The
gap closes by adding the one yardstick that isn't self-authored — a
published standard — and then letting it *feed the other two checks*:

```
corpus ──align──▶ best-fit standard ontology O
                    ├─▶ O's rigid/role/kind tags (UFO/BFO)        ─▶ feeds OntoClean 8g (no hand-tagging)
                    ├─▶ O's domain/range/cardinality/disjointness ─▶ generates SHACL shapes (no hand-writing)
                    └─▶ O's class + property vocabulary            ─▶ Cat 8 drift measured vs STANDARD, not README
                              └─ run audit ──▶ sh:ValidationReport (draft 03's shape)
                              └─ re-type facts under O ──▶ structural deltas (the counterfactual)
```

So draft 04 is not a fourth feature bolted on — it is the **source**
the OntoClean/SHACL drafts consume. Their hand-authored specs become
the **fallback** for the case where no standard aligns (a genuinely
novel domain). When a standard *does* align, the audit is turnkey on a
corpus the maintainer has never hand-specced.

---

**The reference set.** There is no single "most relevant" ontology;
fit is corpus-relative, so the check declares a *reference set* and
reports it (a silent choice of reference is a lie factor — the result
is only meaningful relative to what it was measured against):

- **Upper / foundational** — UFO (Guizzardi; built directly on
  OntoClean's rigidity/identity meta-properties), BFO, DOLCE. Aligning
  here *derives* the 8g meta-property tags instead of hand-authoring
  them.
- **General web standards** (the default baseline) — schema.org, FOAF
  (people/orgs), SKOS (concept schemes), Dublin Core (documents),
  PROV-O (provenance), OWL-Time (temporal). For citation edges
  specifically, CiTO is the domain-standard.
- **Domain ontologies** — swapped in when the corpus domain is known.

**What alignment produces — three fit outcomes per declared type/edge:**

1. **Mappable** — corpus type ↔ standard class at matching
   granularity. Good. (`person` → schema.org `Person`; `event` →
   schema.org `Event`; `mentions` → schema.org `mentions` — an exact
   hit.)
2. **Under-specified** — one corpus type spans several standard
   classes → the system is collapsing distinctions the world has
   standard names for. This is the `concept`-absorbs-everything failure
   quantified against an *external* yardstick instead of just 8c
   entropy. (good-dog's `publication` = "Study, article, bylaw, recall
   notice" spans schema.org `ScholarlyArticle` / `Legislation` /
   government-notice — one type, four standard classes.)
3. **Idiosyncratic** — no standard analog → either genuine domain
   knowledge or accidental noise; flag for a human, never auto-remap.
   (good-dog's `breed` and `regulates` have no clean general-standard
   class; that's a legitimate result, not a failure — but it must be
   *named* so it doesn't hide in an "everything aligned" summary.)

**Worked example — alignment surfaces an overloaded edge for free.**
good-dog's `member_of` is self-flagged in `ontology.yaml` as "Reused
across two relationship shapes; flagged for review in v0.2"
(`breed -> breed` OR `person -> organization`). Standard alignment
*derives* that finding mechanically: the edge maps to **two** distinct
standard properties — SKOS `broader` (breed-group membership) and
schema.org `memberOf` (person–org) — which is the signature of an
overloaded edge type. The maintainer's manual TODO becomes a
reproducible diagnostic.

**Seen in the wild — the under-specified outcome, found by hand (issue
#45).** jphein's MemPalace full-graph re-measurement (#45, 2026-05-31)
found a deterministic predicate normalizer collapsing **~55% of all
edges into a generic `other` sink** (later cut to 27% by hand-expanding
the synonym map and dropping ~48K junk predicates). That `other` 55% is
*exactly* outcome 2 — one edge type absorbing distinctions a standard
relation vocabulary has names for — but it was caught and fixed
manually. `8f_external_fit` against a relation standard would have
flagged it automatically: a 55%-mass bucket that aligns to no single
standard property is the textbook under-specification signal. This is a
stronger worked example than `member_of`, and it's real, not seeded.

---

**The counterfactual (the part that makes this SME-shaped, not a
librarian audit).** Alignment alone yields a fit *score*. The stronger
test re-uses the structural probes SME already has: once you have a
`corpus-type → standard-type` mapping, **re-type the same facts under
O and re-run the probes** — Cat 2/2c reachability, Cat 5 topological
holes, Cat 7 / B-Cubed. Did fixing the ontology actually change
multi-hop reachability, open or close holes, move recall?

This is precisely the *"ablation on a multi-relation graph"* the
brokerage-on-CKG result concluded was the right test (brokerage didn't
predict recall because recall was dominated by hop depth — the clean
experiment is to vary the relation typing and measure the structural
consequence). Re-typing to a **published** relation vocabulary is a
principled relation ablation — the alternative typing isn't arbitrary,
it's a standard. That defensibility is exactly what the CKG brokerage
test lacked.

**Sibling of issue #45, and dependent on its precondition.** #45 asks
the same question from the other side — how much do Cat 4/5 readings
move under *different ontology granularities* (flat / moderate /
fine-grained). The counterfactual here is the **principled instance**:
it varies typing toward a *published standard* rather than arbitrary
granularities. They are the same re-projection harness and should be
built once, not twice. **Hard precondition (jphein, #45):** the base
reading must be computed over the *full* graph (or an explicitly
uniform sample), never an order-dependent `LIMIT N` / scaffold-padded
projection. jphein's MemPalace case showed a tunnel-swamped projection
inverting Cat 8 from FAIL (modularity 0.009) to PASS (0.796) — a
counterfactual delta measured on such a projection would be projection
noise, not ontology fit.

---

**The hard honesty constraint — confidence gates rule application.**
The audit is only as good as the alignment. Audit against a *guessed*
standard and you emit false violations. So:

- **high-confidence** mapping → rule fires as a **violation**
- **low-confidence** mapping → rule fires as **informational only**
- every emitted rule carries **provenance**: `"required by schema.org
  (alignment conf 0.91)"` vs `"declared in README"`.

A guessed audit must never read as a clean one — same posture as 8g's
`typed_coverage` and the reference-set disclosure above.

---

**Proposal — scope.** Two phases; only Phase 1 is in scope for the
first PR.

**Phase 1 — thin vertical slice: PROV-O + OWL-Time.** These two W3C
standards map onto fields SME *already* tracks (`_created_by`,
`_created_at`; the event `timestamp` field), and 8e already checks
their coverage (`ontology_coherence.py` temporal/provenance claim
branches). So the slice proves the inversion end-to-end without the
messy general-alignment problem:

- A new sub-check (`8f_external_fit`) that (a) aligns provenance/
  temporal edges and fields to PROV-O / OWL-Time terms
  (`authored_by` → `prov:wasAttributedTo`; `supersedes` →
  `prov:wasRevisionOf`; `_created_at` / event `timestamp` →
  `time:inXSDDateTime`), (b) auto-generates the conformance checks from
  those standards' constraints, (c) emits results in draft 03's
  `sh:ValidationReport` shape with per-rule provenance + confidence.
- Reports `aligned_coverage`, lists `unaligned_types`, and the chosen
  reference set — coverage-honest like 8g.
- Adapter-agnostic: consumes `entities` / `edges` / `structural_health`
  like `score_cat8`. Extends `Cat8Report.to_dict` **additively** (new
  `8f_external_fit` key, nothing renamed).

Report shape (additive):

```json
{
  "8f_external_fit": {
    "reference_set": ["prov-o", "owl-time"],
    "aligned_coverage": 0.62,
    "unaligned_types": ["breed", "regulates"],
    "alignments": [
      {"corpus_term": "authored_by", "standard_term": "prov:wasAttributedTo",
       "confidence": 0.93, "outcome": "mappable"},
      {"corpus_term": "supersedes", "standard_term": "prov:wasRevisionOf",
       "confidence": 0.71, "outcome": "mappable"}
    ],
    "audit": {
      "@context": {"sh": "http://www.w3.org/ns/shacl#"},
      "sh:conforms": false,
      "sh:result": [
        {"sh:focusNode": "Edge:authored_by",
         "sh:resultSeverity": "sh:Violation",
         "sh:resultMessage": "prov:wasAttributedTo expects a prov:Agent target; 12/40 targets are not type person/organization.",
         "provenance": "PROV-O (alignment conf 0.93)"}
      ]
    }
  }
}
```

**Phase 2 — documented follow-ups (out of scope for the first PR):**
schema.org / FOAF / SKOS / Dublin Core / CiTO alignment; upper-ontology
(UFO/BFO) alignment to auto-derive the 8g tags; the full counterfactual
re-projection harness. Each depends on Phase 1 landing first.

---

**Why this is small (Phase 1).** No new dependency, no RDF projection,
no SHACL engine — PROV-O / OWL-Time term sets are tiny and can ship as
a static mapping table; the audit reuses draft 03's report serializer;
the fields are already extracted. The genuinely new code is the
alignment table + the confidence-gated rule emitter. Comparable in size
to draft 01.

**Why this matters.** It's the only Cat 8 axis whose yardstick the
maintainer didn't write — so it's the only one that can catch "this
ontology is coherent and sound but wrong for the domain." And via the
inversion it makes drafts 02/03 turnkey: a standard, once aligned,
*generates* the OntoClean tags and SHACL shapes they currently demand
by hand. No prior-art benchmark in the spec (KGGen MINE, GraphRAG-Bench,
the Structural Quality Metrics paper) compares a built graph to a
*standard reference ontology* and re-derives structure from the remap.

**Watch-outs.**
- **Verify prior-art names before asserting them.** Ontology alignment
  is an established field (OAEI / LogMap / AML lineage) — confirm exact
  names, serializations, and any quoted specifics via web search before
  putting them in the upstream issue; do not quote from memory (per the
  cite-primary-source discipline). This draft names them as a *pointer
  to verify*, not as established fact.
- **Output conformance, not engine conformance** (inherited from draft
  03): SME emits SHACL-vocabulary reports against an aligned standard;
  it does not run a certified SHACL processor. Claim "standard-aligned
  fit + violation report," never "SHACL validation against schema.org."
- **Alignment is error-prone** — hence the confidence gate. Same
  posture as `taxonomy-validation`: surface consequences, human
  decides, never auto-remap.
- **Reference-set disclosure is load-bearing** — every score is
  relative to the set it was measured against; report it on every run.
- **Faithful base read before any counterfactual** (jphein, #45) — run
  the probes over the full graph / uniform sample, never an
  order-dependent projection, or the delta measures sampling bias.
- Pairs with 02 (OntoClean: derive the tags) and 03 (SHACL: the report
  vocabulary this audit emits into).
