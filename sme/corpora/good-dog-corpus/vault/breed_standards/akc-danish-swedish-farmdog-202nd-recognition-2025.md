---
note_id: event_akc_danish_swedish_farmdog_recognition_2025
source_url: https://www.akc.org/expert-advice/dog-breeds/danish-swedish-farmdog-newest-akc-recognized-breed/
source_title: "AKC — Danish-Swedish Farmdog, the AKC's 202nd recognized breed"
source_date: "2025-01-02"
source_publisher: "American Kennel Club"
license: fair_use_excerpt
license_note: "AKC holds copyright in its expert-advice editorial content. Short excerpts are quoted under fair use for non-commercial research and evaluation; the full article is not reproduced. Source attribution per note frontmatter."
accessed_on: "2026-06-18"
domain: breed_standards

# Ontology-aligned entity declarations introduced by this note.
entities:
  - id: breed_danish_swedish_farmdog
    type: breed
    canonical: "Danish-Swedish Farmdog"
    aliases: ["Danish Swedish Farmdog", "DSF"]
    notes: "AKC's 202nd recognized breed, effective January 1, 2025; assigned to the Working Group."
  - id: breed_group_working
    type: breed
    canonical: "Working Group"
    notes: "AKC breed group (taxonomy node modeled as a breed-group node, per ONTOLOGY.md: breed-group membership is captured by a breed->breed-group edge rather than a separate taxonomy_node type). One of AKC's seven groups."
  - id: breed_lancashire_heeler
    type: breed
    canonical: "Lancashire Heeler"
    notes: "AKC's 201st recognized breed (Stud Book January 1, 2024), assigned to the Herding Group. The immediately preceding recognition before the Danish-Swedish Farmdog."
  - id: breed_group_herding
    type: breed
    canonical: "Herding Group"
    notes: "AKC breed group (added 1983). Lancashire Heeler's assigned group; cross-links to fci-akc-kennel-club-comparative-structure.md."
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "Breed registry authority for the United States. Operates the recognition pipeline: Foundation Stock Service (FSS) -> Miscellaneous Class -> full recognition."
  - id: person_gina_dinardo
    type: person
    canonical: "Gina DiNardo"
    notes: "AKC Executive Secretary; spokesperson for the recognition announcement (per manifest-verified AKC announcement of 2025-01-02)."
  - id: event_dsf_recognition_2025
    type: event
    canonical: "AKC recognition of the Danish-Swedish Farmdog (2025)"
    notes: "Full AKC recognition effective January 1, 2025; the breed entered the Working Group and became eligible to compete in AKC events that date."

# Edges introduced by this note (the GROUND TRUTH the graph is measured against).
edges:
  - from: breed_danish_swedish_farmdog
    type: grouped_under
    to: breed_group_working
    evidence: "The American Kennel Club's 202nd recognized breed and newest member of the Working Group is eligible to start competing in AKC events on January 1, 2025."
  - from: breed_lancashire_heeler
    type: grouped_under
    to: breed_group_herding
    evidence: "Manifest-verified fact: the Lancashire Heeler (AKC's 201st breed, Stud Book January 1, 2024) was assigned to the Herding Group. (Cross-registry group taxonomy documented in fci-akc-kennel-club-comparative-structure.md.)"
  - from: event_dsf_recognition_2025
    type: subject_of
    to: breed_danish_swedish_farmdog
    evidence: "The American Kennel Club's 202nd recognized breed ... is eligible to start competing in AKC events on January 1, 2025."
  - from: person_gina_dinardo
    type: affiliated_with
    to: org_akc
    evidence: "Manifest-verified fact: the AKC announcement of January 2, 2025 was made by Gina DiNardo, AKC Executive Secretary."
  - from: org_akc
    type: regulates
    to: breed_danish_swedish_farmdog
    evidence: "The American Kennel Club's 202nd recognized breed ... is eligible to start competing in AKC events on January 1, 2025. AKC operates the recognition pipeline (FSS 2011 -> Miscellaneous 2021 -> full recognition 2025)."
  - from: breed_danish_swedish_farmdog
    type: supersedes
    to: breed_lancashire_heeler
    evidence: "The Danish-Swedish Farmdog (202nd recognized breed) follows the Lancashire Heeler (201st recognized breed) in AKC's recognition sequence. Edge encodes the ordinal succession in the recognition timeline (202 follows 201)."
    needs_grounding: true

tags: [breed_standards, akc, danish_swedish_farmdog, working_group, fss_pipeline, temporal, recognition_timeline]
---

