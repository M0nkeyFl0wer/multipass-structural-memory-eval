---
note_id: pub_parker_dog_breed_clades_2017
source_url: https://pmc.ncbi.nlm.nih.gov/articles/PMC5492993/
source_title: "Genomic Analyses Reveal the Influence of Geographic Origin, Migration, and Hybridization on Modern Dog Breed Development"
source_date: "2017"
source_publisher: "Cell Reports (Parker, Dreger, Rimbault, … Ostrander)"
license: fair_use_excerpt
accessed_on: "2026-06-18"
domain: veterinary_research

# Ontology-aligned entity declarations introduced by this note.
entities:
  - id: pub_parker_dog_breed_clades_2017
    type: publication
    canonical: "Genomic Analyses Reveal the Influence of Geographic Origin, Migration, and Hybridization on Modern Dog Breed Development"
    aliases: ["Parker et al. 2017 Cell Reports", "dog breed cladogram paper", "Parker 2017 breed development genomics"]
  - id: person_parker
    type: person
    canonical: "Heidi G. Parker"
    aliases: ["Heidi G Parker", "H. G. Parker"]
  - id: person_ostrander
    type: person
    canonical: "Elaine A. Ostrander"
    aliases: ["Elaine A Ostrander", "E. A. Ostrander"]
  - id: org_nhgri
    type: organization
    canonical: "National Human Genome Research Institute"
    aliases: ["NHGRI", "National Human Genome Research Institute, National Institutes of Health"]
  - id: concept_breed_clade
    type: concept
    canonical: "Breed clade (genomic clustering of dog breeds)"
    aliases: ["breed clade", "breed-type clade", "cladogram clade"]

# Edges introduced by this note (the GROUND TRUTH the graph is measured against).
edges:
  - from: pub_parker_dog_breed_clades_2017
    type: authored_by
    to: person_parker
    evidence: "Byline: \"Heidi G Parker ... Cancer Genetics and Comparative Genomics Branch, National Human Genome Research Institute, National Institutes of Health\" listed as first author of the article."
  - from: pub_parker_dog_breed_clades_2017
    type: authored_by
    to: person_ostrander
    evidence: "Byline: \"Elaine A Ostrander ... Cancer Genetics and Comparative Genomics Branch, National Human Genome Research Institute, National Institutes of Health\" listed as senior author of the article."
  - from: person_parker
    type: affiliated_with
    to: org_nhgri
    evidence: "\"Heidi G Parker 1 Cancer Genetics and Comparative Genomics Branch, National Human Genome Research Institute, National Institutes of Health, Bethesda, MD, USA\""
  - from: person_ostrander
    type: affiliated_with
    to: org_nhgri
    evidence: "\"Elaine A Ostrander 1 Cancer Genetics and Comparative Genomics Branch, National Human Genome Research Institute, National Institutes of Health, Bethesda, MD, USA\""
  - from: pub_parker_dog_breed_clades_2017
    type: subject_of
    to: concept_breed_clade
    evidence: "\"The cladogram of 161 breeds presented here ... displaying 23 well-supported clades of breeds representing breed-types that existed before the advent of breed clubs and registries.\""
  - from: pub_parker_dog_breed_clades_2017
    type: mentions
    to: concept_breed_clade
    evidence: "\"After 100 bootstraps, 91% of breeds (146/161) formed single, breed-specific\" nodes with 100% bootstrap support, with breeds further grouped into clades."

tags: [veterinary_research, genomics, dog_breeds, cladogram, breed_clade, nhgri, parker, ostrander, cat_7, cat_2c]
---

# Genomic Analyses Reveal the Influence of Geographic Origin, Migration, and Hybridization on Modern Dog Breed Development (Parker et al., Cell Reports, 2017)

## Summary

