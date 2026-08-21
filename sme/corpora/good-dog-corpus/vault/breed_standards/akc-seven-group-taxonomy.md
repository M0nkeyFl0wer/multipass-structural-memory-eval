---
note_id: breed_akc_seven_groups
source_url: https://www.akc.org/public-education/resources/general-tips-information/dog-breeds-sorted-groups/
source_title: "AKC List of Breeds by Group (seven groups)"
source_date: "2026-06-17"
source_publisher: "American Kennel Club"
license: other
license_note: "American Kennel Club registry/taxonomy content. Not a U.S. government work; AKC.org terms of use apply. Short factual excerpts (group names, the Herding-Group founding year, group-count statements) are quoted under fair use for non-commercial research and evaluation; the full page is not reproduced. source_date reflects the access date — the page is undated boilerplate maintained by AKC."
accessed_on: "2026-06-17"
domain: breed_standards

# Cat 8 CANONICAL taxonomy note. The seven AKC groups are each authored as a
# breed-typed entity (the ontology treats a breed grouping as a recognized
# breed). The taxonomy publication carries the EXACT id pub_akc_group_taxonomy
# so cross-taxonomy `contradicts` edges (FCI-10, UK-KC-7) can be wired against
# it in assembly. Reuses org_akc from the existing breed_standards notes.
# Example breeds connect to their group via `grouped_under` (NOT member_of_group).
entities:
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "U.S. national breed registry, founded 1884. Publishes the canonical seven-group breed taxonomy. Not regulatory in the FDA sense; holds private-association registry authority. (Already declared in akc-german-shepherd-dog.md and fci-akc-kennel-club-comparative-structure.md; reused here.)"
  - id: pub_akc_group_taxonomy
    type: publication
    canonical: "AKC List of Breeds by Group (seven-group taxonomy)"
    notes: "The canonical external standard for Cat 8 SHACL-style conformance and counterfactual re-projection. Stable id; cross-taxonomy contradicts edges to the FCI 10-group and UK KC 7-group nomenclatures are wired against this id at assembly."

  # --- The seven AKC groups, each a breed-typed entity ---------------
  - id: breed_akc_sporting_group
    type: breed
    canonical: "Sporting Group"
    notes: "AKC breed group. Breeds developed to work with hunters: pointers, retrievers, setters, spaniels."
  - id: breed_akc_hound_group
    type: breed
    canonical: "Hound Group"
    notes: "AKC breed group. Hunting breeds relying on sight or scent (sighthounds and scenthounds)."
  - id: breed_akc_working_group
    type: breed
    canonical: "Working Group"
    notes: "AKC breed group. Breeds bred to guard, pull, and perform rescue/draft work. Formerly contained the herding breeds that were split out into the Herding Group in 1983."
  - id: breed_akc_terrier_group
    type: breed
    canonical: "Terrier Group"
    notes: "AKC breed group. Breeds bred to hunt and kill vermin and to go to ground after burrowing prey."
  - id: breed_akc_toy_group
    type: breed
    canonical: "Toy Group"
    notes: "AKC breed group. Small companion breeds."
  - id: breed_akc_non_sporting_group
    type: breed
    canonical: "Non-Sporting Group"
    notes: "AKC breed group. A diverse residual group of breeds varying widely in size, coat, and function."
  - id: breed_akc_herding_group
    type: breed
    canonical: "Herding Group"
    notes: "AKC breed group, created in 1983 — the newest AKC classification. Its members were formerly members of the Working Group."

  # --- Example breeds connected to their group via grouped_under -----
  - id: breed_rottweiler
    type: breed
    canonical: "Rottweiler"
    notes: "Example breed for the Working Group, named in the manifest's proposed Cat 8 question."
  - id: breed_german_shepherd_dog
    type: breed
    canonical: "German Shepherd Dog"
    aliases: ["GSD", "German Shepherd", "Alsatian"]
    notes: "Example breed for the Herding Group under the AKC taxonomy (Pastoral Group under the UK KC — a cross-registry difference handled in other notes). Already declared in akc-german-shepherd-dog.md; reused here."

