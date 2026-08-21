---
note_id: breed_akc_fss
source_url: https://www.akc.org/dog-breeds/foundation-stock-service/
source_title: "AKC Foundation Stock Service — list of breeds"
source_date: "2025-12-31"
source_publisher: "American Kennel Club"
license: other
license_note: "AKC holds rights in its registry and breed-listing content; this is a private-association registry page, not a U.S. government work. Only short factual excerpts and breed names (uncopyrightable facts) are quoted here under fair use for non-commercial research and evaluation. The full page is not reproduced. source_date reflects the '(Revised 12/31/25)' notice on the AKC FSS group-breakout page; the listing page itself is undated boilerplate."
accessed_on: "2026-06-17"
domain: breed_standards

# Cat 5 STRUCTURAL HOLE note. FSS breeds are RECORDED by the AKC but are
# deliberately NOT placed in any of the seven AKC breed groups. The signal
# this note exists to test is the ABSENCE of any `grouped_under` edge on
# these breed entities: every fully-recognized AKC breed in the corpus has a
# grouped_under edge to one of the seven groups; these FSS breeds, though
# mentioned by the same registry, have none. A graph that "helpfully" infers
# a group for them (or treats the informal Sporting/Hound/etc. navigation
# headers on the AKC FSS broken-group page as registry group membership) has
# manufactured a phantom edge; a graph that detects the missing-room is correct.
#
# DO NOT add grouped_under edges to any breed below. Connect them to the AKC
# only via `mentions`.

entities:
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "Breed registry authority for the United States. Reused entity; also declared in akc-german-shepherd-dog.md. The FSS is an AKC program for recording purebred breeds that are not yet fully recognized."

  - id: pub_akc_fss_listing
    type: publication
    canonical: "AKC Foundation Stock Service — list of breeds (akc.org)"
    notes: "The FSS listing / boilerplate page. Records breeds without assigning them to one of the seven AKC breed groups."

  # --- FSS breeds: recorded by the AKC, ungrouped. -------------------
  # Each is a real, specifically-named breed enrolled in the FSS program
  # (per the AKC FSS broken-group page, accessed 2026-06-17). None carries
  # a grouped_under edge: the structural hole is the point.

  - id: breed_american_leopard_hound
    type: breed
    canonical: "American Leopard Hound"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

  - id: breed_bohemian_shepherd
    type: breed
    canonical: "Bohemian Shepherd"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

  - id: breed_braque_du_bourbonnais
    type: breed
    canonical: "Braque du Bourbonnais"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

  - id: breed_estrela_mountain_dog
    type: breed
    canonical: "Estrela Mountain Dog"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

  - id: breed_norrbottenspets
    type: breed
    canonical: "Norrbottenspets"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

  - id: breed_stabyhoun
    type: breed
    canonical: "Stabyhoun"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

  - id: breed_tornjak
    type: breed
    canonical: "Tornjak"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

  - id: breed_volpino_italiano
    type: breed
    canonical: "Volpino Italiano"
    notes: "FSS-recorded; not assigned to any of the seven AKC breed groups."

edges:
  # The listing publication is published by the AKC.
  - from: pub_akc_fss_listing
    type: authored_by
    to: org_akc
    evidence: "Page is hosted at akc.org/dog-breeds/foundation-stock-service/ and states 'Each of the following breeds has been accepted for recording in the AKC Foundation Stock Service®. The AKC provides this service to allow these purebred breeds to continue to develop while providing them with the security of a reliable and reputable avenue to maintain their records.' — i.e. authored/published by the American Kennel Club."

  # Each FSS breed is MENTIONED by the listing. No grouped_under edge follows.
  - from: pub_akc_fss_listing
    type: mentions
    to: breed_american_leopard_hound
    evidence: "American Leopard Hound is listed by name on the AKC Foundation Stock Service breed listing. The page records the breed but assigns it to none of the seven AKC breed groups; 'FSS® breeds are not eligible for AKC registration.'"

  - from: pub_akc_fss_listing
    type: mentions
    to: breed_bohemian_shepherd
    evidence: "Bohemian Shepherd is listed by name on the AKC Foundation Stock Service breed listing. Recorded but ungrouped; 'FSS® breeds are not eligible for AKC registration.'"

  - from: pub_akc_fss_listing
    type: mentions
    to: breed_braque_du_bourbonnais
    evidence: "Braque du Bourbonnais is listed by name on the AKC Foundation Stock Service breed listing. Recorded but ungrouped; 'FSS® breeds are not eligible for AKC registration.'"

  - from: pub_akc_fss_listing
    type: mentions
    to: breed_estrela_mountain_dog
    evidence: "Estrela Mountain Dog is listed by name on the AKC Foundation Stock Service breed listing. Recorded but ungrouped; 'FSS® breeds are not eligible for AKC registration.'"

  - from: pub_akc_fss_listing
    type: mentions
    to: breed_norrbottenspets
    evidence: "Norrbottenspets is listed by name on the AKC Foundation Stock Service breed listing. Recorded but ungrouped; 'FSS® breeds are not eligible for AKC registration.'"

  - from: pub_akc_fss_listing
    type: mentions
    to: breed_stabyhoun
    evidence: "Stabyhoun is listed by name on the AKC Foundation Stock Service breed listing. Recorded but ungrouped; 'FSS® breeds are not eligible for AKC registration.'"

  - from: pub_akc_fss_listing
    type: mentions
    to: breed_tornjak
    evidence: "Tornjak is listed by name on the AKC Foundation Stock Service breed listing. Recorded but ungrouped; 'FSS® breeds are not eligible for AKC registration.'"

  - from: pub_akc_fss_listing
    type: mentions
    to: breed_volpino_italiano
    evidence: "Volpino Italiano is listed by name on the AKC Foundation Stock Service breed listing. Recorded but ungrouped; 'FSS® breeds are not eligible for AKC registration.'"

  # The AKC mentions the FSS program itself (the org records these breeds).
  - from: pub_akc_fss_listing
    type: mentions
    to: org_akc
    evidence: "The listing page names the American Kennel Club as the body operating the Foundation Stock Service® and recording the enrolled breeds."

