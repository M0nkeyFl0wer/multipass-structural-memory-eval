---
note_id: beh_mech_1970_alpha_claim
source_url: https://davemech.org/wolf-news-and-information/
source_title: "Dave Mech — Wolf News and Information (statement on his 1970 book The Wolf)"
source_date: "1970"
source_publisher: "davemech.org (the author's own site, documenting the outdated 1970 alpha-wolf claim from his book The Wolf: Ecology and Behavior of an Endangered Species)"
source_tier: other
license: all_rights_reserved
license_note: "Author's personal website (davemech.org). Tier 'other': this is the author's own statement documenting his outdated 1970 popular claim, not a peer-reviewed primary. Quoted for the contradiction pair only."
accessed_on: "2026-06-17"
domain: behavioral_research

# Ontology-aligned entity declarations. person/concept ids are REUSED from
# the existing good-dog-corpus Mech notes. This note INTRODUCES the 1970 book
# publication (pub_mech_1970_the_wolf) — the superseded pole — and the
# davemech.org statement page that documents it (pub_mech_davemech_wolf_news).
entities:
  - id: person_l_david_mech
    type: person
    canonical: "L. David Mech"
    aliases: ["David Mech", "L David Mech", "Dave Mech"]
  - id: pub_mech_1970_the_wolf
    type: publication
    canonical: "The Wolf: The Ecology and Behavior of an Endangered Species (Mech 1970)"
    aliases: ["The Wolf", "Mech 1970"]
  - id: pub_mech_davemech_wolf_news
    type: publication
    canonical: "Wolf News and Information (davemech.org statement on the outdated alpha-wolf concept)"
    aliases: ["davemech.org Wolf News"]
  - id: concept_alpha_wolf
    type: concept
    canonical: "Alpha wolf concept"
    aliases: ["alpha pair", "alpha status", "alpha wolf"]
  - id: concept_dominance_theory
    type: concept
    canonical: "Dominance theory (canine behavior)"

# Edges. SIDE B is the superseded pole; the contradicts/supersedes edges that
# bind the pair are declared on SIDE A (mech-1999-alpha-status-correction.md),
# pointing INTO pub_mech_1970_the_wolf. Here we wire authorship, the subject
# link to the alpha-wolf concept, and the documentation link from the
# davemech.org statement to the 1970 book.
edges:
  - from: pub_mech_1970_the_wolf
    type: authored_by
    to: person_l_david_mech
    evidence: "The 1970 book 'The Wolf: The Ecology and Behavior of an Endangered Species' was authored by L. David Mech (written 1968, published 1970, in print until 2022 per the davemech.org statement). Same author as the 1999 correction on SIDE A."
  - from: pub_mech_davemech_wolf_news
    type: authored_by
    to: person_l_david_mech
    evidence: "Statement hosted on davemech.org, the author's own website, in his voice ('Although most of the book's info is still accurate, much is outdated')."
  - from: pub_mech_1970_the_wolf
    type: subject_of
    to: concept_alpha_wolf
    evidence: "The 1970 book is the work that popularized the alpha-wolf concept; per Mech's own davemech.org statement, 'One of the outdated pieces of information is the concept of the alpha wolf.'"
  - from: pub_mech_1970_the_wolf
    type: subject_of
    to: concept_dominance_theory
    evidence: "The book framed wolf-pack structure as a strength-based dominance hierarchy with an alpha pair at the top — the dominance-theory framing later applied (and contested) in dog training."
  - from: pub_mech_davemech_wolf_news
    type: mentions
    to: pub_mech_1970_the_wolf
    evidence: "The davemech.org statement is explicitly about the 1970 book The Wolf, identifying which of its claims are outdated."
  - from: pub_mech_davemech_wolf_news
    type: mentions
    to: concept_alpha_wolf
    evidence: "The statement names the alpha-wolf concept directly: 'One of the outdated pieces of information is the concept of the alpha wolf.'"

