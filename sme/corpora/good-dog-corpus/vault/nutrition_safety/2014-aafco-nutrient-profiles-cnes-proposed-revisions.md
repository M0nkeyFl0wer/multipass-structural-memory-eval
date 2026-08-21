---
note_id: pub_aafco_nutrient_profiles_2014_cnes
source_url: https://www.aafco.org/wp-content/uploads/2023/01/Model_Bills_and_Regulations_Agenda_Midyear_2015_Final_Attachment_A.__Proposed_revisions_to_AAFCO_Nutrient_Profiles_PFC_Final_070214.pdf
source_title: "AAFCO Dog and Cat Food Nutrient Profiles (proposed revisions, CNES)"
source_date: "2014"
source_publisher: "Association of American Feed Control Officials"
license: fair_use_excerpt
accessed_on: "2026-06-18"
domain: nutrition_safety

# Introduces the AAFCO Nutrient Profiles proposed-revisions publication, the
# 2006 NRC values it draws on, and the two organizations. Reuses canonical
# org_aafco where downstream notes reference AAFCO's Official Publication.
entities:
  - id: org_aafco
    type: organization
    canonical: "Association of American Feed Control Officials"
    aliases: ["AAFCO"]
  - id: org_nrc
    type: organization
    canonical: "National Research Council"
    aliases: ["NRC", "Committee on Animal Nutrition"]
  - id: pub_aafco_nutrient_profiles_2014_cnes
    type: publication
    canonical: "Proposed Revisions to AAFCO Dog and Cat Food Nutrient Profiles (CNES, 2014)"
    aliases: ["AAFCO Nutrient Profiles proposed revisions"]
  - id: pub_nrc_2006_nutrient_requirements
    type: publication
    canonical: "Nutrient Requirements of Dogs and Cats (NRC, 2006)"
    aliases: ["2006 NRC", "NRC recommended-allowance (RA) values"]
  - id: concept_tryptophan_minimum_growth_reproduction
    type: concept
    canonical: "Tryptophan minimum in the Dog Food Nutrient Profile for Growth and Reproduction"

edges:
  - from: pub_aafco_nutrient_profiles_2014_cnes
    type: authored_by
    to: org_aafco
    evidence: "The revisions are the work of AAFCO's Canine and Feline Nutrition Expert Subcommittees (CNES), an AAFCO body: \"The original Canine and Feline Nutrition Expert Subcommittees convened in 1990\" and the document notes AAFCO \"again formed Canine and Feline Nutrition Expert Subcommittees and charged these\" to revise the AAFCO profiles"
  - from: pub_aafco_nutrient_profiles_2014_cnes
    type: supersedes
    to: pub_nrc_2006_nutrient_requirements
    evidence: "\"the Canine and Feline Nutrition Expert Subcommittees of 2007 primarily used the RA in the 2006 Nutrient Requirements of Dogs and Cats in evaluating whether revision was needed to one or more of the minimum recommended concentrations in the profiles\" — the AAFCO profile concentrations are the operative feed-control values that update/replace the 2006 NRC recommended allowances for regulatory use"
  - from: pub_nrc_2006_nutrient_requirements
    type: authored_by
    to: org_nrc
    evidence: "Nutrient Requirements of Dogs and Cats (2006) is the report of the National Research Council; the document repeatedly attributes the recommended-allowance (RA) values to \"the 2006 Nutrient Requirements of Dogs and Cats\" produced by the NRC."
  - from: pub_aafco_nutrient_profiles_2014_cnes
    type: cites
    to: pub_nrc_2006_nutrient_requirements
    evidence: "\"the Nutrient Requirements of Dogs and Cats in 2006 contained two additional listings of nutrient concentrations for adequate intake and recommended allowance (RA)\" — the document repeatedly cites the 2006 NRC RA values as its evidentiary basis (e.g. retaining adult-maintenance amino-acid amounts that \"were greater than the corresponding RA in the 2006 NRC\")"
  - from: pub_aafco_nutrient_profiles_2014_cnes
    type: mentions
    to: concept_tryptophan_minimum_growth_reproduction
    evidence: "\"The CNES did not elect to change the tryptophan concentration in the Dog Food Nutrient Profile for Growth and Reproduction\" ... \"the minimum requirement for tryptophan in Labrador retriever puppies was less than the current concentration\""

tags: [nutrition_safety, aafco, nrc, nutrient_profiles, cnes, tryptophan, token_efficiency, cat_7, registry_standard]
---

# AAFCO Dog and Cat Food Nutrient Profiles — CNES Proposed Revisions (2014)

