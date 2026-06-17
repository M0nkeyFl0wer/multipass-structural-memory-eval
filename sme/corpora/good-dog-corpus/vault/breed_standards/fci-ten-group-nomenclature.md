---
note_id: breed_fci_ten_groups
source_url: https://www.fci.be/en/Nomenclature/
source_title: "FCI Breeds Nomenclature (10 groups)"
source_date: "2026-06-17"
source_publisher: "Fédération Cynologique Internationale"
license: other
license_note: "FCI nomenclature and breed-standard texts are published by the Fédération Cynologique Internationale under its own terms of use; they are not public-domain government works. This note records the group structure and short verbatim group headings for non-commercial research and evaluation; the full per-breed nomenclature is not reproduced. Source attribution per note frontmatter."
accessed_on: "2026-06-17"
domain: breed_standards

# Ontology-aligned entity declarations introduced by this note.
# Breed groups are themselves `breed`-typed entities (the ontology treats a
# recognized breed grouping as a `breed`). org_fci and org_akc are reused from
# fci-akc-kennel-club-comparative-structure.md; declared here for self-containment.
entities:
  - id: org_fci
    type: organization
    canonical: "Fédération Cynologique Internationale"
    is_regulatory: false
    notes: "International federation of national kennel clubs. Publishes and maintains the breed nomenclature that organises all recognized breeds into 10 groups. Not a registry itself; coordinates breed standards across member national clubs. Based in Thuin, Belgium."
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "U.S. national breed registry. Organises its recognized breeds into 7 groups (Sporting, Hound, Working, Terrier, Toy, Non-Sporting, Herding) — a different cardinality from FCI's 10. Reused entity (declared in fci-akc-kennel-club-comparative-structure.md and akc-german-shepherd-dog.md)."
  - id: pub_fci_nomenclature
    type: publication
    canonical: "FCI Breeds Nomenclature (10 groups)"
    notes: "The FCI's official nomenclature page, which assigns every recognized breed to one of ten groups. The 10-group cardinality is the Cat 8 (ontology coherence) / Cat 3 (cross-taxonomy) signal against AKC's 7 groups."

  - id: breed_group_fci_1
    type: breed
    canonical: "FCI Group 1 - Sheepdogs and Cattledogs (except Swiss Cattledogs)"
  - id: breed_group_fci_2
    type: breed
    canonical: "FCI Group 2 - Pinscher and Schnauzer - Molossoid and Swiss Mountain and Cattledogs"
  - id: breed_group_fci_3
    type: breed
    canonical: "FCI Group 3 - Terriers"
  - id: breed_group_fci_4
    type: breed
    canonical: "FCI Group 4 - Dachshunds"
    notes: "FCI places Dachshunds in their own dedicated group (Group 4). AKC, by contrast, classifies the Dachshund within its single Hound Group. The standalone Dachshund group is part of why FCI has 10 groups where AKC has 7."
  - id: breed_group_fci_5
    type: breed
    canonical: "FCI Group 5 - Spitz and primitive types"
  - id: breed_group_fci_6
    type: breed
    canonical: "FCI Group 6 - Scent hounds and related breeds"
  - id: breed_group_fci_7
    type: breed
    canonical: "FCI Group 7 - Pointing Dogs"
  - id: breed_group_fci_8
    type: breed
    canonical: "FCI Group 8 - Retrievers - Flushing Dogs - Water Dogs"
  - id: breed_group_fci_9
    type: breed
    canonical: "FCI Group 9 - Companion and Toy Dogs"
  - id: breed_group_fci_10
    type: breed
    canonical: "FCI Group 10 - Sighthounds"

  - id: breed_dachshund
    type: breed
    canonical: "Dachshund"
    notes: "Assigned to FCI Group 4 (Dachshunds) — the group is named for and dedicated to the breed. In AKC the same breed falls under the Hound Group, not a dedicated group."

