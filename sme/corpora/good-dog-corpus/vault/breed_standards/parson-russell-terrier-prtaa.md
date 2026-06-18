---
note_id: breed_parson_russell_prtaa
source_url: https://prtaa.org/club-history
source_title: "Parson Russell Terrier Association of America — Club History"
source_date: "2003-04-01"
source_publisher: "Parson Russell Terrier Association of America"
license: other
license_note: "PRTAA (AKC parent-club) website content. Not a U.S. government work. Short factual excerpts (the name-change statement and effective date) are quoted under fair use for non-commercial research and evaluation; the full page is not reproduced. source_date reflects the name-change effective date documented on the page (April 1, 2003); the page itself is undated club history."
accessed_on: "2026-06-17"
domain: breed_standards
alias_pair_id: jack_parson_russell_identity
contradiction_pair_id: jack_parson_russell_identity

# Cat 3 CONTRADICTION pair — SIDE A (higher-trust: AKC parent-club / registry view).
# This is the PRTAA/AKC position: the Jack Russell Terrier was RENAMED to Parson
# Russell Terrier (effective April 1, 2003) and the two names refer to the same
# AKC-recognized breed -> alias_of + supersedes. The contradicts edge points at
# SIDE B's primary publication (pub_jrtca_breed_position, declared in
# jack-russell-terrier-jrtca.md) so it resolves cross-note.
#
# Reuses org_akc, breed_akc_terrier_group, and pub_akc_group_taxonomy from the
# existing breed_standards notes (do NOT redeclare a parallel AKC org/group).
entities:
  - id: org_prtaa
    type: organization
    canonical: "Parson Russell Terrier Association of America"
    aliases: ["PRTAA"]
    is_regulatory: false
    notes: "AKC parent club for the Parson Russell Terrier. Holds AKC-delegated breed-club authority, not government regulatory authority (is_regulatory: false)."
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "U.S. national breed registry, founded 1884. Already declared in akc-german-shepherd-dog.md / akc-seven-group-taxonomy.md; reused here. The body that recognized the breed and approved the 2003 name change."
  - id: org_jrtca
    type: organization
    canonical: "Jack Russell Terrier Club of America"
    aliases: ["JRTCA"]
    is_regulatory: false
    notes: "Declared in full on SIDE B (jack-russell-terrier-jrtca.md). Mentioned here only as the opposing parent society. Reused id so the two notes share one JRTCA node."
  - id: person_rev_jack_russell
    type: person
    canonical: "Rev. John Russell"
    aliases: ["Jack Russell", "Rev. Jack Russell", "the Parson"]
    notes: "19th-century English parson and breeder after whom both the Jack Russell and Parson Russell terriers are named. The 'Parson' name and the eponym are the historical root both sides invoke."
  - id: breed_parson_russell_terrier
    type: breed
    canonical: "Parson Russell Terrier"
    aliases: ["PRT"]
    notes: "The AKC-recognized breed name adopted April 1, 2003. SIDE A treats this as the SAME breed as the Jack Russell Terrier under a new name (alias_of); SIDE B (JRTCA) rejects that equivalence."
  - id: breed_jack_russell_terrier
    type: breed
    canonical: "Jack Russell Terrier"
    aliases: ["JRT"]
    notes: "Declared in full on SIDE B. Reused id. Under SIDE A this is the prior name of the breed now called Parson Russell Terrier; under SIDE B it is a distinct working strain. The alias_of edge below encodes SIDE A's claim ONLY."
  - id: pub_prtaa_club_history
    type: publication
    canonical: "PRTAA Club History (Parson Russell Terrier Association of America)"
    notes: "SIDE A's primary publication. Documents the April 1, 2003 name change from Jack Russell Terrier to Parson Russell Terrier."

