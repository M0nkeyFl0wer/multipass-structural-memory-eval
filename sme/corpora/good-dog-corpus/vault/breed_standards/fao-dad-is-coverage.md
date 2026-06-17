---
note_id: breed_fao_dad_is
source_url: https://www.fao.org/dad-is
source_title: "Domestic Animal Diversity Information System (DAD-IS)"
source_date: "2022-09"
source_publisher: "Food and Agriculture Organization of the United Nations"
license: other
license_note: "FAO/UN material. DAD-IS content is published by the FAO under its own terms (FAO Open Access / database terms of use), not as a U.S. federal government public-domain work. Short excerpts are quoted here for non-commercial research and evaluation with source attribution per frontmatter; the full database is not reproduced. Re-use under FAO's stated licensing terms."
accessed_on: "2026-06-17"
domain: breed_standards

# Cat 5 (Missing Room / gap detection). DAD-IS records national breed
# populations with deliberately uneven coverage: a breed can be recorded
# as local (single country) or as regional/international transboundary, and
# carries an at-risk / not-at-risk / unknown risk classification. The
# structural hole is the population recorded nationally (local) but absent
# from transboundary records, and the population whose risk status is
# "unknown" rather than asserted. The at_risk_status edge binds a breed
# population to its risk category (a concept entity); located_in binds the
# system / coordinators to member-country locations. Per the
# candidate-specific instruction the breed -> risk-category relation is the
# new at_risk_status edge; member-country coverage uses located_in.
entities:
  - id: org_fao
    type: organization
    canonical: "Food and Agriculture Organization of the United Nations"
    is_regulatory: false
    notes: "UN specialized agency. Maintains and develops DAD-IS as a global registry of animal genetic resources. Not regulatory in the FDA jurisdictional sense; holds intergovernmental coordination authority over the SDG 2.5.2 indicator reporting."
  - id: pub_dad_is
    type: publication
    canonical: "Domestic Animal Diversity Information System (DAD-IS)"
    notes: "The searchable breed-population databank maintained by FAO."
  - id: concept_local_breed
    type: concept
    canonical: "Local breed (occurring in only a single country)"
    notes: "DAD-IS coverage category: a breed population reported in only one country."
  - id: concept_transboundary_breed
    type: concept
    canonical: "Transboundary breed (regional or international)"
    notes: "DAD-IS coverage category: a breed reported in several countries in one region (regional transboundary) or across regions (international transboundary)."
  - id: concept_at_risk_status
    type: concept
    canonical: "At-risk of extinction (DAD-IS risk classification)"
    notes: "One of the three DAD-IS risk-of-extinction levels: at-risk."
  - id: concept_not_at_risk_status
    type: concept
    canonical: "Not-at-risk of extinction (DAD-IS risk classification)"
  - id: concept_unknown_risk_status
    type: concept
    canonical: "Unknown level of risk of extinction (DAD-IS risk classification)"
    notes: "The coverage hole: a population whose risk status is recorded as unknown rather than asserted. The Cat 5 gap is the structurally-uneven split between asserted and unknown risk."
  - id: loc_dad_is_member_countries
    type: location
    canonical: "DAD-IS reporting member countries (182 countries)"
    jurisdiction_type: national
    notes: "The set of national jurisdictions from which breed populations are recorded. Coverage is uneven across this set by design — that unevenness is the detectable gap."

