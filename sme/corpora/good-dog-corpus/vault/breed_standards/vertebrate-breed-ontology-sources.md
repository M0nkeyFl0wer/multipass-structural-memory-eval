---
note_id: breed_vbo_sources
source_url: https://monarch-initiative.github.io/vertebrate-breed-ontology/general/sources-dog/
source_title: "Vertebrate Breed Ontology — Sources for Dog Breeds"
source_date: "2024"
source_publisher: "Monarch Initiative (Vertebrate Breed Ontology project)"
license: other
license_note: "VBO is released by the Monarch Initiative under CC BY 4.0 per the project's licensing; the source-list documentation page on monarch-initiative.github.io inherits the project's terms. Short excerpts are quoted here for non-commercial research and evaluation, attributed per frontmatter. Not a U.S. federal government work, so 17 U.S.C. § 105 does not apply."
accessed_on: "2026-06-17"
domain: breed_standards

# Cat 5 (gap detection) note. The VBO dog-breed source page declares which
# registries VBO ingests as data sources. The structural signal is the
# ABSENCE of a source_of edge for a major standards body VBO did NOT ingest:
# the Australian National Kennel Council (ANKC). The ten declared sources are
# modeled with source_of edges (registry/org -> the VBO source-list publication);
# ANKC is deliberately given NO source_of edge — that omission is the Cat 5 hole.
entities:
  - id: pub_vbo_dog_sources
    type: publication
    canonical: "Vertebrate Breed Ontology — Sources for Dog Breeds (source list)"
    notes: "The aggregator-side publication: VBO's declared list of upstream dog-breed registries and resources, with per-source manual-curation counts."
  - id: org_monarch_initiative
    type: organization
    canonical: "Monarch Initiative"
    is_regulatory: false
    notes: "Maintainer of the Vertebrate Breed Ontology. Not a breed registry; a biomedical-ontology consortium."
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "US breed registry. 265 AKC breeds manually curated into VBO per this source list."
  - id: org_ckc
    type: organization
    canonical: "Canadian Kennel Club"
    is_regulatory: false
    notes: "Primary registry body for purebred dogs in Canada. 32 CKC breeds curated into VBO."
  - id: org_ukc
    type: organization
    canonical: "United Kennel Club"
    is_regulatory: false
    notes: "Largest all-breed performance-dog registry. 111 UKC breeds curated into VBO."
  - id: org_fci
    type: organization
    canonical: "Fédération Cynologique Internationale"
    is_regulatory: false
    notes: "The World Canine Organisation; recognises 356 breeds. 38 FCI breeds curated into VBO."
  - id: org_kennel_club_uk
    type: organization
    canonical: "The Kennel Club"
    is_regulatory: false
    notes: "UK kennel club (222 recognized breeds). A declared VBO source."
  - id: org_skk
    type: organization
    canonical: "Svenska Kennelklubben"
    aliases: ["Swedish Kennel Club", "SKK"]
    is_regulatory: false
    notes: "Sweden's largest dog organisation. A declared VBO source."
  - id: org_fao
    type: organization
    canonical: "Food and Agriculture Organization of the United Nations"
    aliases: ["FAO"]
    is_regulatory: false
    notes: "UN agency that compiles and maintains DAD-IS, one of VBO's declared sources."
  - id: pub_dad_is
    type: publication
    canonical: "Domestic Animal Diversity Information System (DAD-IS)"
    notes: "FAO-maintained breed-population list; declared as a VBO dog-breed source."
  - id: pub_idog
    type: publication
    canonical: "iDog — National Genomics Data Center"
    notes: "Integrated resource for domestic dog and wild canids; a declared VBO source."
  - id: pub_venom
    type: publication
    canonical: "Veterinary Nomenclature (VeNom)"
    notes: "Canine breed codes recognized by kennel clubs worldwide; a declared VBO source."
  - id: pub_wikipedia_dog_breeds
    type: publication
    canonical: "Wikipedia — List of dog breeds"
    notes: "35 Wikipedia breeds curated into VBO; a declared VBO source."
  - id: org_ankc
    type: organization
    canonical: "Australian National Kennel Council"
    aliases: ["ANKC"]
    is_regulatory: false
    notes: "Australia's national kennel-club authority and FCI contracting partner. NOT present on the VBO dog-breed source list — modeled here with NO source_of edge. The absence of that edge is the Cat 5 structural signal."

