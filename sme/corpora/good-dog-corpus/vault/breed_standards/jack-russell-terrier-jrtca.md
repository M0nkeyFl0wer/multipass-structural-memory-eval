---
note_id: breed_jack_russell_jrtca
source_url: https://www.therealjackrussell.com/jrtca/diduknow.php
source_title: "JRTCA — Jack Russell Terrier Misconceptions (the JRTCA position on AKC recognition)"
source_date: "2026-06-17"
source_publisher: "Jack Russell Terrier Club of America"
license: other
license_note: "JRTCA (Jack Russell Terrier Club of America) website content. Not a U.S. government work. Short factual excerpts (the opposition statement and the 'separate breeds' statement) are quoted under fair use for non-commercial research and evaluation; the full page is not reproduced. source_date reflects the access date — the page is undated club content."
accessed_on: "2026-06-17"
domain: breed_standards
alias_pair_id: jack_parson_russell_identity
contradiction_pair_id: jack_parson_russell_identity

# Cat 3 CONTRADICTION pair — SIDE B (the dissent: JRTCA working-strain view).
# The JRTCA rejects the AKC/PRTAA claim that Jack Russell == Parson Russell.
# It holds the Parson Russell (and Russell Terrier) are variants the AKC carved
# out, and that the real Jack Russell is a distinct, deliberately-unregistered
# working strain. The contradicts edge is wired on SIDE A against this note's
# pub_jrtca_breed_position id; SIDE B does NOT assert alias_of (that is exactly
# the relation it denies).
#
# NOTE ON SOURCE TIER: the manifest's D2b was a TERTIARY Wikipedia pointer
# (en.wikipedia.org/wiki/Jack_Russell_Terrier). A substring-stable JRTCA PRIMARY
# was located during ingestion and substituted (this page). The Wikipedia
# tertiary is retained below as a cross-reference only. source_tier is therefore
# the JRTCA primary, not tertiary — see warnings.
#
# Reuses org_akc, breed_jack_russell_terrier, breed_parson_russell_terrier,
# org_jrtca, and person_rev_jack_russell ids shared with SIDE A.
entities:
  - id: org_jrtca
    type: organization
    canonical: "Jack Russell Terrier Club of America"
    aliases: ["JRTCA"]
    is_regulatory: false
    notes: "National breed club and registry for the Jack Russell Terrier as a working strain. Deliberately independent of the AKC/all-breed registry system. Holds private-club registry authority, not government regulatory authority (is_regulatory: false). Shared node with SIDE A."
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "Reused id (declared in akc-german-shepherd-dog.md / akc-seven-group-taxonomy.md). The body the JRTCA opposes recognition by; the body that, per the JRTCA, 'made [the Russell variants] into separate breeds'."
  - id: org_prtaa
    type: organization
    canonical: "Parson Russell Terrier Association of America"
    aliases: ["PRTAA"]
    is_regulatory: false
    notes: "Declared in full on SIDE A. Reused id. The AKC parent club whose name-change/recognition position the JRTCA rejects."
  - id: person_rev_jack_russell
    type: person
    canonical: "Rev. John Russell"
    aliases: ["Jack Russell", "Rev. Jack Russell", "the Parson"]
    notes: "Shared id with SIDE A. The eponymous 19th-century parson/breeder both sides invoke."
  - id: breed_jack_russell_terrier
    type: breed
    canonical: "Jack Russell Terrier"
    aliases: ["JRT", "the real Jack Russell Terrier"]
    notes: "Under SIDE B this is a DISTINCT working strain (10-15 inches, varied type), NOT an alias of the Parson Russell Terrier. The JRTCA maintains it deliberately outside all-breed-club registration. Shared id with SIDE A, where the alias_of claim is encoded — this note's contradicts edge denies that claim."
  - id: breed_parson_russell_terrier
    type: breed
    canonical: "Parson Russell Terrier"
    aliases: ["PRT"]
    notes: "Shared id with SIDE A. Under SIDE B this is a SEPARATE breed the AKC made out of one variant of the Jack Russell — explicitly not the same entity as the Jack Russell Terrier."
  - id: breed_russell_terrier
    type: breed
    canonical: "Russell Terrier"
    notes: "The shorter (10-12 inch) variant the AKC separately recognized. Named by the JRTCA as the second of the two variants the AKC 'made into separate breeds'. Reinforces the JRTCA's distinctness claim."
  - id: pub_jrtca_breed_position
    type: publication
    canonical: "JRTCA position on Jack Russell Terrier breed identity and kennel-club recognition"
    notes: "SIDE B's primary publication. The TARGET of SIDE A's contradicts/supersedes edges (stable id, must match the from-side reference in parson-russell-terrier-prtaa.md). States the JRTCA is 'adamantly opposed to all-breed/kennel club registration' and that the Parson Russell and Russell terriers are variants 'made into separate breeds by the AKC'."