tags: [behavioral_research, dominance_theory, wolves, mech, alpha_wolf, contradiction_pair, pre_correction, superseded, tertiary_author_statement]
contradiction_pair_id: alpha_wolf_dominance
---

# Mech 1970 — *The Wolf* and the alpha-wolf claim (SIDE B: the superseded popular claim)

## Summary

L. David Mech's 1970 book ***The Wolf: The Ecology and Behavior of an Endangered
Species*** popularized the **alpha-wolf** framing: that a wolf pack is a
strength-based dominance hierarchy topped by an "alpha" pair that won its position
through contest. This framing was carried into decades of dog-training advice.
Mech himself later disavowed it. This note captures **SIDE B** of the
`alpha_wolf_dominance` Cat 3 pair — the superseded popular claim — as documented
by **Mech's own website**, `davemech.org` (tier `other`, an author self-statement,
not a peer-reviewed primary).

The opposing, higher-trust pole is **SIDE A**
(`mech-1999-alpha-status-correction.md`), Mech's 1999 peer-reviewed paper, which
both **contradicts** and **supersedes** this 1970 claim. Those two binding edges
are declared on Side A and point into `pub_mech_1970_the_wolf` declared here.

## What the source reported (verified verbatim)

From `davemech.org`, the `expected_source` substring for this side:

> "One of the outdated pieces of information is the concept of the alpha wolf."

The statement also notes the book was "written in 1968, published in 1970" and
remained "in print until 2022," and that "Although most of the book's info is
still accurate, much is outdated." On why the alpha concept is now considered
outdated, the page explains that "alpha" implies "competing with others and
becoming top dog by winning a contest or battle," whereas "most wolves who lead
packs achieved their position simply by mating and producing pups"; today
scientists prefer "breeding male," "breeding female," or "adult male/female."

## Why this fits the corpus

- **Cat 3 (contradiction).** This is the superseded pole of a same-author
  self-contradiction. The 1970 book asserts a contest-won dominance hierarchy;
  Side A (1999) asserts the incompatible family-with-breeding-parents model. The
  `contradicts` edge `pub_mech_1999_alpha_status → pub_mech_1970_the_wolf` lives on
  Side A.
- **Cat 6 (temporal).** The `supersedes` edge (also on Side A) makes the 1970 book
  the older, replaced publication in the chain.

## Honest scope note

This side is documented by the author's own website, **tier `other`** (a
self-statement / tertiary-style source), not a peer-reviewed primary. The 1970
book itself is the original publication; `davemech.org` is the accessible
record that confirms, in the author's voice, what the book claimed and that he
now regards the alpha-wolf concept as outdated. Which side is "correct" is a human
ruling at ingestion and is deliberately not adjudicated here — though Mech's own
later retraction is captured faithfully so the contradiction is legible.

## Entity reuse

`person_l_david_mech`, `concept_alpha_wolf`, and `concept_dominance_theory` are
**reused** ids from the existing good-dog-corpus notes; this note does not create
parallel nodes for them. `pub_mech_1970_the_wolf` and
`pub_mech_davemech_wolf_news` are introduced here. Side A references
`pub_mech_1970_the_wolf` for the cross-note contradicts/supersedes binding.

## Provenance and verification

The `davemech.org` page was fetched directly in this authoring session and the
`expected_source` substring "One of the outdated pieces of information is the
concept of the alpha wolf" was confirmed verbatim, along with the surrounding
context about the 1970 book and the breeding-pair reframing.

## Sources

- Dave Mech — Wolf News and Information (source of record for this note, tier `other`): https://davemech.org/wolf-news-and-information/
- Original publication: Mech, L. D. 1970. *The Wolf: The Ecology and Behavior of an Endangered Species.* Natural History Press / University of Minnesota Press.
- Opposing pole (SIDE A): Mech, L. D. 1999. "Alpha status, dominance, and division of labor in wolf packs." *Canadian Journal of Zoology* 77(8): 1196-1203. DOI 10.1139/z99-099.
