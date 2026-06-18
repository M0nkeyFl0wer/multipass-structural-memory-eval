---
note_id: beh_sacks_javma_2000_fatal_attacks
source_url: https://pubmed.ncbi.nlm.nih.gov/10997153/
source_title: "Breeds of dogs involved in fatal human attacks in the United States between 1979 and 1998"
source_date: "2000-09-15"
source_publisher: "Journal of the American Veterinary Medical Association 217(6): 836-840 (PubMed abstract record, PMID 10997153)"
license: fair_use_excerpt
license_note: "JAVMA peer-reviewed article; full text paywalled (avmajournals.avma.org returned HTTP 403). The PubMed abstract record (PMID 10997153) is the fetchable canonical-of-record used here; abstract phrases excerpted under fair use with attribution. Authors include CDC and AVMA staff."
accessed_on: "2026-06-17"
domain: behavioral_research

# Cat 3 contradiction pair: breed_predicts_bite_risk. This is SIDE B
# (the breed-disproportion / breed-risk pole). Grounded on the JAVMA
# 2000 PRIMARY (Sacks et al.) rather than the tertiary Wikipedia
# pointer the manifest supplied; the Wikipedia summary is retained
# only as a labeled tertiary cross-reference. Declares
# pub_sacks_javma_2000 so side A's contradicts edge resolves to it.
# Reuses concept_pit_bull, breed_rottweiler, org_cdc, org_avma,
# concept_bsl from existing notes / side A.
entities:
  - id: pub_sacks_javma_2000
    type: publication
    canonical: "Breeds of dogs involved in fatal human attacks in the United States between 1979 and 1998 (Sacks et al., JAVMA 2000;217(6):836-840)"
    aliases: ["Sacks et al. 2000", "Sacks 2000 JAVMA DBRF study", "PMID 10997153"]
  - id: person_jeffrey_sacks
    type: person
    canonical: "Jeffrey J. Sacks"
    aliases: ["Sacks JJ", "J. J. Sacks"]
  - id: concept_dbrf
    type: concept
    canonical: "Dog-bite-related fatality (DBRF)"
    aliases: ["DBRF", "dog-bite-related fatalities", "fatal dog attack"]

edges:
  - from: pub_sacks_javma_2000
    type: authored_by
    to: person_jeffrey_sacks
    evidence: "Sacks JJ is the first author of the byline 'Sacks JJ, Sinclair L, Gilchrist J, Golab GC, Lockwood R' on JAVMA 2000;217(6):836-840, confirmed by the PubMed record (PMID 10997153)."
  - from: pub_sacks_javma_2000
    type: subject_of
    to: concept_dbrf
    evidence: "The paper's subject is dog-bite-related human fatalities (DBRF) by breed; the abstract states 'At least 25 breeds of dogs have been involved in 238 human DBRF during the past 20 years.'"
  - from: pub_sacks_javma_2000
    type: mentions
    to: concept_pit_bull
    evidence: "Abstract names pit-bull-type dogs as a primary breed implicated: 'Pit bull-type dogs and Rottweilers were involved in more than half of these deaths.'"
  - from: pub_sacks_javma_2000
    type: mentions
    to: breed_rottweiler
    evidence: "Abstract names the Rottweiler alongside pit-bull-type dogs: 'Pit bull-type dogs and Rottweilers were involved in more than half of these deaths.'"
  - from: pub_sacks_javma_2000
    type: mentions
    to: org_cdc
    evidence: "The study is a CDC analysis (lead author Sacks and co-author Gilchrist are CDC; the work uses CDC/HSUS DBRF surveillance data spanning 1979-1998), making the CDC the data-owning body the breed-risk debate cites."
    needs_grounding: true
  - from: pub_sacks_javma_2000
    type: mentions
    to: concept_bsl
    evidence: "The abstract addresses breed-specific ordinances directly: 'Because of difficulties inherent in determining a dog's breed with certainty, enforcement of breed-specific ordinances raises constitutional and practical issues' and 'Many practical alternatives to breed-specific ordinances exist.'"
  # --- Reciprocal half of the Cat 3 binding (cross-note) -----------
  # Side A (pub_avma_bsl_not_answer, in
  # municipal_policy/avma-bsl-not-the-answer.md) carries the primary
  # contradicts edge A -> B. A reciprocal B -> A edge is declared here
  # so the contradiction is bound from both notes. Both carry
  # contradiction_pair_id: breed_predicts_bite_risk.
  - from: pub_sacks_javma_2000
    type: contradicts
    to: pub_avma_bsl_not_answer
    evidence: "Point of disagreement = whether breed predicts bite risk. Sacks et al. report a breed disproportion ('Pit bull-type dogs and Rottweilers were involved in more than half' of 238 DBRF, 1979-1998), the empirical basis breed-risk advocates cite for breed carrying predictive signal. The AVMA position page (pub_avma_bsl_not_answer) asserts the opposite predicate: 'Any dog can bite, regardless of its breed' and that the breed->bite-risk connection is 'weak or absent.' Opposed claims about the same breed->risk predicate. NOTE: this is a partial contradiction — both publications independently caution against breed-specific ordinances on enforcement grounds, so the conflict is over breed's PREDICTIVE value, not over BSL policy itself. Which side is authoritative is a human ruling at ingestion."
    requires_human_grounding: true

tags: [behavioral_research, dbrf, fatal_dog_attacks, breed_risk, pit_bull, rottweiler, cdc, sacks_2000, contradiction_pair, breed_bite_risk, side_b]
contradiction_pair_id: breed_predicts_bite_risk
---