edges:
  - from: pub_jrtca_breed_position
    type: authored_by
    to: org_jrtca
    evidence: "Page is published on therealjackrussell.com, the JRTCA's own site, stating the club's position; the JRTCA is the named author/publisher."
  - from: pub_jrtca_breed_position
    type: mentions
    to: breed_jack_russell_terrier
    evidence: "Page asserts the JRTCA considers the Jack Russell Terrier to be the real Jack Russell Terrier and that the clubs remain 'adamantly opposed to all-breed/kennel club registration of the Jack Russell Terrier'."
  - from: pub_jrtca_breed_position
    type: mentions
    to: breed_parson_russell_terrier
    evidence: "Page: 'The Russell Terrier ... and the Parson Russell Terrier ... are both variants of the Jack Russell Terrier ... made into separate breeds by the AKC.'"
  - from: pub_jrtca_breed_position
    type: mentions
    to: breed_russell_terrier
    evidence: "Same sentence names the Russell Terrier (10\" to 12\") as the second AKC-separated variant."
  - from: pub_jrtca_breed_position
    type: mentions
    to: org_akc
    evidence: "Page names the AKC (American Kennel Club) as the body that made the variants into separate breeds and whose registration the JRTCA opposes."

  # --- SIDE B's core claim: NOT the same breed ------------------------
  # No alias_of edge is written from this note — denying that equivalence is
  # exactly SIDE B's position. The contradicts edge that carries the dissent is
  # wired on SIDE A (pub_prtaa_club_history -> pub_jrtca_breed_position), so the
  # pair is bound once and resolves cross-note. Here we record the standalone
  # JRTCA claim via mentions; the opposed-predicate pairing lives on the
  # contradicts edge in parson-russell-terrier-prtaa.md.

tags: [breed_standards, jack_russell_terrier, parson_russell_terrier, russell_terrier, jrtca, akc, prtaa, contradiction_pair, alias_dispute, working_strain, side_b]
---

# Jack Russell Terrier — JRTCA view (a distinct working strain, NOT the Parson Russell)

## Summary

The **Jack Russell Terrier Club of America (JRTCA)** rejects the AKC/PRTAA claim
that the Jack Russell Terrier and the Parson Russell Terrier are the same breed
under a new name. The JRTCA holds that the **Parson Russell Terrier and the
Russell Terrier are variants "made into separate breeds by the AKC,"** while the
real Jack Russell Terrier remains a **distinct working strain** the club
deliberately keeps outside all-breed-club registration. This is **SIDE B** — the
dissent — of the Cat 3 contradiction pair `jack_parson_russell_identity`.

## What the source reported

Per the JRTCA page (verbatim):

> "Both clubs have always been, and remain, adamantly opposed to all-breed/kennel
> club registration of the Jack Russell Terrier"

> "The Russell Terrier (10" to 12" in height) and the Parson Russell Terrier
> (12" to 14") are both variants of the Jack Russell Terrier (10" to 15") made
> into separate breeds by the AKC (American Kennel Club)."

The JRTCA defines the Jack Russell as any height from 10 to 15 inches with varied
coat, markings, and type — a working definition, not a single conformation
standard — which is the basis for treating the AKC's narrower Parson Russell as a
separate breed rather than the same one renamed.

## Why this fits the corpus (Cat 3 contradiction — SIDE B)

This note is the **dissent pole** of a contradiction over breed identity. The
disagreement lives in the `alias_of` relation:

- **SIDE A (`parson-russell-terrier-prtaa.md`):** Jack Russell `alias_of` Parson
  Russell — one AKC breed, renamed in 2003.
- **SIDE B (this note):** the two are NOT the same breed; the AKC "made [them]
  into separate breeds," and the JRTCA opposes the registration entirely. No
  `alias_of` edge is asserted here — denying that equivalence is the whole point.

The `contradicts` edge that binds the pair is written on SIDE A
(`pub_prtaa_club_history` → `pub_jrtca_breed_position`), targeting this note's
publication id. **Which side is "correct" is a human ruling at ingestion** — this
note records SIDE B faithfully and does not adjudicate.

## Provenance and limitations

The manifest (D2b) supplied a **tertiary** pointer — the Wikipedia "Jack Russell
Terrier" article — with the expected substring `Recognition by kennel clubs for
the Jack Russell breed has been opposed by the breed's parent societies`. During
ingestion a **substring-stable JRTCA primary** was located and substituted as the
source of record: `https://www.therealjackrussell.com/jrtca/diduknow.php`. Both
quoted substrings above (`adamantly opposed to all-breed/kennel club
registration` and `made into separate breeds by the AKC`) were confirmed verbatim
against that live primary on 2026-06-17 via direct fetch. The Wikipedia tertiary
substring was also confirmed verbatim and is retained below as a cross-reference
only. `source_tier` for this note is therefore the JRTCA **primary** (a national
breed club's own statement of position), not tertiary.

## Sources

- JRTCA — Jack Russell Terrier Misconceptions (canonical URL of record, PRIMARY):
  https://www.therealjackrussell.com/jrtca/diduknow.php
- JRTCA main page: https://www.therealjackrussell.com/jrtca/jrtca.php
- Cross-reference (TERTIARY, manifest D2b pointer; not the source of record):
  Wikipedia, "Jack Russell Terrier" — substring `Recognition by kennel clubs for
  the Jack Russell breed has been opposed by the breed's parent societies`:
  https://en.wikipedia.org/wiki/Jack_Russell_Terrier
