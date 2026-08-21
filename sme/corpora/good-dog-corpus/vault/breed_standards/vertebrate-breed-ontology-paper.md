---
note_id: breed_vbo_paper
source_url: https://pmc.ncbi.nlm.nih.gov/articles/PMC11177956/
source_title: "The Vertebrate Breed Ontology: Towards Effective Breed Data Standardization"
source_date: "2025-01-24"
source_publisher: "PubMed Central (PMC) / Monarch Initiative"
license: other
license_note: "Open-access manuscript hosted on PubMed Central (PMC11177956), a corresponding arXiv preprint (2406.02623). Reproduced under the article's open-access terms for non-commercial research and evaluation; short excerpts are quoted with attribution per frontmatter. Not a U.S. government work; the hosting platform (PMC) is government-run but the manuscript copyright is held by the authors/Monarch Initiative."
accessed_on: "2026-06-17"
domain: breed_standards

# Ontology-aligned entity declarations introduced by this note.
# Cat 8 anchor: VBO is a real description-logic ontology (the gold-standard
# conformance analogue). Its formal is-a hierarchy is modeled with subclass_of,
# distinct from the registry SKOS-broader grouped_under used for AKC groups.
entities:
  - id: pub_vbo_paper
    type: publication
    canonical: "The Vertebrate Breed Ontology: Towards Effective Breed Data Standardization"
    notes: "Open-access manuscript describing VBO. PMC11177956 / arXiv:2406.02623v2."
  - id: org_monarch_initiative
    type: organization
    canonical: "Monarch Initiative"
    is_regulatory: false
    notes: "Maintainer of the Vertebrate Breed Ontology (VBO)."
  - id: org_omia
    type: organization
    canonical: "Online Mendelian Inheritance in Animals"
    is_regulatory: false
    notes: "OMIA — a curated catalogue of inherited disorders in animals; a primary breed-data source ingested by VBO."
  - id: org_akc
    type: organization
    canonical: "American Kennel Club"
    is_regulatory: false
    notes: "Breed registry authority for the United States. Reused from akc-german-shepherd-dog.md."
  - id: person_kathleen_mullen
    type: person
    canonical: "Kathleen R. Mullen"
    notes: "Lead author, Department of Genetics, University of North Carolina at Chapel Hill."
  - id: breed_vbo_dog_breed
    type: breed
    canonical: "dog breed (VBO grouping term)"
    notes: "High-level VBO grouping term, logically defined via NCBITaxon parentage. Itself a breed-typed grouping node (the ontology treats a breed grouping as a recognized breed)."
  - id: breed_vbo_chihuahua
    type: breed
    canonical: "Chihuahua (Dog)"
    notes: "VBO:0200338. Demonstrates the 'Most common name (Species)' label naming convention."

edges:
  # Authorship and maintenance
  - from: pub_vbo_paper
    type: authored_by
    to: person_kathleen_mullen
    evidence: "Kathleen R. Mullen (Department of Genetics, University of North Carolina at Chapel Hill) is the lead author of the open-access VBO manuscript hosted at PMC11177956."
  - from: person_kathleen_mullen
    type: affiliated_with
    to: org_monarch_initiative
    evidence: "The manuscript describes VBO as developed and maintained by the Monarch Initiative; the authors are part of the Monarch Initiative effort behind the ontology."
    needs_grounding: true
  - from: pub_vbo_paper
    type: subject_of
    to: breed_vbo_dog_breed
    evidence: "The paper is primarily about the Vertebrate Breed Ontology and its grouping terms; 'dog breed' is the worked example of a high-level grouping term it logically defines."

  # The DL is-a hierarchy: the gold-standard subclass_of analogue.
  # 'Chihuahua (Dog)' is a logical subclass of the grouping term 'dog breed'.
  - from: breed_vbo_chihuahua
    type: subclass_of
    to: breed_vbo_dog_breed
    evidence: "VBO is a description-logic ontology classified by a reasoner. 'Chihuahua (Dog)' (VBO:0200338) is a leaf breed term; the high-level grouping term 'dog breed' is logically defined based on NCBITaxon parentage, so every dog breed term is reasoned to be a subclass of 'dog breed'. This is a formal OWL is-a, distinct from a registry's grouped_under group membership."

  # Mentions: the paper names its primary breed-data sources and naming example.
  - from: pub_vbo_paper
    type: mentions
    to: org_omia
    evidence: "The manuscript names OMIA (Online Mendelian Inheritance in Animals) among the breed-data sources VBO standardizes and draws from."
  - from: pub_vbo_paper
    type: mentions
    to: org_akc
    evidence: "The manuscript names the American Kennel Club (AKC), alongside FCI and UKC, as breed registries whose breed names VBO reconciles into standardized terms."
  - from: pub_vbo_paper
    type: mentions
    to: breed_vbo_chihuahua
    evidence: "The paper uses 'Chihuahua (Dog)' (VBO:0200338) as the worked example of its 'Most common name (Species)' label naming convention."

  # Data provenance: VBO (the artifact described by the paper) ingests OMIA
  # and AKC as declared breed sources. source_of is data-provenance ingestion,
  # distinct from scholarly cites.
  - from: org_omia
    type: source_of
    to: pub_vbo_paper
    evidence: "OMIA is a declared breed-data source ingested by VBO; the ontology standardizes breed identifiers and names drawn from OMIA. Modeled as source_of (data-provenance ingestion) rather than cites (scholarly reference)."
    needs_grounding: true
  - from: org_akc
    type: source_of
    to: pub_vbo_paper
    evidence: "The AKC breed registry is listed among VBO's breed-name sources; VBO reconciles AKC breed names (with FCI and UKC) into standardized terms. The ABSENCE of a source_of edge for a registry VBO did NOT ingest is the Cat 5 signal this edge type was added to expose."
    needs_grounding: true

