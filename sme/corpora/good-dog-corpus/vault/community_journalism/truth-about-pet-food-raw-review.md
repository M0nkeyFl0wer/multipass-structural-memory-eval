---
note_id: cj_tapf_raw_review
source_url: https://truthaboutpetfood.com/a-review-of-avma-raw-pet-food-policy/
source_title: "A Review of AVMA Raw Pet Food Policy"
source_date: "2012"
source_publisher: "Truth About Pet Food (truthaboutpetfood.com)"
source_author: "James K. Russell, Ph.D."
source_tier: other
license: fair_use
license_note: "Consumer-advocacy commentary quoted under fair use for research/diagnostic corpus. Truth About Pet Food (Susan Thixton) holds copyright; guest review authored by James K. Russell, Ph.D., advisor to The Pawsitive Packleader, Inc."
accessed_on: "2026-06-17"
domain: community_journalism

# Cat 3 contradiction pair (side B, lower-trust advocacy / named-author
# consumer commentary). Declares the side-B primary publication
# (pub_tapf_raw_review_2012) that side A's contradicts edge points back at.
# Reuses concept_raw_pet_food_safety and concept_salmonella_petfood from
# the 2018 FDA raw-pet-food note, and reuses org_avma as declared in the
# side-A note (nut_avma_raw_diet). The named author is a new person entity.
entities:
  - id: pub_tapf_raw_review_2012
    type: publication
    canonical: "A Review of AVMA Raw Pet Food Policy (Truth About Pet Food, Russell)"
    aliases: ["TAPF AVMA raw policy review", "Truth About Pet Food raw policy review"]
  - id: person_james_k_russell
    type: person
    canonical: "James K. Russell"
    aliases: ["James K. Russell, Ph.D.", "J. K. Russell"]
  - id: org_avma
    type: organization
    canonical: "American Veterinary Medical Association"
    aliases: ["AVMA"]
    is_regulatory: false
  - id: concept_raw_pet_food_safety
    type: concept
    canonical: "Raw pet food safety risk"
    aliases: ["raw pet food hazards", "raw diet safety", "raw pet food pathogen risk"]
  - id: concept_salmonella_petfood
    type: concept
    canonical: "Salmonella contamination in pet food"
    aliases: ["salmonella in pet food", "Salmonella spp. pet food"]

edges:
  - from: pub_tapf_raw_review_2012
    type: authored_by
    to: person_james_k_russell
    evidence: "Byline on the article reads 'James K. Russell, Ph. D.' with a note that he is an advisor to The Pawsitive Packleader, Inc.; the piece is a guest review hosted on Truth About Pet Food (WebFetch, 2026-06-17)."
  - from: pub_tapf_raw_review_2012
    type: subject_of
    to: concept_raw_pet_food_safety
    evidence: "The review's entire subject is a critique of the AVMA's raw-pet-food safety policy and the evidence behind its pathogen-risk claims."
  - from: pub_tapf_raw_review_2012
    type: mentions
    to: org_avma
    evidence: "The article is titled 'A Review of AVMA Raw Pet Food Policy' and directly critiques the American Veterinary Medical Association's policy throughout."
  - from: pub_tapf_raw_review_2012
    type: mentions
    to: concept_salmonella_petfood
    evidence: "The review's central counter-claim concerns human salmonellosis: 'no confirmed cases of human salmonellosis have been associated with these diets.'"

# Note: no supersedes or alias_of edge is written for this pair. The two
# publications are contemporaneous and stand in a contradicts relation, not a
# temporal-replacement (supersedes) one; and they are distinct documents with
# no shared canonical identity, so alias_of (which ontology.yaml constrains to
# same-type, same-entity surface forms) does not apply. The contradicts edge
# is declared once, on side A (nut_avma_raw_diet), pointing at
# pub_tapf_raw_review_2012 here.

tags: [community_journalism, raw_food, avma, salmonella, advocacy, consumer_commentary, contradiction_pair, side_b_dissent, tertiary_quality_flag]
contradiction_pair_id: raw_diet_relative_risk
---

