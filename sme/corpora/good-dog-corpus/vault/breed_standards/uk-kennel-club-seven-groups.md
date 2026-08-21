---
note_id: breed_ukc_seven_groups
source_url: https://www.royalkennelclub.com/breed-standards/about-breed-standards/
source_title: "About Breed Standards | The Royal Kennel Club"
source_date: "2023-04-01"
source_publisher: "The Royal Kennel Club (UK)"
license: other
license_note: "The Royal Kennel Club holds copyright in its breed-standards and group-classification content. Short excerpts are quoted under fair use for non-commercial research and evaluation; the full page is not reproduced. source_date reflects the April 2023 confirmation of the 'Royal' prefix; the underlying seven-group structure predates it."
accessed_on: "2026-06-17"
domain: breed_standards
alias_pair_id: null

# Ontology-aligned entity declarations. The seven UK groups are modelled as
# breed-typed entities (the ontology treats a breed grouping as a recognized
# breed). The taxonomy publication carries the exact id pub_ukc_group_taxonomy.
# org_rkc and org_akc are reused from the existing breed_standards notes.
entities:
  - id: org_rkc
    type: organization
    canonical: "The Royal Kennel Club (UK)"
    is_regulatory: false
    notes: "UK national breed registry. Formerly 'The Kennel Club'; the 'Royal' prefix was confirmed in April 2023. Same entity as org_tkc in fci-akc-kennel-club-comparative-structure.md."
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "U.S. national breed registry. Referenced here only as the comparison taxonomy for the label-mapping test."
  - id: pub_ukc_group_taxonomy
    type: publication
    canonical: "The Royal Kennel Club (UK) Breed Group Classification — seven groups"
    notes: "The RKC 'About Breed Standards' page, which enumerates the seven UK breed groups."

  # The seven UK (Royal) Kennel Club groups, each a breed-typed grouping entity.
  - id: breed_group_uk_hound
    type: breed
    canonical: "Hound Group (UK Kennel Club)"
  - id: breed_group_uk_toy
    type: breed
    canonical: "Toy Group (UK Kennel Club)"
  - id: breed_group_uk_pastoral
    type: breed
    canonical: "Pastoral Group (UK Kennel Club)"
  - id: breed_group_uk_utility
    type: breed
    canonical: "Utility Group (UK Kennel Club)"
  - id: breed_group_uk_terrier
    type: breed
    canonical: "Terrier Group (UK Kennel Club)"
  - id: breed_group_uk_working
    type: breed
    canonical: "Working Group (UK Kennel Club)"
  - id: breed_group_uk_gundog
    type: breed
    canonical: "Gundog Group (UK Kennel Club)"

  # AKC counterpart grouping entities, declared here so the label-mapping
  # (Pastoral ~ Herding, Gundog ~ Sporting, Utility ~ Non-Sporting) is
  # expressible as same-type alias_of edges. The remaining four labels are
  # shared verbatim with the AKC and are not re-declared as separate AKC nodes.
  - id: breed_group_akc_herding
    type: breed
    canonical: "Herding Group (AKC)"
    notes: "AKC's seventh group, created 1983. UK counterpart: Pastoral."
  - id: breed_group_akc_sporting
    type: breed
    canonical: "Sporting Group (AKC)"
    notes: "AKC group for pointers, setters, retrievers, spaniels. UK counterpart: Gundog."
  - id: breed_group_akc_non_sporting
    type: breed
    canonical: "Non-Sporting Group (AKC)"
    notes: "AKC catch-all group. UK counterpart: Utility."

  # A representative breed used to anchor a grouped_under membership edge into
  # a UK group (German Shepherd Dog is classified by the RKC in Pastoral).
  - id: breed_german_shepherd_dog
    type: breed
    canonical: "German Shepherd Dog"
    aliases: ["GSD", "German Shepherd", "Alsatian"]
    notes: "Already declared in akc-german-shepherd-dog.md and royal-kennel-club-german-shepherd-dog.md; reused here as the membership anchor."

