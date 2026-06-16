"""Cat 8f SHACL ValidationReport — real round-trip conformance.

The other 8f tests assert the report's *values* (e.g.
``sh:resultSeverity == "sh:Violation"``). That checks our own dict
against itself: it cannot tell whether a real SHACL/JSON-LD consumer
would read the report the way SHACL intends. This test closes that gap
by parsing the emitted ``audit`` block through rdflib's JSON-LD reader
and asserting the SHACL-vocabulary terms resolve to the *IRIs* SHACL
defines — not to look-alike string literals.

It runs against the **shipped** ``standard_ontologies.yaml`` (not a test
fixture), so it proves the report SME actually emits conforms — and it
pins the known, deliberate limitation so it can never silently regress:
the node-reference terms (sh:focusNode, sh:value, sh:resultPath) are
graph-local STRINGS, not IRIs. Minting IRIs for property-graph nodes is
the RDF-projection commitment draft 03 defers; until that decision is
made, the report carries conformance + severity + constraint-component
as real SHACL, and the focus nodes as opaque labels.
"""

from __future__ import annotations

import json

import pytest

from sme.adapters.base import Edge, Entity
from sme.categories.external_fit import load_standard_mappings, score_external_fit
from sme.categories.ontology_coherence import ImpliedOntology

pytest.importorskip("rdflib")
from rdflib import Graph, Literal, Namespace, URIRef  # noqa: E402

SH = Namespace("http://www.w3.org/ns/shacl#")


def _audit_graph() -> Graph:
    """Build the 8f report from the shipped mapping table over a small
    graph engineered to produce one high-confidence Violation
    (``authored_by`` target not a prov:Agent) and one low-confidence,
    gated-down Info (``supersedes`` across entity types), then parse the
    emitted ``audit`` block as JSON-LD."""
    implied = ImpliedOntology(
        version="conformance-test",
        source="declared",
        entity_types=["publication", "person"],
        edge_types=["authored_by", "supersedes"],
    )
    entities = [
        Entity(id="pub1", name="Study A", entity_type="publication"),
        Entity(id="pub2", name="Study B", entity_type="publication"),
        Entity(id="per1", name="Alice", entity_type="person"),
    ]
    edges = [
        # authored_by -> target must be person/organization; pub2 is not
        # => Violation (confidence 0.93 >= 0.85)
        Edge(source_id="pub1", target_id="pub2", edge_type="authored_by"),
        # supersedes -> endpoints must be same entity_type; these differ
        # => finding gated to Info (confidence 0.78 < 0.85)
        Edge(source_id="pub1", target_id="per1", edge_type="supersedes"),
    ]
    rep = score_external_fit(
        implied, entities, edges, mappings=load_standard_mappings()
    )
    g = Graph()
    g.parse(data=json.dumps(rep["audit"]), format="json-ld")
    return g


def test_audit_parses_as_jsonld():
    """The emitted report is valid JSON-LD a real RDF reader accepts."""
    assert len(_audit_graph()) > 0


def test_severity_resolves_to_real_shacl_iris():
    """sh:resultSeverity must be the IRI sh:Violation / sh:Info, not a
    string literal a SHACL consumer would ignore."""
    g = _audit_graph()
    severities = {o for _, o in g.subject_objects(SH.resultSeverity)}
    assert severities, "no sh:resultSeverity triples emitted"
    assert all(isinstance(o, URIRef) for o in severities)
    assert SH.Violation in severities
    assert SH.Info in severities


def test_constraint_component_resolves_to_shacl_iri():
    g = _audit_graph()
    comps = {o for _, o in g.subject_objects(SH.sourceConstraintComponent)}
    assert comps, "no sh:sourceConstraintComponent triples emitted"
    assert all(isinstance(o, URIRef) for o in comps)
    assert SH.ClassConstraintComponent in comps
    assert SH.NodeConstraintComponent in comps


def test_conforms_is_a_typed_boolean_false():
    g = _audit_graph()
    conforms = [o for _, o in g.subject_objects(SH.conforms)]
    assert len(conforms) == 1
    assert isinstance(conforms[0], Literal)
    assert conforms[0].value is False  # the fixture graph has a real Violation


def test_node_refs_are_strings_not_iris_documented_limitation():
    """Pin the deliberate tradeoff: focus/value/path are graph-local
    strings, NOT dereferenceable IRIs. If this ever flips (someone adds
    an RDF projection / base namespace), update this test as a conscious
    decision — never let the interop claim quietly broaden."""
    g = _audit_graph()
    for term in (SH.focusNode, SH.value, SH.resultPath):
        objs = [o for _, o in g.subject_objects(term)]
        assert objs, f"no {term} triples emitted"
        assert all(isinstance(o, Literal) for o in objs), (
            f"{term} unexpectedly resolved to an IRI — the report now claims "
            "more SHACL conformance than documented. Update draft 03 + the "
            "@context comment before changing this assertion."
        )
