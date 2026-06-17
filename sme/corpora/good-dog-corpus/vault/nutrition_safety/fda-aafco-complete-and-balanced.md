---
note_id: nut_fda_aafco_complete_balanced
source_url: https://www.fda.gov/animal-veterinary/animal-health-literacy/complete-and-balanced-pet-food
source_title: "“Complete and Balanced” Pet Food"
source_date: "2023-01-26"
source_publisher: "U.S. Food and Drug Administration"
license: public_domain
license_note: "U.S. federal government work, 17 U.S.C. § 105. Page last updated 2020-02-28; content current as of 2023-01-26."
accessed_on: "2026-06-17"
domain: nutrition_safety

# Cat 8 (ontology coherence) source. Introduces the AAFCO controlled-vocabulary
# standard (the Dog or Cat Food Nutrient Profiles, published in AAFCO's annual
# Official Publication) as the conformance target a "complete and balanced"
# product must conform_to. Two life-stage profiles (adult maintenance; growth
# & reproduction) are modeled as concept entities. The FDA page is the
# regulatory explainer; AAFCO is the standard-setting body.
entities:
  - id: org_us_fda
    type: organization
    canonical: "U.S. Food and Drug Administration"
    is_regulatory: true
    notes: "Federal regulator of pet food; authors this consumer explainer of the AAFCO standard."
  - id: org_aafco
    type: organization
    canonical: "Association of American Feed Control Officials"
    is_regulatory: false
    notes: "Standard-setting body for animal-feed nutritional adequacy. Not a government agency; a voluntary membership association of state/federal feed-control officials whose model profiles are widely adopted into state law."
  - id: pub_aafco_nutrient_profiles
    type: publication
    canonical: "AAFCO Dog or Cat Food Nutrient Profiles (Official Publication)"
    notes: "The controlled-vocabulary standard: minimum (and some maximum) nutrient levels by species and life stage, published annually in AAFCO's Official Publication."
  - id: pub_fda_complete_balanced
    type: publication
    canonical: "FDA — “Complete and Balanced” Pet Food"
  - id: concept_adult_maintenance_profile
    type: concept
    canonical: "Adult maintenance nutrient profile"
    notes: "One of the two AAFCO life-stage profiles; covers adult, non-reproducing animals."
  - id: concept_growth_reproduction_profile
    type: concept
    canonical: "Growth and reproduction nutrient profile"
    notes: "One of the two AAFCO life-stage profiles; covers growing, pregnant, and nursing animals."
  - id: concept_complete_and_balanced
    type: concept
    canonical: "Complete and balanced (nutritional adequacy claim)"
    notes: "The regulated nutritional-adequacy statement; a product earns it only by meeting an AAFCO profile or passing an AAFCO feeding trial."
  - id: product_complete_balanced_petfood
    type: product
    canonical: "A pet food labeled “complete and balanced”"
    notes: "Class-level stand-in for any product carrying the regulated 'complete and balanced' statement; the conformance subject in the conforms_to edge."

edges:
  - from: pub_fda_complete_balanced
    type: authored_by
    to: org_us_fda
    evidence: "Page is published on fda.gov under Animal & Veterinary / Animal Health Literacy as an official FDA consumer explainer; footer states 'An official website of the United States government' and 'Content current as of: 01/26/2023'."
  - from: pub_fda_complete_balanced
    type: mentions
    to: org_aafco
    evidence: "Text: 'Meet one of the Dog or Cat Food Nutrient Profiles established by the Association of American Feed Control Officials (AAFCO); or Pass a feeding trial using AAFCO procedures.'"
  - from: pub_fda_complete_balanced
    type: subject_of
    to: concept_complete_and_balanced
    evidence: "The page's primary topic is what the regulated 'complete and balanced' nutritional-adequacy statement means and how a product qualifies for it."
  - from: pub_fda_complete_balanced
    type: mentions
    to: pub_aafco_nutrient_profiles
    evidence: "Text: 'AAFCO publishes the nutrient profiles for dogs and cats in the association's annual Official Publication.' The page describes the AAFCO Dog and Cat Food Nutrient Profiles as the standard a product must meet."
  - from: pub_fda_complete_balanced
    type: mentions
    to: concept_adult_maintenance_profile
    evidence: "Text: 'AAFCO established two nutrient profiles for both dogs and cats—one for growth and reproduction ... and one for adult maintenance.'"
  - from: pub_fda_complete_balanced
    type: mentions
    to: concept_growth_reproduction_profile
    evidence: "Text: 'one for growth and reproduction (which includes growing, pregnant, and nursing animals) and one for adult maintenance.'"
  # The Cat 8 conformance edge: a 'complete and balanced' product conforms_to
  # the AAFCO nutrient-profile standard publication. The conformance target is
  # the standard document, per the v0.3 conforms_to edge semantics.
  - from: product_complete_balanced_petfood
    type: conforms_to
    to: pub_aafco_nutrient_profiles
    evidence: "A pet food may carry the 'complete and balanced' statement only by conformance to the AAFCO standard: per the page, the food 'must either: Meet one of the Dog or Cat Food Nutrient Profiles established by the Association of American Feed Control Officials (AAFCO); or Pass a feeding trial using AAFCO procedures.' The named-standard conformance target is the AAFCO Dog or Cat Food Nutrient Profiles."
  - from: pub_fda_complete_balanced
    type: mentions
    to: product_complete_balanced_petfood
    evidence: "The page's central subject is the labeling of dog and cat food products that carry the 'complete and balanced' nutritional-adequacy statement."
  - from: pub_aafco_nutrient_profiles
    type: mentions
    to: concept_adult_maintenance_profile
    evidence: "The adult-maintenance profile is one of the two life-stage profiles defined within the AAFCO Dog or Cat Food Nutrient Profiles standard: 'AAFCO established two nutrient profiles for both dogs and cats ... and one for adult maintenance.' The standard publication defines this profile."
  - from: pub_aafco_nutrient_profiles
    type: mentions
    to: concept_growth_reproduction_profile
    evidence: "The growth-and-reproduction profile is the second of the two life-stage profiles defined within the AAFCO Dog or Cat Food Nutrient Profiles standard: 'one for growth and reproduction (which includes growing, pregnant, and nursing animals).' The standard publication defines this profile."

