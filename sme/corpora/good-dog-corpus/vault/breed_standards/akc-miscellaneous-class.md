---
note_id: breed_akc_miscellaneous
source_url: https://www.akc.org/dog-breeds/miscellaneous-class/
source_title: "AKC Miscellaneous Class"
source_date: "2025-06-25"
source_publisher: "American Kennel Club"
license: other
license_note: "AKC.org registry page. Not a U.S. government work; the American Kennel Club holds copyright in its site text. Short factual excerpts are quoted in this note under fair use for non-commercial research and evaluation; the page is not reproduced in full. Source attribution per note frontmatter."
accessed_on: "2026-06-17"
domain: breed_standards

# Cat 5 (gap detection) note. The Miscellaneous Class is the transitional,
# deliberately UNGROUPED state between FSS enrollment and full AKC group
# recognition. The structural hole is the conspicuous ABSENCE of any
# grouped_under edge for these breeds: they are recorded by the AKC and
# eligible to compete, yet assigned to none of the seven breed groups.
# The supersedes pipeline (FSS -> Miscellaneous -> full recognition) is
# modeled at the status-document level.
entities:
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "Breed registry authority for the United States. Reused id, consistent with the other breed_standards notes."
  - id: pub_akc_miscellaneous_class
    type: publication
    canonical: "AKC Miscellaneous Class (status-class definition page)"
    notes: "The AKC.org page defining the Miscellaneous Class as a status between FSS enrollment and regular (group) recognition."
  - id: concept_akc_fss
    type: concept
    canonical: "AKC Foundation Stock Service (FSS) enrollment"
    notes: "The earliest developmental status in the AKC recognition pipeline. FSS breeds are recorded but ungrouped."
  - id: concept_akc_miscellaneous_status
    type: concept
    canonical: "AKC Miscellaneous Class status"
    notes: "The transitional ungrouped status between FSS enrollment and regular status. Breeds here may compete but are not yet placed in any of the seven groups."
  - id: concept_akc_regular_status
    type: concept
    canonical: "AKC regular (full) breed recognition"
    notes: "Full recognition: the breed is accepted into the Stud Book and assigned to one of the seven breed groups. This is the only status at which a grouped_under edge becomes valid."

  # Breeds named by the manifest as recent Miscellaneous-Class breeds. Each is
  # recorded by the AKC and ungrouped -> NO grouped_under edge (the Cat 5 hole).
  - id: breed_alaskan_klee_kai
    type: breed
    canonical: "Alaskan Klee Kai"
  - id: breed_german_spitz
    type: breed
    canonical: "German Spitz"
  - id: breed_bolognese
    type: breed
    canonical: "Bolognese"
  - id: breed_czechoslovakian_vlcak
    type: breed
    canonical: "Czechoslovakian Vlcak"
    aliases: ["Czechoslovakian Vlciak"]
  - id: breed_pyrenean_mastiff
    type: breed
    canonical: "Pyrenean Mastiff"
  - id: breed_yakutian_laika
    type: breed
    canonical: "Yakutian Laika"

edges:
  # --- The supersedes pipeline: FSS -> Miscellaneous -> regular status ----
  # Modeled at the concept level as the staged developmental pathway the
  # source describes. The Miscellaneous status supersedes (replaces) FSS
  # status for a breed advancing through the pipeline, and regular status
  # supersedes Miscellaneous status.
  - from: concept_akc_miscellaneous_status
    type: supersedes
    to: concept_akc_fss
    evidence: "The source states 'The breeds currently eligible to participate in the Miscellaneous Class are still enrolled in the AKC Foundation Stock Service®. FSS® enrollment is maintained until the AKC Board of Directors accepts the breed for regular status.' The Miscellaneous Class is the next developmental stage past FSS enrollment in the AKC recognition pipeline; a breed advances from FSS to the Miscellaneous Class while FSS enrollment is carried forward beneath it."
  - from: concept_akc_regular_status
    type: supersedes
    to: concept_akc_miscellaneous_status
    evidence: "Per the source, FSS®/Miscellaneous enrollment 'is maintained until the AKC Board of Directors accepts the breed for regular status' — regular (full) recognition is the terminal stage that replaces the transitional Miscellaneous status, at which point the breed is admitted to the Stud Book and a breed group. This closes the FSS -> Miscellaneous -> regular pipeline."

  # --- The class-definition publication describes the transitional status ---
  - from: pub_akc_miscellaneous_class
    type: subject_of
    to: concept_akc_miscellaneous_status
    evidence: "The page is the canonical AKC definition of the Miscellaneous Class status: the transitional, group-less stage in which an advancing breed may compete in the Miscellaneous Class before regular recognition."
  - from: pub_akc_miscellaneous_class
    type: authored_by
    to: org_akc
    evidence: "Page is published by the American Kennel Club on akc.org under the AKC dog-breeds section; it is AKC's own statement of its Miscellaneous Class policy."
  - from: pub_akc_miscellaneous_class
    type: mentions
    to: concept_akc_fss
    evidence: "Text: 'The breeds currently eligible to participate in the Miscellaneous Class are still enrolled in the AKC Foundation Stock Service®.' The page references FSS enrollment directly as the underlying status of Miscellaneous-Class breeds."

  # --- Each recent Miscellaneous breed is mentioned but deliberately UNGROUPED.
  # The candidate-specific instruction: NO grouped_under for these breeds. The
  # absence is the Cat 5 signal a graph should detect.
  - from: pub_akc_miscellaneous_class
    type: mentions
    to: breed_alaskan_klee_kai
    evidence: "The Alaskan Klee Kai is listed among the breeds currently eligible to participate in the AKC Miscellaneous Class on the source page. It is recorded by the AKC but not assigned to any of the seven breed groups — no grouped_under edge."
  - from: pub_akc_miscellaneous_class
    type: mentions
    to: breed_german_spitz
    evidence: "The German Spitz is listed among the breeds currently eligible for the Miscellaneous Class on the source page. Recorded but ungrouped — no grouped_under edge."
  - from: pub_akc_miscellaneous_class
    type: mentions
    to: breed_bolognese
    evidence: "The Bolognese is listed among the breeds currently eligible for the Miscellaneous Class on the source page. Recorded but ungrouped — no grouped_under edge."
  - from: pub_akc_miscellaneous_class
    type: mentions
    to: breed_czechoslovakian_vlcak
    evidence: "The Czechoslovakian Vlcak (rendered 'Czechoslovakian Vlciak' on the live page) is listed among the breeds currently eligible for the Miscellaneous Class on the source page. Recorded but ungrouped — no grouped_under edge."
  - from: pub_akc_miscellaneous_class
    type: mentions
    to: breed_pyrenean_mastiff
    evidence: "The Pyrenean Mastiff is listed among the breeds currently eligible for the Miscellaneous Class on the source page. Recorded but ungrouped — no grouped_under edge."
  - from: pub_akc_miscellaneous_class
    type: mentions
    to: breed_yakutian_laika
    evidence: "The Yakutian Laika is named in the manifest as a recent Miscellaneous-Class advancement (eff. June 26, 2024). It is recorded by the AKC but not assigned to any of the seven breed groups — no grouped_under edge. (Not directly confirmed in the fetched page body; see Provenance.)"
    needs_grounding: true