# AKC Recognition of the Danish-Swedish Farmdog (202nd Breed, 2025)

## Summary

On January 2, 2025 the **American Kennel Club (AKC)** announced that the
**Danish-Swedish Farmdog** had become the AKC's **202nd recognized breed**,
joining the **Working Group**. The breed became eligible to compete in AKC
events effective January 1, 2025. The announcement was attributed to
**Gina DiNardo**, AKC Executive Secretary.

The recognition is the final step of AKC's multi-stage recognition pipeline.
The Danish-Swedish Farmdog progressed through that pipeline over fourteen
years: it entered the **Foundation Stock Service (FSS) in 2011**, advanced to
the **Miscellaneous Class in 2021**, and reached **full recognition in 2025**.
This completes the FSS -> Miscellaneous -> full-recognition sequence that the
corpus's other AKC-pipeline notes describe in the abstract — this note is the
first to bind a single breed to all three stages, which is why it is tagged
as the pipeline-closing exemplar.

## What the source reported

The AKC expert-advice article states verbatim:

> "The American Kennel Club's 202nd recognized breed and newest member of the
> Working Group is eligible to start competing in AKC events on January 1,
> 2025."

The article documents the pipeline progression directly: the breed entered the
Foundation Stock Service in **2011** and the Miscellaneous Class in **2021**
before full recognition. Manifest-verified facts (used here with source
attribution to the AKC announcement of January 2, 2025) add that **Gina
DiNardo**, AKC Executive Secretary, made the announcement, and that the
immediately preceding recognition was the **Lancashire Heeler** — the AKC's
**201st** breed, admitted to the AKC Stud Book on January 1, 2024 and assigned
to the **Herding Group**.

Note the group distinction: the 202nd breed (Danish-Swedish Farmdog) joins the
**Working Group**, while the 201st breed (Lancashire Heeler) sits in the
**Herding Group**. The two consecutive recognitions land in different AKC
groups, which is why the ordinal succession (202 follows 201) and the group
assignment are independent facts in the graph.

## Why this fits the corpus

This note primarily serves **Cat 6 (temporal)** and closes a **Cat 5 (gap)**:

- **Cat 6 (temporal).** The breed's status walks a dated progression —
  FSS (2011) -> Miscellaneous Class (2021) -> full recognition (2025) — and
  the ordinal recognition sequence (Lancashire Heeler #201 in 2024, then
  Danish-Swedish Farmdog #202 in 2025) gives a clean, explicitly-dated
  temporal chain. A memory system must keep these three status stages ordered
  and attached to the same breed entity rather than fragmenting them into
  unrelated events. The `supersedes` edge encodes the ordinal succession of
  recognitions; it is flagged `needs_grounding` because the source supports the
  ordinal numbers (201, 202) but does not itself use a supersession verb.

- **Cat 5 (gap closed).** Before this note the corpus described the AKC
  recognition pipeline (FSS -> Miscellaneous -> full) only in the abstract,
  with no single breed instantiating all three stages. The Danish-Swedish
  Farmdog supplies that worked example, closing the structural hole: a
  traversal from the FSS concept to a fully-recognized Working Group breed now
  has a real path through one breed entity.

The note also cross-links the **Working Group** and **Herding Group** group
nodes back to `fci-akc-kennel-club-comparative-structure.md`, which already
declares AKC's seven-group taxonomy.

## Provenance and limitations

The source URL was fetched live and the required substring — "newest member of
the Working Group is eligible to start competing in AKC events on January 1,
2025" — was confirmed verbatim on the page, along with the FSS (2011) and
Miscellaneous Class (2021) progression dates. The article page itself did not
surface the Gina DiNardo attribution or the Lancashire Heeler comparison; those
two facts come from the manifest's fact-checked set (AKC announcement of January
2, 2025) and are attributed to the AKC accordingly, not invented here. The
`affiliated_with` and the Lancashire-Heeler `grouped_under` edges therefore rest
on manifest facts rather than on a quote from this specific article. Group-group
membership is modeled with `grouped_under` (breed -> breed-group node) per the
corpus convention of capturing breed-group membership as a breed-to-group edge
rather than a separate taxonomy node type.

## Sources

- AKC — Danish-Swedish Farmdog, the AKC's 202nd recognized breed:
  https://www.akc.org/expert-advice/dog-breeds/danish-swedish-farmdog-newest-akc-recognized-breed/
- Cross-link: `fci-akc-kennel-club-comparative-structure.md` (AKC seven-group taxonomy)
