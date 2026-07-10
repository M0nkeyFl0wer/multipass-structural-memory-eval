---
note_id: nut_wsava_nutritional_assessment_guidelines_2011
source_url: https://wsava.org/wp-content/uploads/2020/01/WSAVA-Nutrition-Assessment-Guidelines-2011-JSAP.pdf
source_title: "WSAVA Nutritional Assessment Guidelines"
source_date: "2011"
source_publisher: "Journal of Small Animal Practice (WSAVA)"
license: fair_use_excerpt
accessed_on: "2026-06-18"
domain: nutrition_safety

# Reuses org_wsava and org_aaha if already declared elsewhere; this note
# introduces the guidelines publication node and the two nutrition concepts.
entities:
  - id: org_wsava
    type: organization
    canonical: "World Small Animal Veterinary Association"
    aliases: ["WSAVA", "World Small Animal Veterinary Association (WSAVA)"]
  - id: org_aaha
    type: organization
    canonical: "American Animal Hospital Association"
    aliases: ["AAHA"]
  - id: pub_wsava_nutritional_assessment_2011
    type: publication
    canonical: "WSAVA Nutritional Assessment Guidelines (JSAP, 2011)"
    aliases: ["WSAVA Nutritional Assessment Guidelines", "WSAVA Global Nutrition Committee Nutritional Assessment Guidelines 2011"]
  - id: concept_nutritional_assessment
    type: concept
    canonical: "Nutritional assessment"
    aliases: ["5th Vital Assessment", "fifth vital assessment", "nutritional evaluation"]
  - id: concept_body_condition_score
    type: concept
    canonical: "Body condition score"
    aliases: ["BCS", "9-point body condition score", "body condition scoring"]

edges:
  - from: pub_wsava_nutritional_assessment_2011
    type: authored_by
    to: org_wsava
    evidence: "Guidelines developed by the WSAVA Global Nutrition Committee and published under the World Small Animal Veterinary Association; hosted on wsava.org"
  - from: pub_wsava_nutritional_assessment_2011
    type: cites
    to: org_aaha
    evidence: "Guidelines reference the American Animal Hospital Association (AAHA) nutritional assessment work as a basis for incorporating nutrition into routine clinical evaluation"
    needs_grounding: true
  - from: pub_wsava_nutritional_assessment_2011
    type: subject_of
    to: concept_nutritional_assessment
    evidence: "The guidelines designate nutritional assessment as the '5th Vital Assessment' to be performed at every patient visit alongside temperature, pulse, respiration, and pain"
  - from: pub_wsava_nutritional_assessment_2011
    type: mentions
    to: concept_body_condition_score
    evidence: "Guidelines describe a 9-point body condition score (BCS) scale with an ideal goal BCS of 4-5 of 9"

tags: [nutrition_safety, wsava, aaha, body_condition_score, nutritional_assessment, peer_reviewed, jsap, vital_assessment, cat_7, token_efficiency]
---

# WSAVA Nutritional Assessment Guidelines (JSAP, 2011)

## Summary

The **WSAVA Nutritional Assessment Guidelines** are a dense, reference-heavy
professional-society document published by the World Small Animal Veterinary
Association in the **Journal of Small Animal Practice (JSAP)** in 2011. Their
central contribution is to formalize nutritional assessment as a routine,
expected part of every small-animal clinical examination: the guidelines
designate nutritional assessment as the **"5th Vital Assessment"** — a fifth
vital sign to be evaluated at every patient visit, alongside temperature,
pulse, respiration, and pain. They prescribe a screening-then-extended
assessment workflow and standardize the **9-point body condition score (BCS)**
scale with an ideal goal of **BCS 4-5 of 9**.

In this corpus the note serves primarily as a **token/efficiency (Cat 7)**
stress source: it is a reference-dense, terminology-heavy guideline whose
load-bearing facts (the "5th Vital Assessment" label, the 9-point scale, the
4-5/9 goal range, the AAHA lineage) are scattered through a long professional
document, so a memory system must compress it without dropping the small set
of facts that actually matter.

## What the source reported

Per the manifest-verified facts for this source:

- Nutritional assessment is designated as the **"5th Vital Assessment"**, to be
  conducted as a routine screening at every veterinary visit and escalated to an
  extended evaluation when risk factors are present.
- The guidelines use a **9-point body condition score (BCS) scale**, with an
  ideal/goal condition of **BCS 4-5 of 9**.
- The document **references AAHA** (the American Animal Hospital Association),
  whose own nutritional-assessment work is part of the lineage that established
  nutrition as a routine clinical screen.
- It was published in the **Journal of Small Animal Practice** in **2011** under
  the World Small Animal Veterinary Association, by the WSAVA Global Nutrition
  Committee.

The guidelines are descriptive clinical-practice guidance — a recommended
screening framework — rather than regulation; they carry no enforcement
authority and complement, rather than supersede, the FDA/AAFCO regulatory
material elsewhere in this corpus.

## Why this fits the corpus

This note primarily serves **cat_7 (token / efficiency)**. It is intentionally a
"dense, reference-heavy professional guideline": the kind of document where the
ratio of prose to load-bearing fact is high. A memory system indexing it must
preserve a compact set of retrievable facts — the **"5th Vital Assessment"**
designation, the **9-point BCS** scale, the **4-5/9** goal, and the **AAHA**
reference — while discarding boilerplate. Token-efficiency tests can measure
whether retrieval surfaces those four facts without bloating context with the
surrounding guideline scaffolding.

Secondarily, the note reinforces the nutrition_safety domain's
**who-recommends-practice vs who-regulates** distinction (WSAVA/AAHA recommend
clinical practice; FDA/AAFCO regulate), complementing the existing WSAVA Global
Nutrition Guidelines source already indexed in the nutrition_safety manifest.

## Provenance and limitations

The canonical source is a **PDF** hosted on wsava.org. A direct WebFetch against
the PDF URL on 2026-06-18 returned the binary as compressed/encoded content and
the fast extraction model could **not** confirm the verbatim presence of the
"5th Vital Assessment" phrase or the BCS figures from the extracted text — so
`expected_source_verified` is set **false** for this note. All factual claims
above are taken from the manifest-verified facts supplied for this source
(already fact-checked at manifest assembly) and from the publisher metadata; the
phrase **"5th Vital Assessment"** is reproduced here verbatim as supplied by the
manifest. A future revision should re-extract the PDF text directly (e.g. with a
local PDF-to-text pass) and ground the `cites(AAHA)` and `subclass_of` edges
against the live guideline text — both are flagged `needs_grounding: true`.

No causal or regulatory claim is made: these guidelines are clinical-practice
recommendations, not a regulatory standard, and nothing here implies the
guidelines have legal force.

## Sources

- WSAVA Nutritional Assessment Guidelines, Journal of Small Animal Practice,
  2011 (canonical PDF of record):
  https://wsava.org/wp-content/uploads/2020/01/WSAVA-Nutrition-Assessment-Guidelines-2011-JSAP.pdf
- WSAVA Global Nutrition Committee / Global Nutrition Toolkit landing:
  https://wsava.org/global-guidelines/global-nutrition-guidelines/
