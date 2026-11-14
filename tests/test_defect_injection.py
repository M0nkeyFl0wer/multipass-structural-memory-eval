"""Tests for the defect-injection harness.

A small synthetic graph, scored by the real `score_reading`. Each defect
must be caught at a gross size (25%), and each control must stay silent.
If a defect is missed here, either the mutation or the detector is broken,
and the matrix on a real graph would be meaningless.
"""

from __future__ import annotations

import random

import pytest

from sme.adapters.base import Edge, Entity
from sme.defect_injection import DEFECTS, choose_targets, format_matrix, run_matrix


def _graph():
    rng = random.Random(0)
    ents = [Entity(id=f"c{i}", name=f"concept {i}", entity_type="concept") for i in range(400)]
    ents += [Entity(id=f"n{i}", name=f"note {i}", entity_type="Note") for i in range(300)]
    eds = [Edge(f"c{i}", f"c{i + 1}", "PART_OF") for i in range(399)]
    eds += [Edge(f"c{rng.randrange(400)}", f"c{rng.randrange(400)}", "PART_OF") for _ in range(300)]
    eds += [Edge(f"c{i}", f"c{(i * 7) % 400}", "DEPENDS_ON") for i in range(150)]
    eds += [Edge(f"c{i}", f"c{(i * 3) % 400}", "SUPPORTS") for i in range(60)]
    return ents, eds


@pytest.fixture
def ontology(tmp_path):
    p = tmp_path / "ontology.yaml"
    p.write_text("entity_types: [concept, Note]\nedge_types: [part_of, depends_on, supports]\n")
    return str(p)


def test_targets_aim_at_the_load_bearing_parts():
    t = choose_targets(*_graph())
    assert (t.edge_type, t.small_edge_type, t.entity_type, t.doc_entity_type) == (
        "PART_OF", "SUPPORTS", "concept", "Note")


def test_every_defect_is_caught_at_gross_size_and_controls_stay_silent(ontology):
    _, rows = run_matrix(*_graph(), sizes=(0.25,), ontology=ontology)
    by = {r.defect: r for r in rows}
    assert set(by) == {d.name for d in DEFECTS}  # nothing silently skipped
    misses = [f"{r.defect}: expected {r.expected}, got {r.fired}" for r in rows if not r.detected]
    assert misses == []


def test_tiny_damage_is_reported_as_missed_not_hidden(ontology):
    # 0.1% of edges is below every tolerance: the matrix must say MISSED.
    _, rows = run_matrix(*_graph(), sizes=(0.001,), ontology=ontology, defects=["drop_edges"])
    assert [r.detected for r in rows] == [False]
    assert "MISSED" in format_matrix(choose_targets(*_graph()), rows)


def test_mutations_never_touch_the_input_lists(ontology):
    ents, eds = _graph()
    before = (list(ents), list(eds))
    run_matrix(ents, eds, sizes=(0.25,), ontology=ontology)
    assert (ents, eds) == before


def test_undeclared_relation_is_skipped_without_an_ontology():
    _, rows = run_matrix(*_graph(), sizes=(0.25,))
    assert "undeclared_relation" not in {r.defect for r in rows}


def test_cli_inject_on_the_good_dog_corpus(tmp_path, capsys):
    from pathlib import Path

    from sme.cli import main

    corpus = Path(__file__).resolve().parents[1] / "sme" / "corpora" / "good-dog-corpus"
    out = tmp_path / "m.json"
    rc = main(["inject", "--adapter", "corpus", "--db", str(corpus / "vault"),
               "--sizes", "0.5", "--json", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "smallest size caught:" in text and "false alarms on controls:" in text
    assert out.exists()


def test_purge_control_is_skipped_not_passed_when_there_is_no_document_layer():
    ents, eds = _graph()
    ents = [e for e in ents if e.entity_type != "Note"]
    _, rows = run_matrix(ents, eds, sizes=(0.25,))
    assert "purge_documents" not in {r.defect for r in rows}