# Truth About Pet Food — A Review of AVMA Raw Pet Food Policy

## Summary

This is a named-author consumer-commentary review, by James K. Russell, Ph.D.,
hosted on Truth About Pet Food (Susan Thixton's consumer-advocacy site). It is
the **lower-trust (advocacy) pole** of a Cat 3 contradiction pair on the
*relative risk* of commercial raw diets. The opposing pole is the AVMA's own
professional-body policy
(`nutrition_safety/avma-raw-diet-policy.md`, note_id `nut_avma_raw_diet`),
which discourages raw feeding on pathogen-risk grounds.

Source tier is `other` (advocacy / consumer commentary). Which side is
"correct" is a human ruling at ingestion; this note captures the dissent
faithfully and does not adjudicate.

## What the source argues

The review's central counter-claim, quoted verbatim (WebFetch, 2026-06-17):

> "no confirmed cases of human salmonellosis have been associated with these
> diets"

On the quality of the evidence the AVMA cites:

> "Few of the studies cited in support of the policy include controls and
> several are little more than anecdotal."

> "Descriptions of methods are restricted to the methods of handling for
> fecal samples with no mention of food preparation methods or hygienic
> measures."

The review also situates the salmonella concern in the broader context that
contamination has driven recalls of conventional commercial dog food as well —
the basis for the "dry foods are recalled more often" line in the manifest's
point-of-disagreement summary. (Note: the live page makes the recall point in
passing; it does not present a quantified raw-vs-dry recall-frequency
comparison — see Provenance and limitations.)

## The point of disagreement (Cat 3)

The disagreement is over **relative risk**. The AVMA holds that the pathogen
risk of raw diets — especially the zoonotic, handler-facing risk — is
sufficient to discourage the practice. This review counters that the human
salmonellosis risk specifically attributed to *commercial* raw diets is
unconfirmed, that the supporting studies are largely uncontrolled or
anecdotal, and that conventional dry foods are subject to recalls too. The
incompatible claim about the relative risk of commercial raw diets is the
contradiction. The `contradicts` edge that binds the two primary publications
is declared on the side-A note and points back at this note's
`pub_tapf_raw_review_2012`.

This pair is genuinely unresolved: the relative-risk question is not settled
science, and this note does not imply that it is.

## Why this fits the corpus

- **Cat 3 (contradiction).** Declares `pub_tapf_raw_review_2012`, the side-B
  primary publication that the side-A `contradicts` edge resolves to. The two
  notes share `contradiction_pair_id: raw_diet_relative_risk`.
- **Entity reuse.** `org_avma` is reused from the side-A note;
  `concept_raw_pet_food_safety` and `concept_salmonella_petfood` are reused
  from `nutrition_safety/2018-02-22-fda-raw-pet-food-safety-study.md`.
- **Tier honesty.** Source tier `other` is recorded in the frontmatter and
  tagged `tertiary_quality_flag`; the dissent is reputable-but-advocacy, not a
  peer-reviewed or government-primary source.

## Provenance and limitations

Both the human-salmonellosis substring and the study-quality critique were
confirmed verbatim against the live page via WebFetch (2026-06-17). The byline
("James K. Russell, Ph. D.") was confirmed in a separate fetch. The page does
**not** present a quantified raw-vs-dry recall-frequency comparison — the
"dry foods are recalled more often" framing comes from the manifest's
point-of-disagreement summary and the article's passing mention of dry-food
recalls, not from a numeric comparison on this page. Re-confirm at any future
ingestion; advocacy pages are edited without version markers.

## Sources

- Truth About Pet Food — "A Review of AVMA Raw Pet Food Policy" (James K.
  Russell, Ph.D.; canonical URL of record):
  https://truthaboutpetfood.com/a-review-of-avma-raw-pet-food-policy/
- Opposing pole (side A, this corpus): AVMA Policy — Raw or Undercooked
  Animal-Source Protein in Cat and Dog Diets:
  https://www.avma.org/resources-tools/avma-policies/raw-or-undercooked-animal-source-protein-cat-and-dog-diets
