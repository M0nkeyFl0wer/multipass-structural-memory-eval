---
note_id: cj_100r_grain_free_dcm
source_url: https://100r.org/2022/07/did-industry-funding-influence-an-fda-investigation-into-canine-heart-disease-and-grain-free-dog-food/
source_title: "Did Industry Funding Influence an FDA Investigation into Canine Heart Disease and Grain-Free Dog Food?"
source_date: "2022-07"
source_publisher: "100Reporters"
license: fair_use_excerpt
license_note: "Copyright held by 100Reporters (investigative nonprofit newsroom). Excerpted for non-commercial research under fair use."
accessed_on: "2026-06-17"
domain: community_journalism

# This note is SIDE B of the Cat 3 contradiction pair `grain_free_dcm_causation`.
# It is the lower-trust-but-reputable dissent: investigative journalism that
# reframes the FDA's grain-free / pulse ASSOCIATION as an artifact of reporting
# bias and undisclosed industry ties, rather than a genuine diet-DCM signal.
#
# REUSED (declared elsewhere, referenced by id only — do NOT redeclare):
#   person_lisa_freeman (canonical "Lisa M. Freeman")
#     (vault/veterinary_research/2022-03-freeman-jvim-prospective-dcm-diet.md)
#   org_tufts_cummings (canonical "Cummings School of Veterinary Medicine at Tufts University")
#     (vault/veterinary_research/2022-03-freeman-jvim-prospective-dcm-diet.md)
#   concept_beg_diet (canonical "BEG diet (boutique, exotic-ingredient, or grain-free)")
#     (vault/veterinary_research/2018-11-tufts-petfoodology-beg-dcm.md)
#   concept_grain_free_diet, concept_dcm
#     (vault/veterinary_research/2018-07-fda-dcm-investigation.md)
entities:
  - id: org_100reporters
    type: organization
    canonical: "100Reporters"
    aliases: ["100r.org"]
    is_regulatory: false
  - id: pub_100r_grain_free_dcm_industry_ties
    type: publication
    canonical: "Did Industry Funding Influence an FDA Investigation into Canine Heart Disease and Grain-Free Dog Food? (100Reporters, 2022)"
    aliases: ["100Reporters grain-free DCM investigation"]
  - id: concept_industry_funding_ties
    type: concept
    canonical: "Industry funding and financial ties of investigators"
    aliases: ["industry ties", "undisclosed financial ties", "conflict of interest"]
  - id: concept_reporting_bias
    type: concept
    canonical: "Selective reporting bias in case ascertainment"
    aliases: ["reporting bias", "case ascertainment bias", "selection effect"]

# Edges introduced or strengthened by this note.
edges:
  - from: pub_100r_grain_free_dcm_industry_ties
    type: authored_by
    to: org_100reporters
    evidence: "Article published on 100r.org, the investigative nonprofit newsroom 100Reporters; the piece describes itself as 'A six-month investigation by 100Reporters'."
  - from: pub_100r_grain_free_dcm_industry_ties
    type: mentions
    to: concept_dcm
    evidence: "The article's subject is the FDA investigation into canine heart disease (dilated cardiomyopathy, DCM) and grain-free dog food."
  - from: pub_100r_grain_free_dcm_industry_ties
    type: mentions
    to: concept_grain_free_diet
    evidence: "Verbatim: 'By 2019, approximately 43 percent of dry foods sold were grain-free, reaching $5.4 billion in sales.' The article's central subject is grain-free dog food and its purported DCM link."
  - from: pub_100r_grain_free_dcm_industry_ties
    type: subject_of
    to: concept_industry_funding_ties
    evidence: "Verbatim thesis: 'A six-month investigation by 100Reporters has found that veterinarians who prompted the FDA to consider diet have financial and other ties to the leading sellers of grain-inclusive pet foods.' The primary subject is the investigators' undisclosed industry ties."
  - from: pub_100r_grain_free_dcm_industry_ties
    type: subject_of
    to: concept_reporting_bias
    evidence: "The article argues the case pool was shaped by reporting parameters: it quotes the instruction to report a case 'If patient is eating any diet besides those made by well-known, reputable companies or if eating a boutique, exotic ingredient, or grain-free (BEG) diet', and cites Joseph Bartges: 'When you only look for what you want to see, you only see what you look for.'"
  - from: pub_100r_grain_free_dcm_industry_ties
    type: mentions
    to: concept_beg_diet
    evidence: "The article quotes the reporting instruction singling out 'a boutique, exotic ingredient, or grain-free (BEG) diet' — the BEG framing introduced in the veterinary nutrition literature (concept_beg_diet)."
  - from: pub_100r_grain_free_dcm_industry_ties
    type: mentions
    to: person_lisa_freeman
    evidence: "The article names Dr. Lisa Freeman's center as the source of the reporting instruction that singled out BEG diets, central to its reporting-bias argument."
  - from: person_lisa_freeman
    type: affiliated_with
    to: org_tufts_cummings
    evidence: "Lisa M. Freeman is a professor at the Cummings School of Veterinary Medicine at Tufts University (consistent with the affiliation recorded across the veterinary_research notes); the 100Reporters piece centers her center's reporting guidance."
  # The reciprocal direction of the contradiction is asserted on SIDE A
  # (pub_fda_dcm_grain_free_association -contradicts-> pub_100r_grain_free_dcm_industry_ties).
  # Recorded here as a back-reference comment only; the canonical contradicts edge
  # lives on SIDE A so the pair is wired once and resolves cross-note.

