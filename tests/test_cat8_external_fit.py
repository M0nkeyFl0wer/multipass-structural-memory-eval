"""Tests for Cat 8 sub-check 8f: external-standard ontology fit + audit.

Covers the four cases the draft calls out: a clean mappable alignment,
an under-specified (one corpus term -> several standard terms) case, an
idiosyncratic/unaligned case, and confidence-gating (a low-confidence
mapping's failure must be informational, not a violation).
"""

from __future__ import annotations

from sme.adapters.base import Edge, Entity
from sme.categories.external_fit import (
    load_standard_mappings,
    score_external_fit,
)
from sme.categories.ontology_coherence import ImpliedOntology


# A self-contained mapping table so the cases are deterministic and don't
# drift if the shipped YAML changes.
MAPPINGS = {
    "version": "test",
    "reference_set": ["prov", "time"],
    "namespaces": {"prov": "http://www.w3.org/ns/prov#"},
    "mappings": [
        {
            "corpus_term": "authored_by",
            "corpus_kind": "edge_type",
            "standard_term": "prov:wasAttributedTo",
            "confidence": 0.93,
            "constraint": {
                "kind": "target_entity_type_in",
                "allowed": ["person", "organization"],
                "component": "sh:ClassConstraintComponent",
                "message": "prov:wasAttributedTo expects a prov:Agent target",
            },
        },
        # same corpus term -> two distinct standard terms => under-specified
        {
            "corpus_term": "member_of",
            "corpus_kind": "edge_type",
            "standard_term": "prov:actedOnBehalfOf",
            "confidence": 0.6,
        },
        {
            "corpus_term": "member_of",
            "corpus_kind": "edge_type",
            "standard_term": "prov:hadMember",
            "confidence": 0.6,
        },
        # low-confidence mapping with a constraint that WILL fail ->
        # must surface as sh:Info, never sh:Violation
        {
            "corpus_term": "supersedes",
            "corpus_kind": "edge_type",
            "standard_term": "prov:wasRevisionOf",
            "confidence": 0.50,
            "constraint": {
                "kind": "endpoints_same_entity_type",
                "component": "sh:NodeConstraintComponent",
                "message": "prov:wasRevisionOf relates same-kind entities",
            },
        },
    ],
}


def _implied() -> ImpliedOntology:
    return ImpliedOntology(
        version="t",
        source="declared",
        entity_types=["person", "publication"],
        edge_types=["authored_by", "member_of", "supersedes", "mentions"],
    )


def _graph():
    entities = [
        Entity(id="p1", name="Alice", entity_type="person"),
        Entity(id="pub1", name="Study A", entity_type="publication"),
        Entity(id="pub2", name="Study B", entity_type="publication"),
    ]
    edges = [
        # good: publication -> person  (prov:Agent target)
        Edge(source_id="pub1", target_id="p1", edge_type="authored_by"),
        # bad: publication -> publication (target not an Agent) => violation
        Edge(source_id="pub1", target_id="pub2", edge_type="authored_by"),
        # supersedes crossing entity types => fails endpoints_same_entity_type
        Edge(source_id="pub1", target_id="p1", edge_type="supersedes"),
    ]
    return entities, edges


def test_mappable_outcome():
    entities, edges = _graph()
    rep = score_external_fit(_implied(), entities, edges, mappings=MAPPINGS)
    authored = [a for a in rep["alignments"] if a["corpus_term"] == "authored_by"]
    assert authored, "authored_by should align"
    assert all(a["outcome"] == "mappable" for a in authored)
    # authored_by and supersedes each map to a single standard term => mappable.
    # member_of maps to two => under-specified (not counted as mappable).
    assert rep["mappable_count"] == 2


