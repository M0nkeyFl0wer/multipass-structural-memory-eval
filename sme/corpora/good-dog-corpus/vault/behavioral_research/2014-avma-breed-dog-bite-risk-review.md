---
note_id: pub_avma_breed_bite_review
source_url: https://www.avma.org/sites/default/files/resources/dog_bite_risk_and_prevention_bgnd.pdf
source_title: "Literature Review on the Welfare Implications of the Role of Breed in Dog Bite Risk and Prevention"
source_date: "2014-05-15"
source_publisher: "American Veterinary Medical Association"
license: fair_use_excerpt
license_note: "AVMA literature review (background/welfare-implications document, dated May 15, 2014). The source URL is a PDF; its text was extracted directly (pdftotext) and the required substring plus the review's central conclusions were verified verbatim against that extracted text. No causal breed-to-bite claim is asserted."
accessed_on: "2026-06-18"
domain: behavioral_research

# Ontology-aligned entity declarations introduced by this note.
entities:
  - id: pub_avma_breed_bite_review
    type: publication
    canonical: "Welfare Implications of the Role of Breed in Dog Bite Risk and Prevention (AVMA literature review, 2014)"
    aliases: ["AVMA breed and dog bite review", "AVMA dog bite risk and prevention background"]
  - id: org_avma
    type: organization
    canonical: "American Veterinary Medical Association"
    is_regulatory: false
    aliases: ["AVMA"]
  - id: org_cdc
    type: organization
    canonical: "Centers for Disease Control and Prevention"
    is_regulatory: false
    aliases: ["CDC"]
  - id: breed_german_shepherd_dog
    type: breed
    canonical: "German Shepherd Dog"
    aliases: ["GSD", "German Shepherd", "Alsatian"]
  - id: concept_dog_bite_risk
    type: concept
    canonical: "Dog bite risk"
    aliases: ["bite risk", "dog bite injury risk"]
  - id: concept_breed_specific_legislation
    type: concept
    canonical: "Breed-specific legislation"
    aliases: ["BSL", "breed bans", "breed-specific laws"]

# Edges introduced by this note (the GROUND TRUTH the graph is measured against).
edges:
  - from: pub_avma_breed_bite_review
    type: authored_by
    to: org_avma
    evidence: "The literature review was produced and published by the American Veterinary Medical Association as one of its welfare-implications background documents."
  - from: pub_avma_breed_bite_review
    type: cites
    to: org_cdc
    evidence: "The review aggregates breed-attributed fatality data spanning periods such as '1979-1998 Fatalities' (CDC dog-bite-related fatality surveillance) in its Table 1 summary of bite-injury data."
  - from: pub_avma_breed_bite_review
    type: mentions
    to: breed_german_shepherd_dog
    evidence: "Verbatim from the review: 'These prevalence referenced studies attribute higher risk to the German Shepherd Dog and crosses ... and various other breeds'."
  - from: pub_avma_breed_bite_review
    type: subject_of
    to: concept_dog_bite_risk
    evidence: "The review's stated subject is the role of breed in dog bite risk and prevention; verbatim conclusion: 'Given that breed is a poor sole predictor of aggressiveness ... it is difficult to support the targeting of this breed as a basis for dog bite prevention.'"
  - from: pub_avma_breed_bite_review
    type: subject_of
    to: concept_breed_specific_legislation
    evidence: "The review is framed as relevant to breed-specific legislation, examining whether breed identity is a sound basis for bite-prevention policy."

tags: [behavioral_research, dog_bite, breed, breed_specific_legislation, AVMA, CDC, epidemiology, welfare]
---

# AVMA — Welfare Implications of the Role of Breed in Dog Bite Risk and Prevention (2014)

## Summary

On **May 15, 2014** the **American Veterinary Medical Association (AVMA)** published a dense, citation- and table-heavy document titled *"Literature Review on the Welfare Implications of the Role of Breed in Dog Bite Risk and Prevention."* The review surveys the epidemiological literature on whether a dog's breed predicts its likelihood of biting, paying particular attention to studies that control for the underlying population prevalence of each breed. Its central conclusion is cautionary: **breed is a poor sole predictor** of aggressiveness and therefore of bite risk. Reported over-representation of particular breeds varies substantially from study to study and is confounded by reporting bias and by how common each breed is in the local population. The review is widely cited in debates over **breed-specific legislation (BSL)**, because its findings undercut the premise that targeting named breeds is an effective bite-prevention strategy.