edges:
  - from: pub_fci_nomenclature
    type: contradicts
    to: pub_akc_group_taxonomy
    evidence: "The FCI nomenclature sorts breeds into TEN groups, whereas the AKC taxonomy (pub_akc_group_taxonomy) uses SEVEN. The two authoritative registries disagree on the cardinality of the breed-group partition — a direct taxonomy-cardinality conflict for Cat 8 conformance / counterfactual re-projection."
  - from: pub_fci_nomenclature
    type: contradicts
    to: pub_ukc_group_taxonomy
    evidence: "FCI's ten-group nomenclature also conflicts with the UK (Royal) Kennel Club's seven-group taxonomy (pub_ukc_group_taxonomy) on group cardinality (10 vs 7), compounding the cross-standard disagreement the AKC/FCI pair already exhibits."
  - from: pub_fci_nomenclature
    type: authored_by
    to: org_fci
    evidence: "The nomenclature is published and maintained by the Fédération Cynologique Internationale at fci.be/en/Nomenclature/; the page is FCI's official organ for the breed-group structure."
  - from: org_fci
    type: regulates
    to: pub_fci_nomenclature
    evidence: "FCI holds the registry authority that issues and maintains the official breed nomenclature dividing all recognized breeds into ten groups across its member national clubs."

  # Every group is mentioned by the nomenclature publication. Heading text quoted
  # verbatim from the live FCI nomenclature page (fetched 2026-06-17).
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_1
    evidence: "Heading 'Group 1 - Sheepdogs and Cattledogs (except Swiss Cattledogs)' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_2
    evidence: "Heading 'Group 2 - Pinscher and Schnauzer - Molossoid and Swiss Mountain and Cattledogs' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_3
    evidence: "Heading 'Group 3 - Terriers' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_4
    evidence: "Heading 'Group 4 - Dachshunds' appears verbatim on the FCI nomenclature page. FCI gives Dachshunds a dedicated group of their own."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_5
    evidence: "Heading 'Group 5 - Spitz and primitive types' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_6
    evidence: "Heading 'Group 6 - Scent hounds and related breeds' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_7
    evidence: "Heading 'Group 7 - Pointing Dogs' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_8
    evidence: "Heading 'Group 8 - Retrievers - Flushing Dogs - Water Dogs' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_9
    evidence: "Heading 'Group 9 - Companion and Toy Dogs' appears verbatim on the FCI nomenclature page."
  - from: pub_fci_nomenclature
    type: mentions
    to: breed_group_fci_10
    evidence: "Heading 'Group 10 - Sighthounds' appears verbatim on the FCI nomenclature page. Group 10 is the highest-numbered group, confirming the ten-group cardinality."

  # The Dachshund -> its FCI group, via grouped_under (registry SKOS-broader).
  - from: breed_dachshund
    type: grouped_under
    to: breed_group_fci_4
    evidence: "The FCI nomenclature lists the Dachshund under 'Group 4 - Dachshunds', a group named for and dedicated to the breed. This registry grouping is the SKOS-broader / grouped_under relation, not a logical is-a."

tags: [breed_standards, fci, nomenclature, breed_groups, dachshund, ten_groups, cross_taxonomy, cardinality, cat8, cat3]
---

# FCI Breeds Nomenclature — the ten-group structure

## Summary

The **Fédération Cynologique Internationale (FCI)** organises every breed it
recognizes into **ten breed groups** via its official nomenclature at
`fci.be/en/Nomenclature/`. The ten groups, with their headings quoted verbatim
from the live page, are:

1. **Group 1 - Sheepdogs and Cattledogs (except Swiss Cattledogs)**
2. **Group 2 - Pinscher and Schnauzer - Molossoid and Swiss Mountain and Cattledogs**
3. **Group 3 - Terriers**
4. **Group 4 - Dachshunds**
5. **Group 5 - Spitz and primitive types**
6. **Group 6 - Scent hounds and related breeds**
7. **Group 7 - Pointing Dogs**
8. **Group 8 - Retrievers - Flushing Dogs - Water Dogs**
9. **Group 9 - Companion and Toy Dogs**
10. **Group 10 - Sighthounds**

Across these ten groups the FCI recognizes on the order of 356 breeds (per its
own nomenclature). Each breed is assigned to exactly one group, and each group
is further subdivided into sections on the full nomenclature.

## The Dachshund has its own group

A structurally notable feature of the FCI scheme is that the **Dachshund is
given a dedicated group of its own — Group 4 - Dachshunds**. No other single
breed anchors an entire FCI group. By contrast, the **American Kennel Club
(AKC)** classifies the Dachshund within its broader **Hound Group**, one of just
**seven** AKC groups (Sporting, Hound, Working, Terrier, Toy, Non-Sporting,
Herding). The Dachshund's standalone FCI group is one of the differences that
yields ten FCI groups where the AKC has seven.

## Why this exercises Cat 8 (ontology coherence) and Cat 3

This note's load-bearing structural fact is a **cardinality conflict between two
authoritative taxonomies of the same domain**: the FCI partitions breeds into
**ten** groups, while the AKC partitions them into **seven**. Both bodies are
naming the same underlying set of breeds, yet their top-level grouping
taxonomies disagree on count and on assignment (the Dachshund being the cleanest
example — its own group under FCI, a member of the Hound Group under AKC).

For **Cat 8 (ontology coherence)**, a memory system must keep the FCI ten-group
taxonomy and the AKC seven-group taxonomy as distinct, internally-consistent
structures rather than silently merging them into one muddled grouping. For
**Cat 3 (contradiction / conflict)**, the FCI-vs-AKC group count is a clean
taxonomy-cardinality conflict to surface when a query asks "how many breed
groups are there." The cross-taxonomy contradiction edge between the FCI and AKC
group structures is wired in corpus assembly using the predictable entity ids;
it is intentionally not authored within this note.

## Provenance and limitations

The FCI nomenclature page was fetched on 2026-06-17. The ten group headings
above were confirmed to appear **verbatim** on the live page, including the exact
string **"Group 4 - Dachshunds"** and a highest-numbered heading of
**"Group 10 - Sighthounds"** (confirming the ten-group cardinality). The
~356-breed figure is from the FCI's own nomenclature as reported in the corpus's
companion note `fci-akc-kennel-club-comparative-structure.md`; it is not re-counted
here. The Dachshund's AKC Hound-Group placement is established AKC fact recorded
for the cross-taxonomy contrast and not drawn from the FCI page.

## Sources

- FCI Breeds Nomenclature (10 groups) — Fédération Cynologique Internationale (canonical URL of record): https://www.fci.be/en/Nomenclature/
- Companion corpus note: `fci-akc-kennel-club-comparative-structure.md`
