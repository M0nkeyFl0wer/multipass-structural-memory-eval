"""Phase 2 web-standard baseline for Cat 8 8f external fit.

Exercises the schema.org / FOAF / SKOS / Dublin Core reference table
against the REAL good-dog ontology, confirming the three fit outcomes
land on the types the draft predicts:
  - person / organization / event  -> mappable
  - member_of                      -> under-specified (two standard terms)
  - breed / regulates              -> idiosyncratic (unaligned)
"""

from __future__ import annotations

from pathlib import Path

from sme.categories.external_fit import load_standard_mappings, score_external_fit
from sme.categories.ontology_coherence import ImpliedOntology

ROOT = Path(__file__).resolve().parent.parent
WEBSTD = ROOT / "sme/claims/standard_ontologies_webstd.yaml"
GOOD_DOG = ROOT / "sme/corpora/good-dog-corpus/ontology.yaml"


def _report():
    mappings = load_standard_mappings(WEBSTD)
    implied = ImpliedOntology.load(GOOD_DOG)  # dict-shape, normalized by loader
    return score_external_fit(implied, [], [], mappings=mappings)


def test_reference_set_reported():
    rep = _report()
    assert rep["reference_set"] == ["schema", "foaf", "skos", "dcterms"]


def test_core_entity_types_mappable():
    rep = _report()
    by_term = {}
    for a in rep["alignments"]:
        by_term.setdefault(a["corpus_term"], []).append(a)
    for t in ("person", "organization", "event"):
        assert t in by_term, f"{t} should align"
        assert all(a["outcome"] == "mappable" for a in by_term[t])


def test_member_of_under_specified():
    rep = _report()
    member = [a for a in rep["alignments"] if a["corpus_term"] == "member_of"]
    assert len(member) == 2, "member_of maps to two standard terms"
    assert {a["standard_term"] for a in member} == {"skos:broader", "schema:memberOf"}
    assert all(a["outcome"] == "under-specified" for a in member)
    # an overloaded edge is NOT counted as cleanly mappable
    mappable_terms = {
        a["corpus_term"] for a in rep["alignments"] if a["outcome"] == "mappable"
    }
    assert "member_of" not in mappable_terms


def test_publication_under_specified():
    rep = _report()
    pub = [a for a in rep["alignments"] if a["corpus_term"] == "publication"]
    assert len(pub) == 2
    assert all(a["outcome"] == "under-specified" for a in pub)


def test_breed_and_regulates_idiosyncratic():
    rep = _report()
    assert "breed" in rep["unaligned_types"]
    assert "regulates" in rep["unaligned_types"]


def test_affiliation_constraint_fires_on_bad_target():
    """affiliated_with whose target is not an organization -> violation."""
    from sme.adapters.base import Edge, Entity

    mappings = load_standard_mappings(WEBSTD)
    implied = ImpliedOntology.load(GOOD_DOG)
    entities = [
        Entity(id="p1", name="Vet", entity_type="person"),
        Entity(id="p2", name="Other vet", entity_type="person"),
        Entity(id="o1", name="AKC", entity_type="organization"),
    ]
    edges = [
        Edge(source_id="p1", target_id="o1", edge_type="affiliated_with"),  # ok
        Edge(source_id="p1", target_id="p2", edge_type="affiliated_with"),  # bad
    ]
    rep = score_external_fit(implied, entities, edges, mappings=mappings)
    results = rep["audit"]["sh:result"]
    aff = [r for r in results if r["sh:resultPath"] == "affiliated_with"]
    assert aff, "affiliation constraint should produce a finding"
    assert aff[0]["sh:resultSeverity"] == "sh:Violation"  # confidence 0.88 >= 0.85
    assert "schema:affiliation" in aff[0]["provenance"]
