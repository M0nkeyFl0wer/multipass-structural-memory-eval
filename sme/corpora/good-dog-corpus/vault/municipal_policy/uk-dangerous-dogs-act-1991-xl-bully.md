---
note_id: pub_uk_dda_1991_xl_bully
source_url: https://www.legislation.gov.uk/ukpga/1991/65/section/1
source_title: "Dangerous Dogs Act 1991, Section 1 (with XL Bully designation amendments)"
source_date: "1991"
source_publisher: "UK Government (legislation.gov.uk)"
license: fair_use_excerpt
license_note: "UK primary legislation on legislation.gov.uk is Crown copyright, published under the Open Government Licence v3.0, which permits reproduction with attribution. Excerpting statutory and amendment text in an evaluation corpus is within OGL scope."
accessed_on: "2026-06-18"
domain: municipal_policy
jurisdiction: "United Kingdom"

# Ontology-aligned entity declarations introduced by this note.
# breed_american_pit_bull_terrier and concept_bsl are reused from the existing
# vault notes (breed_standards/ukc-american-pit-bull-terrier.md, the Montreal/
# Ontario municipal_policy notes) so cross-jurisdiction queries traverse a
# single shared entity rather than a string-match duplicate.
entities:
  - id: pub_dda_1991
    type: publication
    canonical: "Dangerous Dogs Act 1991"
    aliases: ["Dangerous Dogs Act 1991, Section 1", "DDA 1991"]
  - id: org_defra
    type: organization
    canonical: "Department for Environment, Food and Rural Affairs"
    aliases: ["DEFRA", "Defra"]
    is_regulatory: true
  - id: pub_dda_xl_bully_order_2023
    type: publication
    canonical: "The Dangerous Dogs (Designated Types) (England and Wales) Order 2023"
    aliases: ["XL Bully Designation Order 2023"]
  - id: breed_xl_bully
    type: breed
    canonical: "XL Bully"
    aliases: ["American Bully XL", "Bully XL", "XL Bully type"]
    notes: "Designated as a 'type' under DDA 1991 s.1(1)(c), not a kennel-club-registered breed. Modeled as a breed entity here because the corpus treats designated dog types as breed-typed; the designation is type-of-conformation, not pedigree."
  - id: breed_japanese_tosa
    type: breed
    canonical: "Japanese Tosa"
    aliases: ["Tosa", "Tosa Inu"]
  - id: breed_dogo_argentino
    type: breed
    canonical: "Dogo Argentino"
  - id: breed_fila_brasileiro
    type: breed
    canonical: "Fila Brasileiro"
    aliases: ["Fila Braziliero"]
  - id: loc_united_kingdom
    type: location
    canonical: "United Kingdom"
    jurisdiction_type: national
  - id: event_xl_bully_designation
    type: event
    canonical: "XL Bully designation under Dangerous Dogs Act 1991 s.1(1)(c)"
    timestamp: "2023-12-31"
    status: active

# Edges introduced by this note (the GROUND TRUTH the graph is measured against).
edges:
  - from: pub_dda_xl_bully_order_2023
    type: supersedes
    to: pub_dda_1991
    evidence: "The page records: 'S. 1(1)(c) power exercised: type of dog known as XL Bully designated (E.W.) (31.12.2023) by The Dangerous Dogs (Designated Types) (England and Wales) Order 2023', an amending instrument that extends the operative list of designated types in the as-amended s.1 text."
  - from: pub_dda_1991
    type: subject_of
    to: event_xl_bully_designation
    evidence: "Section 1 is the provision under which the XL Bully type was designated; the page marks the s.1(1)(c) power as exercised effective 31.12.2023, making s.1 the statute whose amendment is the designation event."
  - from: pub_dda_1991
    type: mentions
    to: breed_american_pit_bull_terrier
    evidence: "Section 1(1)(a) applies to 'any dog of the type known as the pit bull terrier' — the 'Pit Bull Terrier type' listed as a banned type under the Act."
  - from: pub_dda_1991
    type: mentions
    to: breed_japanese_tosa
    evidence: "Section 1(1)(b) applies to 'any dog of the type known as the Japanese tosa', listed as a banned type under the Act."
  - from: pub_dda_1991
    type: mentions
    to: breed_dogo_argentino
    evidence: "The Dogo Argentino was designated under s.1(1)(c) by subordinate legislation on 12.8.1991 and appears in the as-amended list of banned types."
  - from: pub_dda_1991
    type: mentions
    to: breed_fila_brasileiro
    evidence: "The Fila Brasileiro (Fila Braziliero) was designated under s.1(1)(c) by subordinate legislation on 12.8.1991 and appears in the as-amended list of banned types."
  - from: pub_dda_1991
    type: mentions
    to: breed_xl_bully
    evidence: "The as-amended s.1 list includes the XL Bully following the 31.12.2023 designation: 'type of dog known as XL Bully designated'."
  - from: event_xl_bully_designation
    type: located_in
    to: loc_united_kingdom
    evidence: "The designation applies in England & Wales (31.12.2023) and was extended to Scotland (23.2.2024), i.e. across the United Kingdom under the Act."
  - from: org_defra
    type: regulates
    to: breed_xl_bully
    evidence: "The Dangerous Dogs Act 1991 and its designated-types regime are administered by the Department for Environment, Food and Rural Affairs (DEFRA), the UK department responsible for dog-control policy including the XL Bully designation."
  - from: org_defra
    type: regulates
    to: concept_bsl
    evidence: "DEFRA administers the UK's breed/type-specific prohibition regime under the Dangerous Dogs Act 1991, the canonical UK instance of breed-specific legislation (BSL)."
  - from: org_defra
    type: located_in
    to: loc_united_kingdom
    evidence: "DEFRA is a department of the United Kingdom government."