edges:
  - from: org_ankc
    type: affiliated_with
    to: org_fci
    evidence: "The Australian National Kennel Council is Australia's national kennel-control body and an FCI contract partner. This affiliation connects ANKC into the graph as a real standards body; the DELIBERATE absence of any source_of edge from ANKC to the VBO dog-breed source list (pub_vbo_dog_sources) is the Cat 5 gap signal — a major registry VBO did not ingest."
  # --- source_of edges: each declared registry/org/resource -> the VBO source list.
  # Direction per manifest A4: registry/org -> the VBO publication it is a source for.
  - from: org_akc
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "The VBO dog-breed source page names the American Kennel Club as a source and reports '265 AKC breeds' manually curated from it (within 'A total of 481 breeds are manually curated from public resources: 265 AKC breeds, 32 CKC breeds, 111 UKC breeds, 38 FCI breeds, 35 wikipedia breeds')."
  - from: org_ckc
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page names the Canadian Kennel Club, 'the primary registry body for purebred dogs in Canada', and reports '32 CKC breeds' manually curated into VBO."
  - from: org_ukc
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page names the United Kennel Club, 'the largest all-breed performance-dog registry in the world', and reports '111 UKC breeds' manually curated into VBO."
  - from: org_fci
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page names the Fédération Cynologique Internationale, 'the World Canine Organisation' (recognises 356 breeds), and reports '38 FCI breeds' manually curated into VBO."
  - from: org_kennel_club_uk
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page names The Kennel Club, 'the largest organisation in the UK devoted to dog health, welfare and training' (222 recognized breeds), as a declared dog-breed source."
  - from: org_skk
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page names the Swedish Kennel Club (Svenska Kennelklubben, SKK), 'Sweden's largest organisation dedicated to dogs and dog owners', as a declared dog-breed source."
  - from: org_fao
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page lists Domestic Animal Diversity Information (DAD-IS), described as 'a list compiled and maintained by the Food and Agriculture Organization of the United Nations (FAO)', as a declared source — so FAO is an upstream source organization for the VBO dog-breed list."
  - from: pub_dad_is
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "DAD-IS is explicitly enumerated among the ten dog-breed sources on the VBO source page."
  - from: pub_idog
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page lists 'iDog - National Genomics Data Center', 'an integrated resource for domestic dog and wild canids', among the declared dog-breed sources."
  - from: pub_venom
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page lists Veterinary Nomenclature (VeNom) — canine breed codes recognized by kennel clubs worldwide — among the declared dog-breed sources."
  - from: pub_wikipedia_dog_breeds
    type: source_of
    to: pub_vbo_dog_sources
    evidence: "Page lists Wikipedia's 'List of dog breeds' as a source and reports '35 wikipedia breeds' manually curated into VBO."
  # --- The publication authored/maintained by the Monarch Initiative.
  - from: pub_vbo_dog_sources
    type: authored_by
    to: org_monarch_initiative
    evidence: "The source-list page is hosted at monarch-initiative.github.io as part of the Vertebrate Breed Ontology documentation, maintained by the Monarch Initiative."
  # --- mentions edges for the registries the page names by canonical form.
  - from: pub_vbo_dog_sources
    type: mentions
    to: org_akc
    evidence: "Page names the American Kennel Club (AKC) and quotes its self-description as 'the recognized and trusted expert in breed, health, and training information for all dogs'."
  - from: pub_vbo_dog_sources
    type: mentions
    to: org_fao
    evidence: "Page references the Food and Agriculture Organization of the United Nations (FAO) as the maintainer of DAD-IS."
  # --- alias_of for the SKK surface forms (same entity type: organization).
  # NOTE: No source_of edge is written for org_ankc. ANKC is a real, major
  # standards body (Australia's FCI contracting partner) but is absent from
  # the VBO dog-breed source list. The absence of its source_of edge is the
  # intended Cat 5 gap signal and must NOT be filled in.