tags: [community_journalism, dcm, grain_free, industry_ties, reporting_bias, beg_diet, contradiction_pair, investigative_journalism, causation_unresolved]
contradiction_pair_id: grain_free_dcm_causation
---

# Did Industry Funding Influence an FDA Investigation into Canine Heart Disease and Grain-Free Dog Food? (100Reporters, 2022)

## Summary

This note is **SIDE B** of the Cat 3 contradiction pair `grain_free_dcm_causation` — the **lower-trust-but-reputable dissent** (`source_tier: reputable_news`, investigative nonprofit). In **July 2022**, the investigative newsroom **100Reporters** published a six-month investigation reframing the FDA's grain-free / pulse → DCM association. Where the FDA (SIDE A) treats the over-representation of grain-free, pulse-heavy diets among reported DCM cases as a genuine diet-DCM signal worth publicizing, 100Reporters argues that the association is **an artifact of selective reporting and undisclosed industry ties** — not evidence that grain-free diets cause DCM.

## What 100Reporters reported

The article's central finding, verbatim (confirmed by fetch, 2026-06-17):

> "A six-month investigation by 100Reporters has found that **veterinarians who prompted the FDA to consider diet have financial and other ties** to the leading sellers of grain-inclusive pet foods."

On the size of the market the grain-free scare affected:

> "By 2019, approximately **43 percent of dry foods sold were grain-free, reaching $5.4 billion in sales**."

On the reporting-bias mechanism — why the case pool may have been pre-shaped:

- The piece reports that veterinarians were instructed to report a case **"If patient is eating any diet besides those made by well-known, reputable companies or if eating a boutique, exotic ingredient, or grain-free (BEG) diet"** — a parameter that, by construction, gathers grain-free cases more readily than grain-inclusive ones.
- It quotes veterinarian Joseph Bartges on the resulting selection effect: **"When you only look for what you want to see, you only see what you look for."**

## The point of disagreement

The contradiction is **not** "FDA says grain-free causes DCM; 100Reporters says it doesn't." The FDA (SIDE A) is careful to frame only a **"potential association"** that **"may involve multiple factors,"** and explicitly does not establish causation. The genuine disagreement is **upstream of causation**: it is over whether the grain-free/pulse over-representation in the FDA's case reports is a **real diet-DCM signal at all**, or whether it is an **artifact** of (a) reporting instructions that singled out BEG diets and (b) the financial ties of the investigators who prompted the diet hypothesis. SIDE A treats the association as load-bearing; SIDE B treats it as confounded.

**Whether grain-free diets cause DCM remains genuinely unresolved**, and which side of this pair is "correct" is a human ruling at ingestion. The corpus records both faithfully and does not adjudicate.

## Tier and honesty labelling

- SIDE B is `reputable_news` — an investigative nonprofit newsroom, **not** a peer-reviewed or government-primary source. It is the **dissent** in this pair, recorded with its tier intact per the corpus adjudication rule (government-primary/peer-reviewed is the default authoritative side; reputable-news/advocacy is the dissent; both are recorded).
- This is **not** a tertiary source (it is the primary investigative report itself), so no Wikipedia/encyclopedic pointer is involved here.
- The cross-note reuse of `person_lisa_freeman` / `org_tufts_cummings` / `concept_beg_diet` is deliberate: the same Freeman / Tufts / BEG entities that anchor the veterinary-research thread are the subjects 100Reporters scrutinizes, giving a Cat 2c multi-hop bridge (`pub_100r_grain_free_dcm_industry_ties -mentions-> person_lisa_freeman -affiliated_with-> org_tufts_cummings`) across the contradiction.

## Provenance and limitations

The source page was fetched directly (HTTP 200) on 2026-06-17. The `expected_source` substring `veterinarians who prompted the FDA to consider diet have financial and other ties` was confirmed verbatim in the fetched page body, as were the 43%/$5.4 billion grain-free market figure and the BEG reporting-instruction / Bartges selection-effect quotes. The frontmatter `source_url` is the canonical URL of record.

## Sources

- 100Reporters — "Did Industry Funding Influence an FDA Investigation into Canine Heart Disease and Grain-Free Dog Food?" (canonical URL of record): https://100r.org/2022/07/did-industry-funding-influence-an-fda-investigation-into-canine-heart-disease-and-grain-free-dog-food/
- Contradiction-pair partner (SIDE A): `vault/nutrition_safety/fda-grain-free-dcm-investigation.md`
- Reused entities: `vault/veterinary_research/2022-03-freeman-jvim-prospective-dcm-diet.md` (Freeman / Tufts), `vault/veterinary_research/2018-11-tufts-petfoodology-beg-dcm.md` (BEG diet)