edges:
  # Base: the databank mentions the local / transboundary coverage categories.
  - from: pub_dad_is
    type: mentions
    to: concept_local_breed
    evidence: "DAD-IS states 'Mammalian and avian livestock breeds are reported to occur either in only a single country (local breeds), in several countries in one region (regional transboundary) or in different regions of the world (international transboundary).' The 'local breed' category is the single-country coverage class."
  - from: pub_dad_is
    type: mentions
    to: concept_transboundary_breed
    evidence: "Same DAD-IS sentence names the regional transboundary ('several countries in one region') and international transboundary ('different regions of the world') classes, distinguishing them from local single-country breeds."
  - from: pub_dad_is
    type: mentions
    to: concept_at_risk_status
    evidence: "DAD-IS describes 'the proportion of local and transboundary breeds, classified as being at risk, not-at risk or of unknown level of risk of extinction and the SDG indicator 2.5.2' — 'at risk' is one of the three risk-of-extinction classifications."
  - from: pub_dad_is
    type: mentions
    to: concept_not_at_risk_status
    evidence: "The same DAD-IS sentence lists 'not-at risk' as the second of the three risk-of-extinction classifications applied to local and transboundary breeds."
  - from: pub_dad_is
    type: mentions
    to: concept_unknown_risk_status
    evidence: "The same DAD-IS sentence lists 'of unknown level of risk of extinction' as the third classification — the category that marks a coverage hole where risk is recorded but not determined."
  # at_risk_status (v0.3): the local-vs-transboundary coverage categories carry
  # a risk-of-extinction status. Modeled at the level of the breed/coverage
  # class because DAD-IS asserts the status against 'local and transboundary
  # breeds' as populations rather than against an individual named breed here.
  - from: concept_transboundary_breed
    type: at_risk_status
    to: concept_at_risk_status
    evidence: "DAD-IS reports the proportion of transboundary breeds 'classified as being at risk' — the system attaches an explicit at-risk-of-extinction status field to transboundary breed populations, feeding SDG indicator 2.5.2."
  - from: concept_local_breed
    type: at_risk_status
    to: concept_at_risk_status
    evidence: "DAD-IS reports the proportion of 'local ... breeds, classified as being at risk' of extinction — local single-country populations carry the same explicit risk-status field, and a local population recorded as 'unknown' rather than 'at risk' is the Cat 5 coverage gap."
  # located_in (v0.3 use): the databank's coverage spans 182 member countries.
  - from: org_fao
    type: located_in
    to: loc_dad_is_member_countries
    evidence: "DAD-IS records 'More than 15 000 national breed populations (representing more than 8 800 breeds and about 40 species) from 182 countries' — FAO's DAD-IS coverage is scoped across these 182 reporting national jurisdictions, with National Coordinators for the Management of Animal Genetic Resources contacts listed per country."
  - from: pub_dad_is
    type: authored_by
    to: org_fao
    evidence: "DAD-IS is 'the Domestic Animal Diversity Information System maintained and developed by FAO'; the databank is published and curated by the Food and Agriculture Organization of the United Nations."

tags: [breed_standards, fao, dad_is, gap_detection, cat5, at_risk_status, transboundary, conservation, animal_genetic_resources, missing_room]
---

# FAO Domestic Animal Diversity Information System (DAD-IS) — coverage and the structural gap

## Summary

The **Domestic Animal Diversity Information System (DAD-IS)** is the global breed-population databank "maintained and developed by FAO." As recorded on the system's landing page, it holds **"More than 15 000 national breed populations (representing more than 8 800 breeds and about 40 species) from 182 countries."** It provides searchable access to breed-related information and to the contact details of all National Coordinators for the Management of Animal Genetic Resources.

## Why DAD-IS coverage is structurally uneven (the Cat 5 gap)

DAD-IS classifies each population along two axes that are deliberately incomplete by design, which is what makes it a gap-detection (Cat 5 / "Missing Room") source rather than a flat registry:

1. **Geographic coverage — local vs transboundary.** Per DAD-IS, "Mammalian and avian livestock breeds are reported to occur either in only a single country (**local breeds**), in several countries in one region (**regional transboundary**) or in different regions of the world (**international transboundary**)." A population recorded *nationally* as a local breed but *absent* from any transboundary record is the textbook structural hole: present in one frame, missing from the adjacent frame.

2. **Risk coverage — at-risk vs not-at-risk vs unknown.** DAD-IS reports "the proportion of local and transboundary breeds, classified as being **at risk**, **not-at risk** or of **unknown level of risk** of extinction," feeding SDG indicator 2.5.2. The "unknown" class is the second hole: a population is recorded, but its conservation status is not asserted. A graph that treats "unknown" as equivalent to "not recorded" — or that silently omits the populations carrying it — is missing exactly the rooms DAD-IS deliberately keeps visible.

The gap is therefore not an accident of incomplete data entry; the local-vs-transboundary and at-risk-vs-unknown splits are first-class fields, and the *unevenness across them* is the detectable signal a structural-memory system should surface.

## Provenance and limitations

The DAD-IS landing page was fetched directly during this note's drafting; the headline figure **"More than 15 000 national breed populations ... from 182 countries"** and the local/regional-transboundary/international-transboundary and at-risk/not-at-risk/unknown classifications were confirmed verbatim against the live page text. The page's around-8 800-breeds and around-40-species counts are point-in-time figures (the databank is continuously updated); a corroborating tertiary summary (Wikipedia's DAD-IS entry) cited the September 2022 snapshot at roughly 8,859 breeds with 595 reported extinct — close to the live "more than 8 800 breeds" figure but **not** used as a primary source here and to be re-confirmed against FAO at any ingestion that quotes an exact count.

This note records the *coverage structure* (the categories and their unevenness), not a list of individual at-risk dog populations; DAD-IS is a livestock-wide system, and the breed-level enumeration of which specific dog populations are local-only or risk-unknown is left to a query against the live databank rather than asserted here.

## Sources

- FAO Domestic Animal Diversity Information System (DAD-IS), landing page (canonical URL of record): https://www.fao.org/dad-is
- Corpus ontology (v0.3 edge `at_risk_status`): `sme/corpora/good-dog-corpus/ontology.yaml`
