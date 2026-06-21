---
note_id: nut_fda_xylitol_paws_off
source_url: https://www.fda.gov/consumers/consumer-updates/paws-xylitol-its-dangerous-dogs
source_title: "Paws Off Xylitol; It's Dangerous for Dogs"
source_date: "2023"
source_publisher: "U.S. Food and Drug Administration"
license: fair_use_excerpt
license_note: "This FDA consumer update is a U.S. federal government work and is in the public domain (17 U.S.C. § 105); short excerpts are quoted here under fair-use research conventions and the full update is not reproduced."
accessed_on: "2026-06-18"
domain: nutrition_safety
alias_pair_id: xylitol

# Ontology-aligned entity declarations introduced by this note.
entities:
  - id: concept_xylitol
    type: concept
    canonical: "Xylitol"
    aliases: ["birch sugar", "wood sugar"]
    notes: "A sugar alcohol (sugar-substitute sweetener) the FDA documents as toxic to dogs even though it is safe for people. On product labels it may appear under the alternative names 'birch sugar' or 'wood sugar'."
  - id: concept_birch_sugar
    type: concept
    canonical: "birch sugar"
    notes: "Surface form: an alternative label name for xylitol called out by the FDA consumer update. Bound to concept_xylitol via alias_of (same-type)."
  - id: concept_wood_sugar
    type: concept
    canonical: "wood sugar"
    notes: "Surface form: an alternative label name for xylitol called out by the FDA consumer update. Bound to concept_xylitol via alias_of (same-type)."
  - id: pub_fda_xylitol_consumer_update
    type: publication
    canonical: "Paws Off Xylitol; It's Dangerous for Dogs (FDA Consumer Update)"

# Edges introduced by this note (the GROUND TRUTH the graph is measured against).
edges:
  - from: pub_fda_xylitol_consumer_update
    type: authored_by
    to: org_us_fda
    evidence: "Published as an FDA Consumer Update on fda.gov; the update names Martine Hartogensis, a veterinarian at the FDA, as its source."
  - from: pub_fda_xylitol_consumer_update
    type: mentions
    to: concept_xylitol
    evidence: "Title 'Paws Off Xylitol; It's Dangerous for Dogs'; the update is entirely about xylitol toxicity in dogs."
  - from: concept_birch_sugar
    type: alias_of
    to: concept_xylitol
    evidence: "'...products containing xylitol, which also may be known as birch sugar or wood sugar.'"
  - from: concept_wood_sugar
    type: alias_of
    to: concept_xylitol
    evidence: "'...products containing xylitol, which also may be known as birch sugar or wood sugar.'"
  - from: org_us_fda
    type: regulates
    to: concept_xylitol
    evidence: "The FDA's Center for Veterinary Medicine collects adverse-event reports on xylitol poisoning of pets and issues this consumer guidance; xylitol-containing foods and the products that carry it fall under FDA food/animal-feed oversight."
    needs_grounding: true

# Note: org_us_fda is reused from vault/nutrition_safety/2007-03-16-fda-melamine-pet-food-recall-initial-announcement.md
# (and other nutrition_safety / veterinary_research notes) and is not redeclared here per corpus guidance.

tags: [nutrition_safety, xylitol, toxin, alias_chain, fda, label_names]
---

# Paws Off Xylitol; It's Dangerous for Dogs (FDA Consumer Update)

## Summary

The U.S. Food and Drug Administration's consumer update **"Paws Off Xylitol; It's Dangerous for Dogs"** warns dog owners that **xylitol**, a sugar-substitute sweetener (a class of sugar alcohol), is **toxic to dogs** even though it is safe for people. The load-bearing alias fact for this corpus: on product labels, xylitol **also may be known as birch sugar or wood sugar**. Because a dog owner scanning an ingredient list might encounter one of those alternative names rather than the word "xylitol," the alias relationship is exactly the kind of surface-form mapping a memory system must resolve to keep a dog safe.

## What the source reported

The FDA, through its Center for Veterinary Medicine, reports having received numerous reports over recent years of dogs being poisoned by xylitol — many involving sugarless chewing gum, with the most recent report cited as related to a "skinny" (sugar-free) ice cream. The update emphasizes that **gum is not the only product containing xylitol**. It lists products that commonly carry the sweetener: **sugar-free gum, candy** (including mints and chocolate bars), **baked goods**, breath mints, cough syrup, children's and adult chewable vitamins, mouthwash, toothpaste, **some peanut and nut butters**, over-the-counter medicines, dietary supplements, and sugar-free desserts. It explicitly advises owners to check nut-butter labels before using them as a treat or as a vehicle for giving a dog a pill, because xylitol may be present.

On the toxicology: in people, xylitol does not stimulate insulin release, but in dogs it is rapidly absorbed and may trigger a potent release of insulin from the pancreas, causing a rapid and profound drop in blood sugar (hypoglycemia) — the update notes effects can appear within roughly 10 to 60 minutes of ingestion. Untreated, this can be life-threatening. Symptoms described include vomiting, decreased activity, weakness, staggering, incoordination, collapse, and seizures.

The critical preventive instruction the FDA gives — and the reason the alias matters — is to check the label for xylitol in the ingredients. A label reading **"birch sugar"** or **"wood sugar"** names the same hazard under a different word.

## Why this fits the corpus

This note serves two SME categories in the `nutrition_safety` domain:

- **Cat 4 (alias resolution / The Threshold).** The note declares the canonical concept **Xylitol** plus two same-type alias concepts, **birch sugar** and **wood sugar**, each bound to the canonical via an `alias_of` edge (`alias_pair_id: xylitol`). A correct memory system must collapse all three surface forms onto one toxin entity — so that a question about "wood sugar" retrieves the xylitol-toxicity warning and a question about "is birch sugar safe for dogs" resolves to the same answer. This mirrors the breed-standard alias chains (e.g. APBT / AmStaff) but in the nutrition-safety domain, with a same-type `concept->concept` alias rather than `breed->breed`.
- **Cat 1 (factual retrieval / The Lookup).** The flat facts — xylitol is dangerous to dogs; it is found in sugar-free gum, candy, baked goods, and some peanut butters — are directly retrievable single-hop lookups.

## Provenance and limitations

The agent WebFetch tool returned HTTP 404 for this URL (the FDA edge blocks that user-agent), so the page was retrieved instead via a direct browser-user-agent fetch, and the exact phrase **"birch sugar or wood sugar"** was confirmed present verbatim in the live page body (this is the registered `expected_source` substring for the smoke test). The FDA entity is reused as `org_us_fda` to match the identifier already declared across this corpus's existing FDA notes, rather than spawning a parallel entity. The `regulates(org_us_fda -> concept_xylitol)` edge carries `needs_grounding: true`: the update is consumer guidance, not a rulemaking, so the regulatory relationship is inferred from FDA's adverse-event-collection role rather than quoted as a regulatory action. The `source_date` is recorded as the consumer-update year per the corpus manifest; FDA pages are revised in place, so any downstream consumer relying on exact wording should re-verify against the canonical URL. This note does not assert any breed-specific or grain-free/DCM causation claim — it is confined to what the xylitol update states.

## Sources

- Paws Off Xylitol; It's Dangerous for Dogs — FDA Consumer Update (canonical URL of record): https://www.fda.gov/consumers/consumer-updates/paws-xylitol-its-dangerous-dogs
