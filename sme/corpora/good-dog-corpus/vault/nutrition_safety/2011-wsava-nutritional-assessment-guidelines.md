---
note_id: nut_wsava_nutritional_assessment_guidelines_2011
source_url: https://wsava.org/wp-content/uploads/2020/01/WSAVA-Nutrition-Assessment-Guidelines-2011-JSAP.pdf
source_title: "WSAVA Nutritional Assessment Guidelines"
source_date: "2011"
source_publisher: "Journal of Small Animal Practice (WSAVA)"
license: fair_use_excerpt
accessed_on: "2026-06-18"
domain: nutrition_safety

# Reuses canonical org_wsava and org_aaha; introduces the guidelines
# publication node and the two nutrition concepts. Authored from text
# extracted directly from the canonical PDF (pdftotext), so all four edges
# are grounded against quoted source text.
entities:
  - id: org_wsava
    type: organization
    canonical: "World Small Animal Veterinary Association"
    aliases: ["WSAVA", "World Small Animal Veterinary Association (WSAVA)", "WSAVA 5th Vital Assessment Group", "WSAVA Global Nutrition Committee"]
  - id: org_aaha
    type: organization
    canonical: "American Animal Hospital Association"
    aliases: ["AAHA", "American Animal Hospital Association (AAHA)"]
  - id: pub_wsava_nutritional_assessment_2011
    type: publication
    canonical: "WSAVA Nutritional Assessment Guidelines (JSAP, 2011)"
    aliases: ["WSAVA Nutritional Assessment Guidelines", "WSAVA Global Nutritional Assessment Guidelines"]
  - id: concept_nutritional_assessment
    type: concept
    canonical: "Nutritional assessment"
    aliases: ["5th Vital Assessment", "fifth vital assessment", "fifth vital sign", "nutritional evaluation"]
  - id: concept_body_condition_score
    type: concept
    canonical: "Body condition score"
    aliases: ["BCS", "9-point body condition score", "body condition scoring"]

edges:
  - from: pub_wsava_nutritional_assessment_2011
    type: authored_by
    to: org_wsava
    evidence: "\"The WSAVA 5th Vital Assessment Group (V5) has utilized the science-based Nutritional Assessment Guidelines from the American Animal Hospital Association (AAHA) to develop global Nutritional Assessment Guidelines\"; published \"© 2011 WSAVA\" in the Journal of Small Animal Practice"
  - from: pub_wsava_nutritional_assessment_2011
    type: cites
    to: org_aaha
    evidence: "\"The WSAVA 5th Vital Assessment Group (V5) has utilized the science-based Nutritional Assessment Guidelines from the American Animal Hospital Association (AAHA) to develop global Nutritional Assessment Guidelines\"; AAHA is also listed in the references as \"AAHA American Animal Hospital Association http://www.aahanet.org\""
  - from: pub_wsava_nutritional_assessment_2011
    type: subject_of
    to: concept_nutritional_assessment
    evidence: "The guidelines designate nutritional assessment as the \"5th Vital Assessment\": \"Incorporating the screening evaluation described in these guidelines as the fifth vital sign in the standard physical examination requires little to no additional time or cost.\""
  - from: pub_wsava_nutritional_assessment_2011
    type: mentions
    to: concept_body_condition_score
    evidence: "\"these guidelines will use a 9-point scale\" and \"The goal for most pets is a BCS of 4 to 5 of 9.\""

tags: [nutrition_safety, wsava, aaha, body_condition_score, nutritional_assessment, peer_reviewed, jsap, vital_assessment, cat_7, token_efficiency]
---

# WSAVA Nutritional Assessment Guidelines (JSAP, 2011)

## Summary

The **WSAVA Nutritional Assessment Guidelines** are a dense, reference-heavy
professional-society document published by the World Small Animal Veterinary
Association in the **Journal of Small Animal Practice (JSAP)** in 2011. Their
central contribution is to formalize nutritional assessment as a routine,
expected part of every small-animal clinical examination. The guidelines —
developed by the **WSAVA 5th Vital Assessment Group (V5)** — designate
nutritional assessment as the **"5th Vital Assessment"**: a fifth vital sign
to be evaluated at every patient visit, alongside temperature, pulse,
respiration, and pain. They prescribe a screening-then-extended assessment
workflow and standardize the **9-point body condition score (BCS)** scale with
an ideal goal of **BCS 4-5 of 9**.