tags: [breed_standards, akc, miscellaneous_class, foundation_stock_service, fss, ungrouped, cat5_gap, recognition_pipeline, supersedes_chain]
---

# AKC Miscellaneous Class — the transitional ungrouped status

## Summary

The American Kennel Club's **Miscellaneous Class** is a transitional status in
the AKC's breed-recognition pipeline. It sits between **Foundation Stock
Service® (FSS) enrollment** — the earliest developmental stage — and **regular
status**, the point of full recognition at which a breed is admitted to the
AKC Stud Book and assigned to one of the seven breed groups.

The source page states the relationship directly:

> "The breeds currently eligible to participate in the Miscellaneous Class are
> still enrolled in the AKC Foundation Stock Service®. **FSS® enrollment is
> maintained until the AKC Board of Directors accepts the breed for regular
> status.**"

So a breed advancing toward recognition moves **FSS → Miscellaneous Class →
regular status**, with FSS enrollment carried forward underneath until the
Board accepts the breed for regular status. The Miscellaneous Class lets such a
breed compete in AKC events before it has a group placement.

## Why this is a Cat 5 (gap-detection) note

Breeds in the Miscellaneous Class are **recorded by the AKC and eligible to
compete, yet assigned to none of the seven breed groups.** They are the
deliberately *ungrouped* middle of the pipeline. In graph terms, the
structural hole is the conspicuous **absence of any `grouped_under` edge** for
these breeds: a memory system that "fills in" a group for a Miscellaneous-Class
breed has hallucinated a placement the registry has not yet made; a system that
detects the missing group relation has found the real gap.

Recent breeds that occupy (or recently occupied) this transitional status —
named in the corpus manifest — include the **Alaskan Klee Kai** (advanced
effective June 25, 2025 per the manifest), and the **German Spitz**,
**Bolognese**, **Czechoslovakian Vlcak**, **Pyrenean Mastiff**, and **Yakutian
Laika** (each effective June 26, 2024 per the manifest). None of these carry a
`grouped_under` edge in this note, by design.

## The recognition pipeline (supersedes chain)

```
concept_akc_fss                     (Foundation Stock Service enrollment — recorded, ungrouped)
            ▲
            │ supersedes
            │
concept_akc_miscellaneous_status    (Miscellaneous Class — transitional, may compete, still ungrouped)
            ▲
            │ supersedes
            │
concept_akc_regular_status          (regular/full recognition — admitted to Stud Book + a breed group)
```

Only at `concept_akc_regular_status` does a `grouped_under` edge become valid
for the breed. The two supersedes edges model the staged developmental pathway
the source describes; the breeds named above sit at the middle stage and so
remain ungrouped.

## Provenance and limitations

The canonical AKC.org page was fetched successfully on 2026-06-17. The
status-relationship quote — "FSS® enrollment is maintained until the AKC Board
of Directors accepts the breed for regular status" — was confirmed **verbatim**
against the live page, including its immediately preceding sentence about
Miscellaneous-Class breeds still being enrolled in the FSS.

The fetched page body listed the Alaskan Klee Kai, German Spitz, Bolognese,
Czechoslovakian Vlciak (the live page's spelling) and Pyrenean Mastiff among
the eligible breeds, alongside others not modeled here (Dutch Shepherd,
Japanese Akitainu, Kai Ken, Norrbottenspets, Peruvian Inca Orchid, Portuguese
Podengo, Small Munsterlander). The **Yakutian Laika** was not directly visible
in the fetched body; its inclusion (and the per-breed effective dates) is taken
from the corpus manifest rather than from the live page text, and the
corresponding edge is flagged `needs_grounding: true`. The Miscellaneous-Class
membership list is volatile — breeds graduate to regular status and new ones
enter — so the specific roster should be re-verified against the live page at
each ingestion.

## Sources

- AKC Miscellaneous Class (canonical URL of record): https://www.akc.org/dog-breeds/miscellaneous-class/
- Corpus manifest: recent Miscellaneous-Class advancements and effective dates (Alaskan Klee Kai eff. 2025-06-25; German Spitz, Bolognese, Czechoslovakian Vlcak, Pyrenean Mastiff, Yakutian Laika eff. 2024-06-26)