edges:
  # Authorship / provenance of the taxonomy document.
  - from: pub_ukc_group_taxonomy
    type: authored_by
    to: org_rkc
    evidence: "The 'About Breed Standards' page is published on royalkennelclub.com by The Royal Kennel Club, which states the breed-standards guardianship rests with a sub-committee 'comprised of experts from each of the seven groups (hounds, toys, pastoral, utility, terriers, working and gundogs)'."

  # The taxonomy mentions each of the seven groups it enumerates.
  - from: pub_ukc_group_taxonomy
    type: mentions
    to: breed_group_uk_hound
    evidence: "Listed verbatim in 'hounds, toys, pastoral, utility, terriers, working and gundogs'."
  - from: pub_ukc_group_taxonomy
    type: mentions
    to: breed_group_uk_toy
    evidence: "Listed verbatim in 'hounds, toys, pastoral, utility, terriers, working and gundogs'."
  - from: pub_ukc_group_taxonomy
    type: mentions
    to: breed_group_uk_pastoral
    evidence: "Listed verbatim in 'hounds, toys, pastoral, utility, terriers, working and gundogs'."
  - from: pub_ukc_group_taxonomy
    type: mentions
    to: breed_group_uk_utility
    evidence: "Listed verbatim in 'hounds, toys, pastoral, utility, terriers, working and gundogs'."
  - from: pub_ukc_group_taxonomy
    type: mentions
    to: breed_group_uk_terrier
    evidence: "Listed verbatim in 'hounds, toys, pastoral, utility, terriers, working and gundogs'."
  - from: pub_ukc_group_taxonomy
    type: mentions
    to: breed_group_uk_working
    evidence: "Listed verbatim in 'hounds, toys, pastoral, utility, terriers, working and gundogs'."
  - from: pub_ukc_group_taxonomy
    type: mentions
    to: breed_group_uk_gundog
    evidence: "Listed verbatim in 'hounds, toys, pastoral, utility, terriers, working and gundogs'."

  # Membership: a representative breed grouped under a UK group (the
  # registry/SKOS-broader relation grouped_under, breed -> breed-group).
  - from: breed_german_shepherd_dog
    type: grouped_under
    to: breed_group_uk_pastoral
    evidence: "The Royal Kennel Club classifies the German Shepherd Dog in the Pastoral Group (see royal-kennel-club-german-shepherd-dog.md). Pastoral is one of the seven UK groups enumerated by this page; the AKC files the same breed under Herding."

  # Cross-registry label mapping: three UK group labels denote the same
  # functional grouping as a differently-named AKC group. alias_of is the
  # same-type (breed->breed) SKOS-altLabel relation; it does NOT assert the
  # memberships are identical, only that the two registries' labels denote the
  # corresponding functional group.
  - from: breed_group_uk_pastoral
    type: alias_of
    to: breed_group_akc_herding
    evidence: "The UK Kennel Club's Pastoral Group is the label-mapped counterpart of the AKC's Herding Group: both collect herding/droving breeds (e.g. the German Shepherd Dog sits in Pastoral under the RKC and Herding under the AKC). Same functional grouping, different registry label."
  - from: breed_group_uk_gundog
    type: alias_of
    to: breed_group_akc_sporting
    evidence: "The UK Kennel Club's Gundog Group is the label-mapped counterpart of the AKC's Sporting Group: both collect pointing, setting, flushing and retrieving breeds. Same functional grouping, different registry label."
  - from: breed_group_uk_utility
    type: alias_of
    to: breed_group_akc_non_sporting
    evidence: "The UK Kennel Club's Utility Group is the label-mapped counterpart of the AKC's Non-Sporting Group: both are the catch-all for breeds not specialised to the other working categories. Same functional grouping, different registry label."

tags: [breed_standards, royal_kennel_club, uk_kennel_club, breed_groups, ontology_coherence, label_mapping, cat8]
---

# The Royal Kennel Club (UK) Seven Breed Groups

## Summary

The Royal Kennel Club (UK) — formerly "The Kennel Club," with the "Royal"
prefix confirmed in April 2023 — divides recognised breeds into **seven groups**.
The Royal Kennel Club's "About Breed Standards" page enumerates them when it
describes how the breed standards are governed:

> "The guardianship of the breed standards is entrusted to the breed standards
> and stud book sub-committee, comprised of experts from each of the seven
> groups (hounds, toys, pastoral, utility, terriers, working and gundogs)."

The seven UK groups are therefore: **Hounds, Toys, Pastoral, Utility, Terriers,
Working, and Gundogs.**

## Same cardinality as the AKC, different labels

The UK system has the **same group count as the AKC (seven)** but uses
**different category names** for three of them. The functional mapping is:

| UK (Royal) Kennel Club | AKC |
|---|---|
| Pastoral | Herding |
| Gundog | Sporting |
| Utility | Non-Sporting |
| Hound | Hound |
| Terrier | Terrier |
| Working | Working |
| Toy | Toy |

Four labels (Hound, Terrier, Working, Toy) are shared verbatim; three differ.
The clearest worked example of the label difference is the German Shepherd Dog,
which the Royal Kennel Club classifies under **Pastoral** while the AKC
classifies the same breed under **Herding** (see
`royal-kennel-club-german-shepherd-dog.md` and `akc-german-shepherd-dog.md`).

## Why this exercises Cat 8 (ontology coherence)

This note is the UK leg of a three-taxonomy testbed (AKC seven groups, FCI ten
groups, UK seven groups). It is the cleanest **re-projection / label-mapping**
conformance test in the set: a memory system must recognise that the UK Pastoral
Group and the AKC Herding Group denote the *same* functional grouping under two
different registry labels — without collapsing them into a single node (they are
distinct registry classifications) and without treating them as unrelated. The
`alias_of` edges encode the label equivalence at the group level; the
`grouped_under` edge encodes a concrete breed-to-group membership. A system that
either (a) fails to relate Pastoral to Herding, or (b) merges them outright,
fails this conformance check.

## Provenance and limitations

The Royal Kennel Club "About Breed Standards" page was fetched directly in this
note's drafting session and the seven-group list was confirmed verbatim:
"hounds, toys, pastoral, utility, terriers, working and gundogs." The
label-to-AKC mappings (Pastoral≈Herding, Gundog≈Sporting, Utility≈Non-Sporting)
are well-established functional correspondences widely documented across both
registries; the source page itself enumerates only the UK labels, so the
cross-registry mapping is asserted from the corpus's own AKC notes plus standard
registry practice rather than quoted from this single page. The `source_date`
records the April 2023 "Royal" confirmation; the underlying seven-group
structure long predates it.

## Sources

- About Breed Standards | The Royal Kennel Club (canonical URL of record):
  https://www.royalkennelclub.com/breed-standards/about-breed-standards/
- AKC seven-group taxonomy and the Herding/Sporting/Non-Sporting labels:
  `akc-german-shepherd-dog.md`, `fci-akc-kennel-club-comparative-structure.md`
- German Shepherd Dog classified in the UK Pastoral Group:
  `royal-kennel-club-german-shepherd-dog.md`