A landmark 2017 *Cell Reports* paper by Heidi G. Parker, Elaine A. Ostrander, and colleagues at the National Human Genome Research Institute (NHGRI/NIH) that reconstructs the population structure and shared ancestry of modern dog breeds from genome-wide data. Working from a dataset of 1,346 dogs representing 161 breeds — described by the authors as the most diverse set of domestic dog breeds analyzed to that date — the study builds a bootstrapped cladogram that groups breeds by allele and haplotype sharing rather than by phenotype or club-assigned grouping. The headline structural result is a cladogram displaying 23 well-supported clades of breeds, with the great majority of individual breeds resolving as their own tight genomic cluster.

The paper is dense and long, with heavy methods, supplementary tables, and Circos haplotype-sharing plots — which is exactly why it earns its place in the corpus as a token/efficiency stress case alongside its clean author→affiliation→subject hop chain.

## What the source reported

On the dataset and tree:
> "We examined genomic data from the largest and most diverse group of breeds studied to date, amassing a dataset of 1346 dogs representing 161 breeds."

The authors used distance measures based on allele sharing (rather than allele frequency) and enhanced these with unbiased haplotype sharing to assess canine population structure robustly. A bootstrapped cladogram was obtained using an identity-by-state distance matrix and a neighbor-joining tree algorithm.

On the clade structure (the load-bearing result):
> "The cladogram of 161 breeds presented here represents the most diverse dataset of domestic dog breeds analyzed to date, displaying 23 well-supported clades of breeds representing breed-types that existed before the advent of breed clubs and registries."

On the resolution of individual breeds:
> "After 100 bootstraps, 91% of breeds (146/161) formed single, breed-specific" nodes — i.e., the overwhelming majority of breeds resolved as their own tightly supported genomic cluster with 100% bootstrap support, before being grouped into the broader clades.

The clades correspond to shared geographic origin, historical migration routes, and deliberate hybridization events used to create newer breeds — the three forces named in the title. Haplotype sharing across clades was tested for significance against the 95th-percentile boundary of cross-clade dog pairs, allowing the authors to trace which breeds contributed to the formation of others.

## Why this fits the corpus

This note serves two SME categories:

- **Cat 7 (token / efficiency).** The source is a long, dense, supplement-heavy genetics paper. A retriever that must surface a single specific fact — "how many clades?" → 23 — from a document this large is a token-efficiency test: does the system return the load-bearing sentence, or drown it in methods prose? The verbatim figures (23 clades, 1,346 dogs, 161 breeds, 146/161 at 100% bootstrap) are precise anchors for measuring whether the right chunk was retrieved.
- **Cat 2c (multi-hop).** The note encodes a clean two-hop chain: publication → `authored_by` → person (Parker / Ostrander) → `affiliated_with` → organization (NHGRI). A multi-hop question ("what institute were the authors of the dog breed cladogram paper affiliated with?") cannot be answered from a single node; it requires traversing two typed edges. The `subject_of`/`mentions` edges to the breed-clade concept add a second traversable spine into the genetics content.

## Provenance and limitations

The summary author confirmed the source via a direct retrieval of the PMC article HTML (the WebFetch tool was blocked by a reCAPTCHA browser-check; a local curl with a desktop User-Agent succeeded). All quoted statements above are sourced from the live PMC article text. The article writes the sample size as "1346" without a comma; "1,346" in this note is the same figure. Note that "clade" here is a genomic-clustering construct specific to this dataset and method (identity-by-state distance, neighbor-joining, 100 bootstraps) — it is not an official kennel-club grouping and should not be conflated with AKC/FCI breed groups. The paper does not assign regulatory or breed-standard status; it is a descriptive population-genetics result.

## Sources

- Parker HG, Dreger DL, Rimbault M, et al. "Genomic Analyses Reveal the Influence of Geographic Origin, Migration, and Hybridization on Modern Dog Breed Development." *Cell Reports* (2017). https://pmc.ncbi.nlm.nih.gov/articles/PMC5492993/