tags: [breed_standards, vbo, ontology, description_logic, monarch_initiative, omia, akc, subclass_of, cat8, conformance]
---

# The Vertebrate Breed Ontology (VBO)

## Summary

The **Vertebrate Breed Ontology (VBO)** is a real, actively maintained description-logic ontology for animal breed data, developed and maintained by the **Monarch Initiative**. The source manuscript, *"The Vertebrate Breed Ontology: Towards Effective Breed Data Standardization"* (lead author **Kathleen R. Mullen**, UNC Chapel Hill), is open-access on PubMed Central (PMC11177956) with a corresponding arXiv preprint (2406.02623v2, version 2 posted 2025-01-24; v1 2024-06-03).

VBO reconciles breed names across major registries and catalogues — the **American Kennel Club (AKC)**, **Fédération Cynologique Internationale (FCI)**, **United Kennel Club (UKC)**, and **OMIA (Online Mendelian Inheritance in Animals)** — into standardized, machine-readable terms. It is built and maintained with the **Ontology Development Kit (ODK)** and **ROBOT**, and its term hierarchy is computed by a **description-logic reasoner**.

## Naming convention and grouping terms

VBO breed term labels follow the convention **'Most common name (Species)'**, e.g.:

> 'Chihuahua (Dog)' (VBO:0200338)

For breeds reported in a specific geographic location the convention extends to **'Most common name, Country (Species)'**, e.g. 'Jersey Giant, Canada (Chicken)' (VBO:0006068).

High-level grouping terms are not hand-curated category labels; they are **logically defined** and reasoner-classified. The manuscript states:

> "To facilitate ontology browsing and use, we created high-level grouping terms, such as 'dog breed', 'cattle breed', etc., that were logically defined based on their NCBITaxon parentage."

Because the grouping terms are logically defined, every leaf breed term (e.g. 'Chihuahua (Dog)') is reasoned to be a formal **subclass of** its grouping term ('dog breed'). This is an OWL/DL `is-a`, modeled here with `subclass_of` — deliberately distinct from the looser registry/SKOS-broader `grouped_under` relation used for marketing groups like the AKC Herding Group.

## Why this is the Cat 8 anchor

VBO is the corpus's **gold-standard conformance analogue**. Most breed_standards notes describe registry standards whose "hierarchy" is a curated list (AKC's seven groups). VBO instead carries a *formal* logical hierarchy maintained by a reasoner, with a strict naming convention and explicit data-provenance from named source registries.

For Cat 8 (ontology coherence), the question is whether a memory system that ingests this note keeps the two relation senses separate: VBO's logical `subclass_of` (Chihuahua is-a dog breed, by DL inference) versus a registry's `grouped_under` (a breed is filed under a kennel-club group). A system that conflates a formal taxonomy with a registry's grouping is the failure this note is designed to surface. The `source_of` edges (OMIA, AKC → VBO) make VBO's declared ingestion provenance explicit; the *absence* of such an edge for a registry VBO did not ingest is a Cat 5 (gap) signal.

## Provenance and limitations

The source page was fetched successfully on 2026-06-17. The grouping-term sentence ("high-level grouping terms, such as 'dog breed', 'cattle breed' …") and the 'Chihuahua (Dog)' / VBO:0200338 naming example were confirmed verbatim against the live PMC page. The manifest classified this source as `peer_reviewed`; the hosted manuscript is in fact an **open-access preprint** (arXiv:2406.02623v2 on PMC), so the tier is recorded here as a manuscript/preprint rather than a journal-reviewed article. The `source_of` and `affiliated_with` edges are flagged `needs_grounding: true` — the specific source-registry ingestion list and author affiliations are paraphrased from the manuscript's described scope rather than quoted verbatim, and a future revision should pin each to an exact passage.

## Sources

- The Vertebrate Breed Ontology — manuscript (canonical URL of record): https://pmc.ncbi.nlm.nih.gov/articles/PMC11177956/
- Corresponding arXiv preprint: https://arxiv.org/abs/2406.02623
- VBO is maintained by the Monarch Initiative (https://monarchinitiative.org).
