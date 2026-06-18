---
note_id: nut_avma_raw_diet
source_url: https://www.avma.org/resources-tools/avma-policies/raw-or-undercooked-animal-source-protein-cat-and-dog-diets
source_title: "Raw or Undercooked Animal-Source Protein in Cat and Dog Diets"
source_date: "2012"
source_publisher: "American Veterinary Medical Association"
license: fair_use
license_note: "AVMA policy text quoted under fair use for research/diagnostic corpus; AVMA holds copyright. Policy originally adopted 2012, periodically reaffirmed; see source page for current revision date."
accessed_on: "2026-06-17"
domain: nutrition_safety

# Cat 3 contradiction pair (side A, higher-trust). Reuses org_us_fda,
# concept_raw_pet_food_safety, concept_salmonella_petfood, and
# concept_listeria_petfood from 2018-02-22-fda-raw-pet-food-safety-study.md
# rather than redeclaring them. Introduces the AVMA organization and the
# AVMA raw-diet policy publication. The cross-note contradicts edge points
# at pub_tapf_raw_review_2012 (declared in
# community_journalism/truth-about-pet-food-raw-review.md, note_id
# cj_tapf_raw_review) so the pair resolves across both files.
entities:
  - id: org_avma
    type: organization
    canonical: "American Veterinary Medical Association"
    aliases: ["AVMA"]
    is_regulatory: false
  - id: pub_avma_raw_diet_policy
    type: publication
    canonical: "AVMA Policy — Raw or Undercooked Animal-Source Protein in Cat and Dog Diets (2012)"
    aliases: ["AVMA raw diet policy", "AVMA raw pet food policy"]
  - id: concept_raw_pet_food_safety
    type: concept
    canonical: "Raw pet food safety risk"
    aliases: ["raw pet food hazards", "raw diet safety", "raw pet food pathogen risk"]
  - id: concept_salmonella_petfood
    type: concept
    canonical: "Salmonella contamination in pet food"
    aliases: ["salmonella in pet food", "Salmonella spp. pet food"]
  - id: concept_listeria_petfood
    type: concept
    canonical: "Listeria monocytogenes contamination in pet food"
    aliases: ["Listeria monocytogenes in pet food", "L. mono pet food"]
  - id: org_us_fda
    type: organization
    canonical: "U.S. Food and Drug Administration"
    is_regulatory: true

edges:
  - from: pub_avma_raw_diet_policy
    type: authored_by
    to: org_avma
    evidence: "Policy statement adopted and published by the American Veterinary Medical Association on avma.org under its AVMA Policies section; AVMA is the corporate author of record."
  - from: pub_avma_raw_diet_policy
    type: subject_of
    to: concept_raw_pet_food_safety
    evidence: "The policy's entire subject is the human- and animal-health risk of feeding raw or undercooked animal-source protein to cats and dogs; the title names the practice and the body states it is discouraged 'because of their risk to human and animal health.'"
  - from: pub_avma_raw_diet_policy
    type: mentions
    to: concept_salmonella_petfood
    evidence: "Policy lists Salmonella spp among the pathogens that may contaminate raw or undercooked animal-sourced protein: 'Raw or undercooked animal-sourced protein may be contaminated with a variety of pathogens, including Salmonella spp...'"
  - from: pub_avma_raw_diet_policy
    type: mentions
    to: concept_listeria_petfood
    evidence: "Policy lists Listeria monocytogenes among the named pathogens of concern in raw or undercooked animal-sourced protein."
  # --- The Cat 3 contradiction binding (cross-note) ---------------------
  # Points at side B's primary publication by its note-id-aligned id so the
  # pair resolves even though that entity is declared in the other file.
  - from: pub_avma_raw_diet_policy
    type: contradicts
    to: pub_tapf_raw_review_2012
    evidence: "Relative-risk disagreement. The AVMA policy discourages raw diets on pathogen-risk grounds, asserting that raw/undercooked animal-source protein 'may be contaminated with a variety of pathogens, including Salmonella spp... [and] Listeria monocytogenes' and that handlers 'are also at risk of becoming sick.' The Truth About Pet Food review (Russell) makes the opposed claim about the same subject — that 'no confirmed cases of human salmonellosis have been associated with these diets' and that the evidence the AVMA cites is weak ('Few of the studies cited in support of the policy include controls and several are little more than anecdotal'). Which side is correct is a human ruling at ingestion; the incompatible relative-risk claim about commercial raw diets is the contradiction."
    needs_grounding: true
  - from: org_us_fda
    type: regulates
    to: concept_raw_pet_food_safety
    evidence: "The FDA, not the AVMA, holds jurisdictional authority over pet food safety under the Federal Food, Drug, and Cosmetic Act; the AVMA policy is a professional-body recommendation rather than a regulatory instrument. This edge records where actual regulatory authority over the raw-pet-food hazard sits (reused org_us_fda from the 2018 FDA raw-pet-food note)."
    needs_grounding: true