## What the source reported

The review aggregates bite and fatality data across multiple studies and jurisdictions, summarized in tables that include fatality windows such as "1979-1998 Fatalities" drawn from **CDC** dog-bite-related fatality surveillance. A recurring methodological theme is that raw counts of bites attributed to a breed are uninterpretable without the denominator — the number of dogs of that breed in the population. The review cites a Rome, Italy study in which molosser dogs "were not disproportionately involved in biting incidents when taking into account their prevalence in the community." A breed that is numerically common will appear frequently in bite reports even at an average or below-average per-dog rate.

Different studies implicate different breeds, and the rankings are unstable across time and place. As the review puts it, prevalence-referenced studies attribute **"higher risk to the German Shepherd Dog and crosses"** and various other breeds — while elsewhere it notes that fatal attacks in some areas of Canada are attributed mainly to sled dogs and Siberian Huskies, presumably from regional prevalence. The review treats this divergence as evidence that breed-level rankings are artifacts of local population composition and reporting practices rather than stable biological propensities. Breed identification in bite reports is itself unreliable, frequently based on visual guesses rather than verified pedigree ("Visual determination of dog breed is known to not always be reliable"), which further degrades any breed-to-bite inference.

The review does **not** assert that any breed causes bites. It frames bite risk as multifactorial — training method, sex and neutering status, the target (owner versus stranger), and the context in which the dog is kept (urban versus rural) — and concludes that "Given that breed is a poor sole predictor of aggressiveness ... it is difficult to support the targeting of this breed as a basis for dog bite prevention." It even notes owner correlations may have "the owner's behavior as the underlying causal factor." CDC fatality figures are scale-of-problem context, not a basis for breed-targeted policy; the CDC itself has disclaimed the use of its breed data for policy purposes.

## Why this fits the corpus

This note serves two SME categories:

- **cat_7 (token/efficiency).** The source is deliberately dense — citation-heavy, with tables and per-study breakdowns. It is a good probe for whether a memory system can extract the load-bearing conclusion ("breed is a poor sole predictor") without being dragged into every per-study number, and whether it spends tokens proportionate to signal.
- **cat_2c (multi-hop).** The `authored_by` (review → AVMA) and `cites` (review → CDC) edges, combined with `mentions` (review → German Shepherd Dog) and the two `subject_of` edges to dog bite risk and breed-specific legislation, set up multi-hop traversals such as: *which organization authored a review that both cites the CDC and bears on breed-specific legislation?* It also cross-links to the corpus's municipal-policy BSL thread (Montreal, Denver, Calgary, Ontario) through the shared `concept_breed_specific_legislation` node and to the breed-standards thread through the shared `breed_german_shepherd_dog` node.

## Provenance and limitations

The source URL is a PDF. The automated WebFetch reader could not surface the exact substring (PDF-to-markdown limits), so the PDF text was extracted directly with `pdftotext` and the required substring *"higher risk to the German Shepherd Dog and crosses"* plus the review's central conclusions ("breed is a poor sole predictor of aggressiveness"; the Rome molosser prevalence finding; the multifactorial framing) were verified verbatim against that extracted text. `expected_source_verified` is therefore **true**. Crucially, **no causal claim** is made: the review's own position is that breed is a confounded and unreliable sole predictor of bite risk, and the CDC disclaims policy use of its breed-attribution data. Any reader of this note should treat per-breed over-representation findings as study-specific and confounded, not as evidence that a breed causes bites.

## Sources

- AVMA literature review (PDF): https://www.avma.org/sites/default/files/resources/dog_bite_risk_and_prevention_bgnd.pdf
- AVMA dog bite resources landing page: https://www.avma.org/resources-tools/animal-health-and-welfare/dog-bite-prevention
- CDC dog-bite-related fatality literature (cited within the review) — CDC has stated its breed data should not be used for breed-specific policy.