tags: [nutrition_safety, fda, aafco, complete_and_balanced, nutrient_profiles, controlled_vocabulary, life_stage, conformance, cat_8_ontology]
---

# FDA — "Complete and Balanced" Pet Food (AAFCO nutrient profiles)

## Summary

This FDA consumer page explains the regulated meaning of the **"complete and
balanced"** nutritional-adequacy statement on dog and cat food labels and the
controlled vocabulary behind it. To carry that statement, a product must
either **meet one of the Dog or Cat Food Nutrient Profiles established by the
Association of American Feed Control Officials (AAFCO)**, or **pass a feeding
trial using AAFCO procedures**. AAFCO publishes the profiles in the
association's annual **Official Publication**.

## The two life-stage profiles

Because nutritional needs differ across life stages, **AAFCO established two
nutrient profiles for both dogs and cats**:

1. **Growth and reproduction** — covering growing, pregnant, and nursing
   animals.
2. **Adult maintenance** — covering adult, non-reproducing animals.

Every nutrient in a profile carries a **minimum** level, and some also carry a
**maximum** level. As the page notes, "A growing kitten or a dog nursing six
pups ... has different nutritional requirements than an older, spayed or
neutered pet."

## Worked example: the adult-cat crude-protein minimum

The page's worked example states that the **AAFCO Cat Food Nutrient Profile for
adult cat maintenance sets the minimum level of crude protein at 26 percent on
a dry matter basis.** It emphasizes that label guaranteed-analysis values are
expressed on an as-fed (moisture-included) basis, so a dry-matter comparison
requires converting out the moisture guarantee before comparing products
against the 26% DM figure.

## Why this exercises Cat 8 (ontology coherence)

The AAFCO Dog or Cat Food Nutrient Profiles are a **formal controlled
vocabulary / standard**, and "complete and balanced" is a claim that a product
makes *against* that standard. This note models that relationship with the
v0.3 `conforms_to` edge: the conformance target is the named standard
publication, not a marketing label. The two life-stage profiles are modeled as
`concept` entities the standard publication defines (bound via `mentions`),
giving a SHACL-style conformance testbed — a memory system should bind a "complete and
balanced" product to the AAFCO standard via conformance, distinguish the two
life-stage profiles, and not conflate the regulatory explainer (FDA) with the
standard-setting body (AAFCO).

## Provenance and limitations

The source page was fetched successfully (HTTP 200) and the quoted phrases —
including the "Dog or Cat Food Nutrient Profiles established by the Association
of American Feed Control Officials," the two-profile description, and the
"26 percent on a dry matter basis" adult-cat crude-protein minimum — were
verified verbatim against the live FDA page on 2026-06-17. The page is a U.S.
federal government work (public domain, 17 U.S.C. § 105); the underlying AAFCO
Official Publication is a separately-copyrighted standard not reproduced here.
The page footer records "Content current as of: 01/26/2023" with a last-update
metadata timestamp of 02/28/2020.

## Sources

- FDA — "Complete and Balanced" Pet Food (canonical URL of record): https://www.fda.gov/animal-veterinary/animal-health-literacy/complete-and-balanced-pet-food
- AAFCO Dog and Cat Food Nutrient Profiles — published in AAFCO's annual Official Publication (the named standard; not reproduced here)