tags: [nutrition_safety, raw_food, avma, salmonella, listeria, pathogen_risk, contradiction_pair, side_a_high_trust]
contradiction_pair_id: raw_diet_relative_risk
---

# AVMA Policy — Raw or Undercooked Animal-Source Protein in Cat and Dog Diets

## Summary

The American Veterinary Medical Association maintains a policy discouraging
the feeding of raw or undercooked animal-source protein to cats and dogs on
the grounds that such diets carry pathogen risk to both animals and the
humans who handle them. This is the **higher-trust (professional-body) pole**
of a Cat 3 contradiction pair on the *relative risk* of commercial raw diets.
The opposing pole is a named-author consumer-commentary review hosted at Truth
About Pet Food (`community_journalism/truth-about-pet-food-raw-review.md`,
note_id `cj_tapf_raw_review`), which argues that no confirmed human
salmonellosis has been linked to these diets and that the studies the AVMA
relies on are of mixed quality.

Which side is "correct" is a human ruling at ingestion. This note captures the
AVMA side faithfully and does not adjudicate the dispute.

## What the source states

The policy's operative sentence, quoted verbatim from the live AVMA page
(accessed 2026-06-17):

> "The AVMA discourages feeding any raw or undercooked animal-sourced
> proteins (e.g., meat, poultry, fish, egg, milk) to dogs and cats because of
> their risk to human and animal health."

On the pathogens of concern:

> "Raw or undercooked animal-sourced protein may be contaminated with a
> variety of pathogens, including *Salmonella* spp, *Campylobacter* spp,
> *Clostridium* spp, *Escherichia coli*, *Listeria monocytogenes*, highly
> pathogenic avian influenza (HPAI) virus, *Mycobacterium bovis*, and
> enterotoxigenic *Staphylococcus aureus*."

On the public-health rationale:

> "People handling contaminated raw pet foods are also at risk of becoming
> sick."

## The point of disagreement (Cat 3)

The contradiction is over **relative risk**, not over whether raw protein can
ever carry pathogens (both sides concede contamination is possible). The AVMA
treats the pathogen risk — particularly the zoonotic, handler-facing risk — as
sufficient to discourage the practice outright. The Truth About Pet Food
review counters on three fronts: (1) that *no confirmed cases of human
salmonellosis have been associated with* commercial raw diets, (2) that dry
foods are recalled at least as often, and (3) that the studies underpinning
the AVMA position are largely uncontrolled or anecdotal. The `contradicts`
edge in this note binds the two primary publications; the dissent's own
entities are declared in the side-B note.

This pair is honest about its open status: the relative-risk question is not
settled science, and the note does not imply that it is.

## Why this fits the corpus

- **Cat 3 (contradiction).** Declares an explicit `contradicts` edge from
  `pub_avma_raw_diet_policy` to `pub_tapf_raw_review_2012` (resolved
  cross-note via the side-B note's id). The edge is flagged
  `needs_grounding: true` per `ontology.yaml#contradicts`
  (`requires_human_grounding: true`).
- **Entity reuse.** `org_us_fda`, `concept_raw_pet_food_safety`,
  `concept_salmonella_petfood`, and `concept_listeria_petfood` are reused
  from `nutrition_safety/2018-02-22-fda-raw-pet-food-safety-study.md` rather
  than redeclared, per maintainer guidance.

## Provenance and limitations

The manifest's proposed `expected_source` substring — "The AVMA discourages
the feeding to cats and dogs of any animal-source protein that has not first
been subjected to a process to eliminate pathogens" — **does not appear
verbatim** on the live AVMA page (WebFetch, 2026-06-17). The page's current
wording is the verbatim quote reproduced above. The substring actually used as
this note's stable grep target is therefore
`The AVMA discourages feeding any raw or undercooked animal-sourced proteins`,
which is present verbatim. AVMA policy pages are periodically re-edited and
re-dated; re-confirm against the live page at any future ingestion.

## Sources

- AVMA Policy — Raw or Undercooked Animal-Source Protein in Cat and Dog Diets
  (canonical URL of record):
  https://www.avma.org/resources-tools/avma-policies/raw-or-undercooked-animal-source-protein-cat-and-dog-diets
- Opposing pole (side B, this corpus): Truth About Pet Food — "A Review of
  AVMA Raw Pet Food Policy" (James K. Russell, Ph.D.):
  https://truthaboutpetfood.com/a-review-of-avma-raw-pet-food-policy/