tags: [breed_standards, akc, foundation_stock_service, fss, cat5_structural_hole, ungrouped, missing_room]
---

# AKC Foundation Stock Service — Recorded but Ungrouped Breeds

## Summary

The American Kennel Club operates the **Foundation Stock Service® (FSS)**, a
program that records purebred breeds the AKC does not yet fully recognize. The
listing page states that "Each of the following breeds has been accepted for
recording in the AKC Foundation Stock Service®," and that the AKC "provides this
service to allow these purebred breeds to continue to develop while providing
them with the security of a reliable and reputable avenue to maintain their
records." Crucially, the page also states verbatim:

> "FSS® breeds are not eligible for AKC registration."

Per the AKC's FSS breed group-breakout page (accessed 2026-06-17), **there are
currently 87 breeds in the FSS program** — a figure that drifts over time as
breeds advance toward recognition (the manifest's earlier 12/31/25 snapshot
recorded 84; an older AKC page cited 72). These breeds are recorded by the
registry, but **none of them is placed in any of the seven AKC breed groups**
(Sporting, Hound, Working, Terrier, Toy, Non-Sporting, Herding).

## Why this is a Cat 5 structural hole

Every *fully recognized* AKC breed in this corpus carries a `grouped_under`
edge to one of the seven AKC breed groups — the German Shepherd Dog to Herding,
the Rottweiler to Working, and so on. The FSS breeds documented here are
deliberately the exception: they are first-class, named, recorded breed entities
that the same registry mentions, yet **they have no group membership at all.**

The structural signal is therefore an **absence**: a graph built over this
corpus should be able to detect that these breeds are recorded-but-ungrouped —
that there is a "missing room" where the group edge would be for a recognized
breed. This note deliberately authors **no** `grouped_under` edge for any FSS
breed. The breeds connect to the registry only via `mentions`.

Two specific failure modes this note is built to catch:

1. **Phantom-group inference.** A system that "helpfully" assigns an FSS breed
   to a group it resembles (e.g. filing the American Leopard Hound under the
   Hound Group because of its name) has manufactured a `grouped_under` edge that
   the registry does not assert. FSS breeds are not in any AKC group.
2. **Navigation-header capture.** The AKC's FSS group-breakout page arranges FSS
   breeds under informal headings (Sporting, Hound, Working, etc.) purely as a
   browsing convenience. Those headings are **not** AKC breed-group membership —
   FSS breeds are by definition not yet placed in the formal groups. A system
   that ingests those navigation headers as registry `grouped_under` edges has
   read an organizational aid as an ontological commitment.

## The FSS → Miscellaneous → full-recognition pipeline (context)

FSS enrollment is the first stage of a longer recognition pipeline: a breed is
recorded in the FSS, may later advance to the Miscellaneous Class, and only on
acceptance by the AKC Board of Directors for regular status is it assigned to
one of the seven groups. Until that final step, the breed remains ungrouped.
The companion notes on the Miscellaneous Class and on recently fully-recognized
breeds (e.g. the Danish-Swedish Farmdog, the AKC's 202nd recognized breed,
placed in the Working Group effective Jan 1 2025) model the closing of this
pipeline; this note models its open, ungrouped state.

## Breeds documented in this note

The following FSS breeds are authored as recorded-but-ungrouped entities (a
representative subset of the ~87, drawn from the AKC FSS broken-group listing):
American Leopard Hound, Bohemian Shepherd, Braque du Bourbonnais, Estrela
Mountain Dog, Norrbottenspets, Stabyhoun, Tornjak, and Volpino Italiano. Each
is connected to the AKC's FSS listing publication by a `mentions` edge and to
no breed group by any edge.

## Provenance and limitations

The FSS listing page (`akc.org/dog-breeds/foundation-stock-service/`) was
fetched successfully on 2026-06-17; the eligibility sentence "FSS® breeds are
not eligible for AKC registration." and the recording boilerplate were confirmed
verbatim against the live page. The 87-breed count and the individual breed
names were taken from the AKC FSS group-breakout page
(`akc.org/breeder-programs/foundation-stock-service-program/fss-breeds-broken-group/`),
also fetched 2026-06-17. The count is volatile and should be re-verified at
ingestion. No `grouped_under` relation is asserted for any breed here; that
absence is intentional and is the artifact under test.

## Sources

- AKC Foundation Stock Service — list of breeds (canonical URL of record): https://www.akc.org/dog-breeds/foundation-stock-service/
- AKC Foundation Stock Service breeds, broken out by group (source of the 87-breed count and breed names): https://www.akc.org/breeder-programs/foundation-stock-service-program/fss-breeds-broken-group/