edges:
  - from: pub_prtaa_club_history
    type: authored_by
    to: org_prtaa
    evidence: "Page is the Club History published on prtaa.org, the PRTAA's own site; PRTAA is the named author/publisher of the club-history narrative."
  - from: pub_prtaa_club_history
    type: mentions
    to: breed_parson_russell_terrier
    evidence: "Club History states 'On April 1, 2003 the name of the breed was changed from Jack Russell Terrier to Parson Russell Terrier.' — the Parson Russell Terrier is the resulting recognized breed."
  - from: pub_prtaa_club_history
    type: mentions
    to: breed_jack_russell_terrier
    evidence: "Same sentence names the prior breed name, Jack Russell Terrier, as the name that was changed."
  - from: pub_prtaa_club_history
    type: mentions
    to: org_akc
    evidence: "Club History describes the breed's AKC recognition and its placement in the AKC Terrier Group; the AKC is the body that approved the 2003 name change."
  - from: pub_prtaa_club_history
    type: mentions
    to: person_rev_jack_russell
    evidence: "The breed and the 'Parson' name derive from Rev. John (Jack) Russell; the club history narrates the eponym."

  # --- SIDE A's core claim: the two names are the SAME breed -----------
  - from: breed_jack_russell_terrier
    type: alias_of
    to: breed_parson_russell_terrier
    evidence: "PRTAA Club History: 'the name of the breed was changed from Jack Russell Terrier to Parson Russell Terrier' (effective April 1, 2003) — SIDE A asserts the two surface forms name ONE AKC-recognized breed (same entity_type: breed). This edge encodes the PRTAA/AKC position; SIDE B's JRTCA note explicitly rejects this equivalence via its contradicts edge. Registry-proposed alias, human-grounded: the equivalence is contested, not settled."
    needs_grounding: true

  # --- SIDE A's supersession: new name replaces old -------------------
  - from: pub_prtaa_club_history
    type: supersedes
    to: pub_jrtca_breed_position
    evidence: "Per the PRTAA/AKC view, the April 1, 2003 rename of Jack Russell Terrier to Parson Russell Terrier replaced the older breed-name designation that the JRTCA continues to maintain; SIDE A frames the AKC recognized name as the current registry designation that supersedes the prior 'Jack Russell Terrier' breed-name standard. Disputed supersession — the JRTCA does not accept that its working-strain designation was superseded."
    needs_grounding: true

  # --- THE CONTRADICTION: A's claim vs B's primary publication --------
  - from: pub_prtaa_club_history
    type: contradicts
    to: pub_jrtca_breed_position
    evidence: "Point of disagreement: whether the Jack Russell and Parson Russell terriers are the SAME breed. SIDE A (PRTAA/AKC) states 'the name of the breed was changed from Jack Russell Terrier to Parson Russell Terrier' — one breed, renamed (alias_of). SIDE B (JRTCA) states the Parson Russell Terrier is a variant 'made into separate breeds by the AKC' and that the clubs remain 'adamantly opposed to all-breed/kennel club registration of the Jack Russell Terrier' — i.e. the Jack Russell is a distinct working strain, NOT an alias of the Parson Russell. The two publications make incompatible claims about the same breed identity. Which side is authoritative is a human ruling at ingestion; both are recorded."
    needs_grounding: true

tags: [breed_standards, parson_russell_terrier, jack_russell_terrier, prtaa, akc, jrtca, contradiction_pair, alias_dispute, name_change, side_a]
---

# Parson Russell Terrier — PRTAA / AKC view (the breed was renamed in 2003)

## Summary

The **Parson Russell Terrier Association of America (PRTAA)**, the AKC parent
club for the breed, documents on its Club History page that **"On April 1, 2003
the name of the breed was changed from Jack Russell Terrier to Parson Russell
Terrier."** Under the PRTAA/AKC view, the Jack Russell Terrier and the Parson
Russell Terrier are the **same AKC-recognized breed** — the second name simply
replaced the first. This is **SIDE A** of the Cat 3 contradiction pair
`jack_parson_russell_identity`.

## What the source reported

Per the PRTAA Club History page (verbatim):

> "On April 1, 2003 the name of the breed was changed from Jack Russell Terrier
> to Parson Russell Terrier."

The breed is registered by the **American Kennel Club** and placed in the AKC
**Terrier Group**. The PRTAA is the AKC-delegated parent club; its history
narrates the breed's path to AKC recognition and the subsequent rename.

## Why this fits the corpus (Cat 3 contradiction — SIDE A)

This note is the **higher-trust / registry pole** of a contradiction over breed
identity. The disagreement is structural and lives in the `alias_of` relation:

- **SIDE A (this note):** Jack Russell Terrier `alias_of` Parson Russell
  Terrier — one breed, two names, the AKC-recognized name superseding the older
  one in 2003.
- **SIDE B (`jack-russell-terrier-jrtca.md`):** the Jack Russell Terrier Club of
  America rejects that equivalence, holding that the AKC carved variants out of
  the Jack Russell and that the real Jack Russell remains a distinct,
  unregistered working strain.

The `contradicts` edge from `pub_prtaa_club_history` to `pub_jrtca_breed_position`
binds the pair. **Which side is "correct" is a human ruling at ingestion** — this
note records SIDE A faithfully and does not adjudicate. The `alias_of` and
`supersedes` edges encode the PRTAA/AKC claim *as a claim*, flagged
`needs_grounding: true` because the equivalence is contested.

## Provenance and limitations

The name-change sentence was confirmed verbatim against the live PRTAA Club
History page (`https://prtaa.org/club-history`) on 2026-06-17 via direct fetch;
the substring `the name of the breed was changed from Jack Russell Terrier to
Parson Russell Terrier` matches the page text. The page is undated club-history
boilerplate; `source_date` is set to the documented effective date (April 1,
2003) rather than a publication date. The PRTAA page does not itself mention the
JRTCA — the opposing position is sourced separately in SIDE B.

## Sources

- PRTAA Club History (canonical URL of record): https://prtaa.org/club-history
- AKC breed page — Parson Russell Terrier (Terrier Group): https://www.akc.org/dog-breeds/parson-russell-terrier/