## Summary

This source is the **Proposed Revisions to the AAFCO Dog and Cat Food Nutrient
Profiles**, prepared by the Association of American Feed Control Officials'
**Canine and Feline Nutrition Expert Subcommittees (CNES)** and circulated as
Attachment A to the AAFCO Model Bills and Regulations agenda (Midyear 2015,
final draft dated 2014). It is a dense, table-heavy registry standard: minimum
and (where set) maximum concentrations for protein, amino acids, fatty acids,
minerals, and vitamins across two life stages (Adult Maintenance; Growth and
Reproduction), accompanied by footnotes and a long rationale narrative
explaining each retained or revised value. It is the kind of document where the
answer to a single nutrient question is buried in dozens of pages of tables and
prose.

## What the source reported

The CNES used the **recommended-allowance (RA) values in the 2006 NRC
publication *Nutrient Requirements of Dogs and Cats*** as its primary yardstick
for deciding whether each AAFCO profile concentration needed revision, updating
or retaining values where supported by the NRC RA, feeding studies, or
practical experience. This makes the AAFCO profiles the operative feed-control
values that draw on, and for regulatory purposes supersede, the older NRC
recommended allowances. Where the existing adult-maintenance amino-acid amounts
(histidine, lysine, threonine, tryptophan) "were greater than the corresponding
RA in the 2006 NRC," the panel elected to retain them; several growth amino-acid
minimums (arginine, leucine, methionine, phenylalanine-tyrosine, valine) were
raised to match the NRC RA for growth.

The rationale narrative gives a concrete worked example for **tryptophan**. The
subcommittee "did not elect to change the tryptophan concentration in the Dog
Food Nutrient Profile for Growth and Reproduction" for two reasons. First, it
"had access to feeding studies and a publication showing that the **minimum
requirement for tryptophan in Labrador retriever puppies** was less than the
current concentration in [the] AAFCO Dog Food Nutrient Profile for Growth and
Reproduction, and that the tryptophan concentration of 0.2% DM already provided
approximately a 25% safety margin." Second, the panel noted "it was nearly
impossible to formulate a product at the minimum protein concentration to
contain more than 0.2% tryptophan on a DM basis from typical ingredients
without including crystalline tryptophan in the formula." The panel similarly
declined to raise leucine and valine to the NRC lactation RA, citing "lack of
documented problems with the previous concentrations."

## Why this fits the corpus

This note serves **Cat 7 (token efficiency / "The Abacus")**. The source is
deliberately information-dense: nutrient tables, footnotes, and a multi-page
rationale where a single load-bearing fact (the tryptophan minimum was *not*
changed, and why) is surrounded by hundreds of unrelated numbers. A
token-efficient memory system should retrieve and answer the narrow question
("did AAFCO change the growth tryptophan minimum, and on what evidence?")
without dragging the entire profile table into context. It also lightly
exercises **Cat 6 (temporal supersession)** through the `supersedes` edge from
the AAFCO profiles to the 2006 NRC values, and **Cat 1 (factual retrieval)**
for the specific tryptophan rationale.

## Provenance and limitations

The required substring and every quoted passage above were verified by
extracting the text directly from the canonical AAFCO PDF (the live WebFetch
could not parse the compressed PDF stream, so the file was downloaded and
`pdftotext` was run against it, then the rationale section was grepped). The
substring "minimum requirement for tryptophan in Labrador retriever puppies"
appears verbatim in the PDF, wrapped across two lines as "...minimum requirement
for tryptophan in Labrador / retriever puppies...".

Scope limits to respect: this is a **proposed-revisions / agenda-attachment**
draft (final draft dated 070214), not necessarily the final adopted Official
Publication text; the `2014` source date is that draft-final date. The CNES
*declined* to change the tryptophan minimum — this note must not be read as a
profile increase. The 2006-NRC `supersedes` edge is in the feed-control /
regulatory sense (which values govern commercial labeling), not a claim that
AAFCO invalidated the NRC's underlying physiology; the same document also
`cites` the 2006 NRC as its evidentiary basis, so both edges legitimately hold.
No causal nutrition-safety claim (e.g., grain-free/DCM) is asserted here; this
source predates and does not bear on that question.

## Sources

- AAFCO Dog and Cat Food Nutrient Profiles, proposed revisions (CNES), 2014: https://www.aafco.org/wp-content/uploads/2023/01/Model_Bills_and_Regulations_Agenda_Midyear_2015_Final_Attachment_A.__Proposed_revisions_to_AAFCO_Nutrient_Profiles_PFC_Final_070214.pdf