def test_under_specified_outcome():
    entities, edges = _graph()
    rep = score_external_fit(_implied(), entities, edges, mappings=MAPPINGS)
    member = [a for a in rep["alignments"] if a["corpus_term"] == "member_of"]
    assert len(member) == 2, "member_of maps to two standard terms"
    assert all(a["outcome"] == "under-specified" for a in member)
    # an overloaded term is NOT counted as cleanly mappable
    assert "member_of" not in {
        a["corpus_term"] for a in rep["alignments"] if a["outcome"] == "mappable"
    }


def test_idiosyncratic_unaligned():
    entities, edges = _graph()
    rep = score_external_fit(_implied(), entities, edges, mappings=MAPPINGS)
    # nothing in the PROV/Time table maps these
    assert "mentions" in rep["unaligned_types"]
    assert "person" in rep["unaligned_types"]
    assert "publication" in rep["unaligned_types"]
    # coverage is honest: 2 cleanly-mappable of 6 declared terms
    assert rep["considered_terms"] == 6
    assert abs(rep["aligned_coverage"] - 2 / 6) < 1e-3


def test_confidence_gating():
    entities, edges = _graph()
    rep = score_external_fit(_implied(), entities, edges, mappings=MAPPINGS)
    results = rep["audit"]["sh:result"]
    by_path = {r["sh:resultPath"]: r for r in results}

    # high-confidence authored_by failure -> Violation
    assert by_path["authored_by"]["sh:resultSeverity"] == "sh:Violation"
    # low-confidence supersedes failure -> Info (gated down), NOT a violation
    assert by_path["supersedes"]["sh:resultSeverity"] == "sh:Info"

    # every result carries provenance
    assert all("provenance" in r for r in results)
    # report does not conform (there is a genuine Violation)
    assert rep["audit"]["sh:conforms"] is False


def test_clean_graph_conforms():
    # only the good authored_by edge -> no violations at all
    entities = [
        Entity(id="p1", name="Alice", entity_type="person"),
        Entity(id="pub1", name="Study A", entity_type="publication"),
    ]
    edges = [Edge(source_id="pub1", target_id="p1", edge_type="authored_by")]
    rep = score_external_fit(_implied(), entities, edges, mappings=MAPPINGS)
    assert rep["audit"]["sh:conforms"] is True


def test_flows_through_score_cat8_additively():
    """8f is reachable via score_cat8().to_dict() and does not disturb the
    existing 8a-8e / introspection keys (the additive contract)."""
    from sme.categories.ontology_coherence import score_cat8

    entities, edges = _graph()
    report = score_cat8(_implied(), entities, edges, {})  # empty structural_health
    d = report.to_dict()

    # existing keys still present and untouched
    for k in (
        "8a_type_coverage",
        "8b_edge_vocabulary",
        "8c_schema_alignment",
        "8d_drift",
        "8e_claims",
        "introspection",
    ):
        assert k in d, f"existing Cat 8 key {k!r} missing — additive contract broken"

    # new key present and well-formed
    assert "8f_external_fit" in d
    ef = d["8f_external_fit"]
    assert ef is not None
    assert "reference_set" in ef
    assert "audit" in ef and "sh:result" in ef["audit"]


def test_shipped_table_loads_and_runs():
    """The real PROV-O/OWL-Time table loads and scores without error."""
    mappings = load_standard_mappings()
    assert mappings.get("reference_set") == ["prov", "time"]
    entities = [
        Entity(id="e1", name="Recall", entity_type="event",
               properties={"timestamp": "2019-01-31T00:00:00Z"}),
        Entity(id="e2", name="Bad event", entity_type="event",
               properties={"timestamp": "last tuesday"}),  # not ISO
    ]
    edges = [Edge(source_id="e1", target_id="e2", edge_type="supersedes")]
    rep = score_external_fit(_implied(), entities, edges, mappings=mappings)
    # the malformed timestamp is caught by the OWL-Time datatype rule
    paths = {r["sh:resultPath"] for r in rep["audit"]["sh:result"]}
    assert "timestamp" in paths