tags: [municipal_policy, united_kingdom, dda_1991, bsl, xl_bully, pit_bull, cat_6_temporal_chain, cat_3_contradiction, cross_jurisdiction_anchor, national_level]
---

# UK Dangerous Dogs Act 1991, Section 1 — banned types and the XL Bully amendment

## Summary

The **Dangerous Dogs Act 1991** is the United Kingdom's national statute prohibiting and restricting certain dog types. Section 1 bans four named types: the **Pit Bull Terrier type** (the corpus's `breed_american_pit_bull_terrier`), the **Japanese Tosa**, the **Dogo Argentino**, and the **Fila Brasileiro**. The first two are named directly in the primary Act; the latter two were designated by subordinate legislation in August 1991. The Act is administered by the **Department for Environment, Food and Rural Affairs (DEFRA)**. The most recent extension of the list is the **XL Bully**, added by amendment in 2023–2024.

## What the source reported

The legislation.gov.uk "as amended" view of Section 1 carries the operative prohibition text plus a set of amendment annotations. The load-bearing temporal marker for this corpus is the annotation that records the exercise of the s.1(1)(c) designation power:

> S. 1(1)(c) power exercised: **type of dog known as XL Bully designated** (E.W.) (31.12.2023) by The Dangerous Dogs (Designated Types) (England and Wales) Order 2023

So the Act's banned-type list grew over time rather than being fixed in 1991:

- **1991 (primary Act):** Pit Bull Terrier type and Japanese Tosa named directly in s.1(1)(a)–(b).
- **12 August 1991 (subordinate legislation):** Dogo Argentino and Fila Brasileiro designated under s.1(1)(c).
- **31 December 2023 (England & Wales):** the **XL Bully** type designated, effective for the designation; the **ownership offence** (keeping an XL Bully without an exemption certificate) takes effect from **1 February 2024**.
- **23 February 2024 (Scotland):** the XL Bully restrictions extended to Scotland.

The XL Bully is designated as a **"type"** under s.1(1)(c) — defined by conformation and physical characteristics — not as a kennel-club-registered breed. This is the same legal mechanism the Act uses for the "Pit Bull Terrier type": the statute regulates a *type* identified by appearance, which is why DDA enforcement turns on a dog's measured conformation rather than its pedigree.

## Why this fits the corpus

This note serves two SME categories:

- **Cat 6 (temporal supersession / The Archive):** The banned-type list is a multi-event temporal chain on a single statute — 1991 primary text → 1991 subordinate designations → 2023 E&W XL Bully designation → 2024 ownership offence → 2024 Scotland extension. The `supersedes` edge from the 2023 Designation Order to the 1991 Act, plus the `subject_of` edge to the dated designation event, make the "what was added, and when" question a graph traversal rather than a single-note lookup. A flat retriever that reads only the 1991 text would miss that the XL Bully is now in scope.
- **Cat 3 (contradiction surfacing / The Dissonance):** The UK's national type-ban posture stands in direct tension with the behaviour-based, anti-BSL postures elsewhere in the corpus — the repealed Montreal bylaw (`vault/municipal_policy/montreal-bsl-2018-repeal.md`) and the Calgary responsible-pet-ownership model (`vault/municipal_policy/calgary-rpob-47m2021.md`). Where several North American jurisdictions were *narrowing or repealing* breed-specific legislation, the UK was *expanding* it (the XL Bully addition). Both bind to the shared `concept_bsl` and `breed_american_pit_bull_terrier` entities, so the opposed-direction policy signal is queryable as a single cross-jurisdiction comparison.

It is also a **cross-jurisdiction anchor at the national level**, complementing the province-level (Ontario DOLA) and municipal-level (Montreal, Calgary, Denver) instances already in the corpus.

## Provenance and limitations

The REQUIRED substring "type of dog known as XL Bully designated" was confirmed verbatim on the live legislation.gov.uk page via WebFetch on the accessed date; the s.1(1)(c) amendment annotation quoted above is from that page. The dated facts (E&W effective 31 Dec 2023, ownership offence from 1 Feb 2024, Scotland from 23 Feb 2024; the four original types; DEFRA as administering department) are the manifest-verified facts supplied for this note and align with the page's amendment record.

Non-causation discipline: this note makes no claim that any listed type causes a measurable share of bite incidents. Breed/type designation under the DDA is a *policy* classification by conformation; it is not an epidemiological finding, and the corpus elsewhere records that the CDC disclaims the use of breed data for policy. The Act regulates a *type* (a conformation category), not a pedigree breed, and that distinction is the load-bearing one here.

## Sources

- UK Government (legislation.gov.uk), Dangerous Dogs Act 1991, Section 1 (as amended): https://www.legislation.gov.uk/ukpga/1991/65/section/1
- The Dangerous Dogs (Designated Types) (England and Wales) Order 2023 — the amending instrument designating the XL Bully type (referenced in the s.1(1)(c) amendment annotation).
- Administering department: Department for Environment, Food and Rural Affairs (DEFRA).