In this corpus the note serves primarily as a **token/efficiency (Cat 7)**
stress source: it is a reference-dense, terminology-heavy guideline whose
load-bearing facts (the "5th Vital Assessment" label, the 9-point scale, the
4-5/9 goal range, the AAHA lineage) are scattered through a long professional
document, so a memory system must compress it without dropping the small set of
facts that actually matter.

## What the source reported

Extracted directly from the canonical PDF:

- The **WSAVA 5th Vital Assessment Group (V5)** "has utilized the science-based
  Nutritional Assessment Guidelines from the **American Animal Hospital
  Association (AAHA)** to develop global Nutritional Assessment Guidelines." The
  WSAVA guidelines are thus explicitly derived from, and cite, the prior AAHA
  nutritional-assessment work.
- Nutritional assessment is framed as the **fifth vital sign**: "Incorporating
  the screening evaluation described in these guidelines as the fifth vital sign
  in the standard physical examination requires little to no additional time or
  cost." It is conducted as a routine screen at every veterinary visit and
  escalated to an extended evaluation when risk factors are present.
- The guidelines use a **9-point BCS scale** — "these guidelines will use a
  9-point scale" — noting that a variety of systems exist (scales of 5, 6, 7,
  or 9). The recommended target is explicit: "The goal for most pets is a BCS of
  4 to 5 of 9," with disease-risk associations appearing to increase above 6 of 9.
- The document distinguishes BCS from a separate **muscle condition score
  (MCS)**, and was published in the **Journal of Small Animal Practice** in
  **2011** ("Journal of Small Animal Practice • Vol 00 • June 2011 • © 2011
  WSAVA").

The guidelines are descriptive clinical-practice guidance — a recommended
screening framework — rather than regulation; they carry no enforcement
authority and complement, rather than supersede, the FDA/AAFCO regulatory
material elsewhere in this corpus.

## Why this fits the corpus

This note primarily serves **cat_7 (token / efficiency, "The Abacus")**. It is
intentionally a "dense, reference-heavy professional guideline": the kind of
document where the ratio of prose to load-bearing fact is high. A memory system
indexing it must preserve a compact set of retrievable facts — the **"5th Vital
Assessment"** designation, the **9-point BCS** scale, the **4-5/9** goal, and
the **AAHA** lineage — while discarding boilerplate. Token-efficiency tests can
measure whether retrieval surfaces those four facts without bloating context
with the surrounding guideline scaffolding.

Secondarily, the note reinforces the nutrition_safety domain's
**who-recommends-practice vs who-regulates** distinction (WSAVA/AAHA recommend
clinical practice; FDA/AAFCO regulate), and the `cites(AAHA)` edge gives a small
multi-hop path (WSAVA guideline → AAHA prior guideline) for traversal tests.

## Provenance and limitations

The canonical source is a 12-page **PDF** hosted on wsava.org. A direct WebFetch
against the PDF URL returned the binary as compressed/encoded content and the
fast extraction model could not read it, so the maintainer downloaded the file
locally and ran `pdftotext` against it. Every quoted passage above — including
the verbatim phrase **"5th Vital Assessment"**, the "fifth vital sign" sentence,
the "9-point scale" choice, and the "BCS of 4 to 5 of 9" goal — was confirmed
present in the extracted text, so `expected_source_verified` is **true** for
this note. (This supersedes an earlier manifest-only authoring of the same note
in which the edges were flagged `needs_grounding`.)

No causal or regulatory claim is made: these guidelines are clinical-practice
recommendations, not a regulatory standard, and nothing here implies they have
legal force. The note does not bear on the grain-free/DCM question, on which the
FDA has stated no causal link has been established.

## Sources

- WSAVA Nutritional Assessment Guidelines, Journal of Small Animal Practice,
  2011 (canonical PDF of record):
  https://wsava.org/wp-content/uploads/2020/01/WSAVA-Nutrition-Assessment-Guidelines-2011-JSAP.pdf
- WSAVA Global Nutrition Committee / Global Nutrition Toolkit landing:
  https://wsava.org/global-guidelines/global-nutrition-guidelines/