tags: [breed_standards, vbo, vertebrate_breed_ontology, monarch_initiative, source_of, cat5_gap, missing_room, registries, ankc_absent]
---

# Vertebrate Breed Ontology — Sources for Dog Breeds

## Summary

The Vertebrate Breed Ontology (VBO), maintained by the Monarch Initiative, documents on a public page exactly **which registries and resources it ingests as dog-breed sources**. The page enumerates **ten** sources: the American Kennel Club (AKC), the Canadian Kennel Club (CKC), the United Kennel Club (UKC), the Fédération Cynologique Internationale (FCI), The Kennel Club (UK), the Swedish Kennel Club (SKK), the FAO-maintained Domestic Animal Diversity Information System (DAD-IS), iDog (National Genomics Data Center), Veterinary Nomenclature (VeNom), and Wikipedia's "List of dog breeds."

The page also records per-source manual-curation counts:

> "A total of 481 breeds are manually curated from public resources: 265 AKC breeds, 32 CKC breeds, 111 UKC breeds, 38 FCI breeds, 35 wikipedia breeds."

Because the source page declares its provenance **source-by-source**, the registries VBO ingests are visible by type — and so are the absences.

## The Cat 5 signal: which standards body is absent

The diagnostic value of this note is the **gap**. VBO's declared dog-breed source list names ten upstream resources, but it does **not** name the **Australian National Kennel Council (ANKC)** — Australia's national kennel-club authority and an FCI contracting partner of comparable standing to The Kennel Club (UK) and the Swedish Kennel Club, both of which VBO *does* ingest. The New Zealand Kennel Club is likewise absent.

In graph terms, every ingested registry carries a `source_of` edge into the VBO source-list publication; the ANKC entity carries **no such edge**. A memory system that has correctly modeled VBO's source list should be able to answer "which registries does VBO ingest?" *and* surface that ANKC is missing — the absence is a first-class fact, not a silent omission. This is the canonical Cat 5 (Missing Room / gap-detection) failure mode: an entity is recorded, comparable peers carry a relation, and the absence of that relation for one well-known peer is the structural hole the graph should detect.

## Why `source_of` and not `cites`

The ontology (v0.3) distinguishes `cites` (scholarly reference) from `source_of` (data-provenance ingestion). VBO does not merely *cite* the AKC; it **ingests** 265 AKC breed records as upstream data. The `source_of` edge therefore runs from each registry/resource to the VBO source-list publication, capturing "this registry is a declared data source that VBO integrated." The deliberate non-existence of a `source_of` edge for ANKC is what makes the gap legible to a Cat 5 probe.

## Provenance and limitations

The source page was fetched successfully on 2026-06-17. The quoted curation-count sentence ("265 AKC breeds, 32 CKC breeds, 111 UKC breeds, 38 FCI breeds") was confirmed verbatim in the live page, embedded in the longer sentence "A total of 481 breeds are manually curated from public resources: 265 AKC breeds, 32 CKC breeds, 111 UKC breeds, 38 FCI breeds, 35 wikipedia breeds." The list of ten named sources, and the descriptions quoted in the edge evidence strings, were likewise read directly from the live page.

The absence of ANKC is asserted on the basis of the live source list as fetched on the access date; source lists drift over time, so a future revision should re-confirm that ANKC remains absent. The individual recognized-breed counts cited in entity notes (FCI "recognises 356 breeds", KC "222 recognized breeds", etc.) are stated on the same page as descriptive context for each source and are not load-bearing for the Cat 5 signal.

## Sources

- Vertebrate Breed Ontology — Sources for Dog Breeds (canonical URL of record): https://monarch-initiative.github.io/vertebrate-breed-ontology/general/sources-dog/
- Vertebrate Breed Ontology project (Monarch Initiative): https://monarch-initiative.github.io/vertebrate-breed-ontology/