edges:
  # The publication is authored/published by the AKC.
  - from: pub_akc_group_taxonomy
    type: authored_by
    to: org_akc
    evidence: "The breed-group listing is published by the American Kennel Club on akc.org under its public-education resources; the page is AKC registry boilerplate stating that each AKC-registered breed is assigned to one of seven groups."

  # The publication mentions each of the seven groups it enumerates.
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_akc_sporting_group
    evidence: "The page lists 'Sporting Group' as one of the seven AKC groups, enumerating its member breeds."
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_akc_hound_group
    evidence: "The page lists 'Hound Group' as one of the seven AKC groups, enumerating its member breeds."
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_akc_working_group
    evidence: "The page lists 'Working Group' as one of the seven AKC groups; the Herding Group's members were formerly members of the Working Group."
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_akc_terrier_group
    evidence: "The page lists 'Terrier Group' as one of the seven AKC groups, enumerating its member breeds."
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_akc_toy_group
    evidence: "The page lists 'Toy Group' as one of the seven AKC groups, enumerating its member breeds."
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_akc_non_sporting_group
    evidence: "The page lists 'Non-Sporting Group' as one of the seven AKC groups, enumerating its member breeds."
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_akc_herding_group
    evidence: "The page lists 'Herding Group' as one of the seven AKC groups and states: 'The Herding Group, created in 1983, is the newest AKC classification; its members were formerly members of the Working Group.'"

  # AKC is the registry authority that maintains the group taxonomy publication.
  - from: org_akc
    type: regulates
    to: pub_akc_group_taxonomy
    evidence: "The AKC is the U.S. breed-registry authority that assigns each registered breed to exactly one of seven groups and maintains/publishes this group taxonomy. The page states each AKC-registered breed 'are assigned to one of seven groups representing characteristics and functions the breeds were originally bred for.'"
    needs_grounding: true

  # The supersession of the Working->Herding split (1983) is the one temporal
  # marker the page makes explicit.
  - from: pub_akc_group_taxonomy
    type: mentions
    to: breed_rottweiler
    evidence: "The Rottweiler is listed under the Working Group on the AKC group page; it is the breed named in the manifest's proposed Cat 8 question."

  # Example breed -> group membership via grouped_under (NOT member_of_group).
  - from: breed_rottweiler
    type: grouped_under
    to: breed_akc_working_group
    evidence: "Under the AKC seven-group taxonomy the Rottweiler is assigned to the Working Group, as listed on the AKC breeds-sorted-by-group page. grouped_under is the registry/SKOS-broader group-membership relation (the manifest's 'member_of_group' is the same relation under this ontology)."
  - from: breed_german_shepherd_dog
    type: grouped_under
    to: breed_akc_herding_group
    evidence: "Under the AKC seven-group taxonomy the German Shepherd Dog is assigned to the Herding Group (created 1983). grouped_under is the registry group-membership relation; the same breed sits in the UK Kennel Club's Pastoral Group, handled in companion notes."

tags: [breed_standards, akc, breed_groups, taxonomy, seven_groups, herding_group, cat_8, ontology_coherence, canonical_taxonomy]
---

# AKC Seven-Group Breed Taxonomy (canonical Cat 8 standard)

## Summary

The **American Kennel Club** assigns each of its registered breeds to exactly **one of seven groups**, "representing characteristics and functions the breeds were originally bred for." The seven groups are the **Sporting Group, Hound Group, Working Group, Terrier Group, Toy Group, Non-Sporting Group, and Herding Group**.

The **Herding Group is the newest** of the seven. As the AKC page states:

> "The Herding Group, created in 1983, is the newest AKC classification; its members were formerly members of the Working Group."

That single sentence supplies the taxonomy's one explicit temporal marker: the Herding Group was carved out of the Working Group in 1983, which is why a herding breed such as the German Shepherd Dog now sits in the Herding Group rather than the Working Group under the AKC system.

## Group assignments of the example breeds

- The **Rottweiler** is assigned to the **Working Group**.
- The **German Shepherd Dog** is assigned to the **Herding Group** (created 1983).

Both assignments are modeled here with `grouped_under` edges from the breed to its group — the registry/SKOS-broader group-membership relation. (The ontology treats a breed grouping as itself a `breed`-typed entity, so each of the seven groups is authored as a `breed` node.)

## Why this is the canonical Cat 8 taxonomy note

This note materializes the AKC seven-group taxonomy as the **external standard** against which a built graph can be checked for ontology coherence (Cat 8). Its publication node carries the stable id `pub_akc_group_taxonomy` so that cross-taxonomy `contradicts` edges — to the **FCI ten-group** nomenclature and the **UK Kennel Club seven-but-differently-named** taxonomy — can be wired against it at assembly time. The cardinality conflict (AKC 7 vs FCI 10) and the label conflict (AKC "Herding" vs UK "Pastoral" for the same breeds) are the two coherence tests this standard anchors.

## Provenance and limitations

The source page was fetched live during drafting. The expected-source substring **"The Herding Group, created in 1983, is the newest AKC classification"** was confirmed verbatim on the live AKC page, as were the seven group names, the Rottweiler's Working-Group assignment, and the "one of seven groups" statement. The page is undated AKC boilerplate; `source_date` records the access date rather than a publication date. AKC holds copyright in the group taxonomy and breed listings; only short factual excerpts are quoted here under fair use.

## Sources

- AKC List of Breeds by Group (canonical URL of record): https://www.akc.org/public-education/resources/general-tips-information/dog-breeds-sorted-groups/
- Companion cross-registry note: `vault/breed_standards/fci-akc-kennel-club-comparative-structure.md`