# Sacks et al. (JAVMA 2000) — Breeds of Dogs Involved in Fatal Human Attacks, 1979–1998

## Summary

This 2000 CDC study (Sacks, Sinclair, Gilchrist, Golab & Lockwood, *Journal of the American Veterinary Medical Association* 217(6): 836–840) analyzed 20 years of U.S. dog-bite-related human fatalities (DBRF) by breed. Its headline empirical finding — that **pit-bull-type dogs and Rottweilers were "involved in more than half"** of the 238 fatalities studied — is the most-cited evidentiary basis for the **breed-risk** view that breed carries predictive signal for severe-bite/fatality risk.

This is **side B** (the breed-disproportion pole) of the Cat 3 contradiction pair `breed_predicts_bite_risk`. The opposing pole is **side A**, the AVMA's breed-neutral position (`municipal_policy/avma-bsl-not-the-answer.md`). **Which side is correct is a human ruling** — this note captures the breed-risk finding faithfully without adjudicating it.

## What the source reported

Verbatim from the abstract (confirmed by direct fetch of the PubMed record, PMID 10997153, on 2026-06-17):

> "At least 25 breeds of dogs have been involved in 238 human DBRF during the past 20 years."

> "Pit bull-type dogs and Rottweilers were involved in more than half of these deaths."

On policy — and this is the crucial honesty caveat for the pair — the same abstract states:

> "Because of difficulties inherent in determining a dog's breed with certainty, enforcement of breed-specific ordinances raises constitutional and practical issues."

> "Many practical alternatives to breed-specific ordinances exist and hold promise for prevention of dog bites."

So the authors who produced the breed-disproportion *finding* did **not** endorse breed-specific *legislation*.

## The point of disagreement

The narrow contradiction with side A is over the **predictive** claim:

- **Side B (this note):** pit-bull-type dogs and Rottweilers are disproportionately represented in fatal attacks (>50% of 238 DBRF) — breed is associated with severe-bite outcomes in the fatality data.
- **Side A (AVMA):** the breed→bite-risk connection is "weak or absent"; "any dog can bite, regardless of its breed"; ownership/management variables dominate.

The disagreement is **not** over whether to enact BSL — Sacks et al. and the AVMA both caution against breed bans (Sacks on enforcement/identification grounds; AVMA on effectiveness grounds). The live contradiction the pair surfaces is whether the fatality breed-disproportion means breed *predicts* risk, or is an artifact (breed-misidentification, popularity/exposure confounding, reporting bias). **This is genuinely unresolved** (see Caveats); the note does not imply settled causation in either direction.

## Why this fits the corpus

- **Cat 3 (contradiction).** Declares the reciprocal `contradicts` edge to side A's `pub_avma_bsl_not_answer`; both notes carry `contradiction_pair_id: breed_predicts_bite_risk`. Side A holds the primary A→B edge; this note holds the reciprocal B→A edge so the pair is bound from both directions.
- **Cross-domain.** `behavioral_research` (epidemiological fatality study) contradicting `municipal_policy` (AVMA BSL position) — the manifest's intended crossing.
- **Reuse.** `concept_pit_bull`, `breed_rottweiler`, `org_cdc`, `org_avma`, and `concept_bsl` are reused from existing notes / side A; only `pub_sacks_javma_2000`, `person_jeffrey_sacks`, and `concept_dbrf` are introduced here.

## Provenance and limitations

The JAVMA full text is paywalled — a direct fetch of `avmajournals.avma.org/view/journals/javma/217/6/javma.2000.217.836.xml` returned **HTTP 403**. The **PubMed abstract record (PMID 10997153)** is fetchable and is therefore the `source_url` / canonical-of-record for this note; the three quoted abstract passages above were confirmed verbatim against it on 2026-06-17.

**Tertiary pointer (labeled, not used as primary):** the manifest's original side-B URL was the Wikipedia article *Fatal dog attacks in the United States*, which summarizes this study as "pit bull type dogs were most likely to be involved in fatal attacks, accounting for 28%" (verified verbatim on the live Wikipedia page, 2026-06-17). That is a **tertiary** source. Per the manifest's ingestion instruction, this note substitutes the Sacks et al. *JAVMA primary* (via its PubMed abstract) for the breed-risk pole and retains the Wikipedia summary only as a labeled cross-reference below.

The "28%" pit-bull-specific figure appears in the tertiary Wikipedia summary, not in the verbatim abstract passages confirmed here; the abstract states the combined pit-bull-and-Rottweiler ">half" figure across 238 DBRF. The narrower 28% pit-bull-only share is reported in the full paper's tables (not fetchable here) and should be re-verified against the full text before being quoted as primary.

## Sources

- PubMed abstract record (canonical URL of record for this note): https://pubmed.ncbi.nlm.nih.gov/10997153/
- Primary publication (paywalled full text): Sacks JJ, Sinclair L, Gilchrist J, Golab GC, Lockwood R. "Breeds of dogs involved in fatal human attacks in the United States between 1979 and 1998." *J Am Vet Med Assoc* 2000 Sep 15;217(6):836–840. https://avmajournals.avma.org/view/journals/javma/217/6/javma.2000.217.836.xml (HTTP 403 from this client)
- Tertiary cross-reference (labeled `other`, NOT primary): Wikipedia, "Fatal dog attacks in the United States" — https://en.wikipedia.org/wiki/Fatal_dog_attacks_in_the_United_States
- Opposing pole (side A): AVMA — Why breed-specific legislation is not the answer. See `municipal_policy/avma-bsl-not-the-answer.md`.
