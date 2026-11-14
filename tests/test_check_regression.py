"""Tests for day-over-day regression detection in `sme-eval check`.

Each test perturbs ONE metric of a realistic baseline (shaped like the real
nightly vault-rag reading) and asserts exactly that metric is flagged, so a
finding can never be credited to the wrong cause.
"""

from __future__ import annotations

import copy
import json

import pytest

from sme.check_regression import Tolerances, compare_readings, compare_readings_keyed

BASELINE = {
    "cat4": {
        "entities": 200_000,
        "edges": 28_000,
        "canonical_collisions": 40_000,
        "required_field_coverage": 1.0,
        "edge_type_counts": {"PART_OF": 8_600, "DEPENDS_ON": 4_400, "AUTHORED_BY": 5},
        "dominant_edge_type": "PART_OF",
        "dominant_edge_type_fraction": 0.30,
    },
    "cat5": {"isolated_nodes": 180_000},
}


def _with(path: str, value):
    """Copy of BASELINE with one dotted key replaced."""
    reading = copy.deepcopy(BASELINE)
    *parents, leaf = path.split(".")
    node = reading
    for key in parents:
        node = node[key]
    node[leaf] = value
    return reading


def test_identical_readings_are_clean():
    assert compare_readings(BASELINE, BASELINE) == []


def test_normal_night_is_not_an_alarm():
    # What a normal night on the real vault graph looks like (21 replayed
    # nightlies, 2026-10/11): edges GROW with ingest and the dominant type's
    # share wobbles by up to ~0.016. Nothing falls.
    cur = _with("cat4.edges", 28_560)  # +2%
    cur["cat4"]["dominant_edge_type_fraction"] = 0.32
    assert compare_readings(BASELINE, cur) == []


def test_a_two_percent_edge_loss_is_an_alarm():
    # Before calibration (edge_drop=0.05) this passed unseen. Normal nights
    # never lose edges, so 2% of them vanishing is worth a look.
    findings = compare_readings(BASELINE, _with("cat4.edges", 27_440))
    assert len(findings) == 1 and findings[0].startswith("edges fell")


def test_edge_drop_flagged():
    findings = compare_readings(BASELINE, _with("cat4.edges", 20_000))
    assert len(findings) == 1 and findings[0].startswith("edges fell")


def test_edge_type_disappearing_flagged():
    cur = _with("cat4.edge_type_counts", {"PART_OF": 8_600, "AUTHORED_BY": 5})
    findings = compare_readings(BASELINE, cur)
    assert findings == ["edge type DEPENDS_ON disappeared (4400 -> 0)"]


def test_edge_type_partial_drop_flagged():
    cur = _with("cat4.edge_type_counts",
                {"PART_OF": 8_600, "DEPENDS_ON": 2_000, "AUTHORED_BY": 5})
    findings = compare_readings(BASELINE, cur)
    assert len(findings) == 1 and "DEPENDS_ON fell" in findings[0]


def test_tiny_edge_types_are_ignored():
    # AUTHORED_BY has 5 edges; losing them all is noise, not a signal.
    cur = _with("cat4.edge_type_counts", {"PART_OF": 8_600, "DEPENDS_ON": 4_400})
    assert compare_readings(BASELINE, cur) == []


def test_collision_rise_flagged():
    findings = compare_readings(BASELINE, _with("cat4.canonical_collisions", 50_000))
    assert len(findings) == 1 and "canonical collisions rose" in findings[0]


def test_monoculture_creep_flagged():
    findings = compare_readings(BASELINE, _with("cat4.dominant_edge_type_fraction", 0.40))
    assert len(findings) == 1 and "monoculture" in findings[0]


def test_coverage_drop_flagged():
    findings = compare_readings(BASELINE, _with("cat4.required_field_coverage", 0.95))
    assert len(findings) == 1 and "coverage fell" in findings[0]


def test_isolated_share_rise_flagged():
    findings = compare_readings(BASELINE, _with("cat5.isolated_nodes", 190_000))
    assert len(findings) == 1 and "isolated-node share" in findings[0]


def test_entity_purge_alone_is_not_an_alarm():
    # Entities fall 10% and isolates fall with them: a legitimate purge.
    # Raw totals are not a health signal for this graph; proportions are.
    cur = _with("cat4.entities", 180_000)
    cur["cat5"]["isolated_nodes"] = 162_000
    assert compare_readings(BASELINE, cur) == []


def test_old_baseline_missing_fields_never_false_alarms():
    assert compare_readings({"cat4": {"edges": 28_000}}, BASELINE) == []


def test_tolerances_are_configurable():
    cur = _with("cat4.edges", 27_860)  # 0.5% drop: under the 1% floor
    assert compare_readings(BASELINE, cur) == []
    assert compare_readings(BASELINE, cur, Tolerances(edge_drop=0.001))


def test_against_real_nightly_shape(tmp_path):
    # The real sme.json round-trips through JSON; make sure nothing in the
    # comparison depends on Python-only types.
    p = tmp_path / "prev.json"
    p.write_text(json.dumps(BASELINE))
    assert compare_readings(json.loads(p.read_text()), BASELINE) == []


@pytest.mark.parametrize("prev_edges", [0])
def test_zero_baseline_does_not_divide_by_zero(prev_edges):
    assert compare_readings(_with("cat4.edges", prev_edges), BASELINE) == []


# --- locating: findings say WHERE, not only how much ---------------------

TYPED = {
    "cat4": {
        "entities": 200_000,
        "edges": 28_000,
        "edge_type_counts": {"PART_OF": 8_600, "DEPENDS_ON": 4_400},
        "entity_type_counts": {"Note": 150_000, "Concept": 10_000, "Tiny": 50},
        "canonical_collisions": 40_000,
        "collision_examples": [{"key": "salmon", "type": "Concept", "n": 40, "names": ["Salmon"]}],
    },
    "cat5": {
        "isolated_nodes": 150_000,
        "isolated_by_type": {"Note": 145_000, "Concept": 1_000, "Tiny": 10},
    },
}


def _typed(**changes):
    r = copy.deepcopy(TYPED)
    for path, value in changes.items():
        *parents, leaf = path.split("__")
        node = r
        for k in parents:
            node = node[k]
        node[leaf] = value
    return r


def test_one_type_going_dark_is_caught_even_when_global_share_barely_moves():
    # Concept isolates 10% -> 15%: +500 isolates is only +0.25 points of the
    # global share (under its 0.5-point tolerance), but plain per type.
    cur = _typed(cat5__isolated_by_type={"Note": 145_000, "Concept": 1_500, "Tiny": 10},
                 cat5__isolated_nodes=150_500)
    findings = compare_readings_keyed(TYPED, cur)
    assert [k for k, _ in findings] == ["isolated_share:Concept"]


def test_tiny_types_are_not_judged_per_type():
    cur = _typed(cat5__isolated_by_type={"Note": 145_000, "Concept": 1_000, "Tiny": 50})
    assert compare_readings_keyed(TYPED, cur) == []


def test_edge_drop_names_the_types_that_fell():
    cur = _typed(cat4__edges=20_000, cat4__edge_type_counts={"PART_OF": 1_000, "DEPENDS_ON": 4_400})
    (what,) = [w for k, w in compare_readings_keyed(TYPED, cur) if k == "edges"]
    assert "largest drops: PART_OF -7600" in what


def test_collision_rise_names_the_largest_groups():
    cur = _typed(cat4__canonical_collisions=50_000)
    (what,) = [w for k, w in compare_readings_keyed(TYPED, cur) if k == "canonical_collisions"]
    assert "'Salmon' x40" in what


def test_old_readings_without_type_fields_still_compare():
    # Pre-2026-11-13 readings have no per-type fields: no crash, no false alarm.
    assert compare_readings_keyed(BASELINE, BASELINE) == []
    # Baseline lacks the per-type fields: no per-type finding can be formed.
    keys = [k for k, _ in compare_readings_keyed(BASELINE, TYPED)]
    assert not any(k.startswith("isolated_share:") for k in keys)


# --- Cat 8 vocabulary drift ---------------------------------------------

C8 = {
    "ontology": "/x/schema.md",
    "types_missing": [],
    "types_undeclared": ["handoff", "session"],
    "edges_missing": ["broader_than"],
    "edges_undeclared": ["IDENTIFIED_IN"],
}


def _c8(**changes):
    return {"cat8": {**C8, **changes}}


def test_standing_drift_is_not_reported_every_night():
    assert compare_readings_keyed(_c8(), _c8()) == []


def test_new_undeclared_edge_type_is_flagged():
    cur = _c8(edges_undeclared=["IDENTIFIED_IN", "CAUSES"])
    assert [k for k, _ in compare_readings_keyed(_c8(), cur)] == ["cat8:undeclared_edge:CAUSES"]


def test_declared_type_going_unused_is_flagged():
    cur = _c8(types_missing=["person"])
    assert [k for k, _ in compare_readings_keyed(_c8(), cur)] == ["cat8:vanished:person"]


def test_new_entity_types_collapse_to_one_finding():
    cur = _c8(types_undeclared=["handoff", "session", "a", "b"])
    findings = compare_readings_keyed(_c8(), cur)
    assert [k for k, _ in findings] == ["cat8:undeclared_entity_types"]
    assert "2 new entity type(s)" in findings[0][1]


def test_different_ontology_files_are_not_compared():
    cur = _c8(ontology="/y/other.yaml", edges_undeclared=["X", "Y"])
    assert compare_readings_keyed(_c8(), cur) == []


def test_duplicates_appearing_in_a_graph_that_had_none_are_flagged():
    # Found by the defect-injection harness: 0 -> 72 produced no finding.
    prev = {"cat4": {"canonical_collisions": 0}}
    findings = compare_readings_keyed(prev, {"cat4": {"canonical_collisions": 72}})
    assert [k for k, _ in findings] == ["canonical_collisions"]
    assert "from zero" in findings[0][1]


def test_a_handful_of_new_duplicates_is_not_an_alarm():
    prev = {"cat4": {"canonical_collisions": 10}}
    assert compare_readings_keyed(prev, {"cat4": {"canonical_collisions": 30}}) == []


def test_collision_names_stay_one_short_line():
    # Seen on the real graph: chunk nodes named by their whole multi-line
    # body turned one finding into a 60-line dump.
    body = "## Caddy routes\n\n| Listen | Upstream |\n" + "| :9000 | x |\n" * 50
    cur = _typed(cat4__canonical_collisions=50_000,
                 cat4__collision_examples=[{"key": body, "type": "Chunk", "n": 854, "names": [body]}])
    (what,) = [w for k, w in compare_readings_keyed(TYPED, cur) if k == "canonical_collisions"]
    assert "\n" not in what and "x854" in what and len(what) < 250


def test_changing_the_judged_tables_is_not_drift():
    # The first night after the nightly starts passing --ontology-tables, every
    # type list shrinks at once. That is a config change, not a finding.
    cur = _c8(tables=["Entity"], types_undeclared=["concept"], edges_undeclared=["X"])
    assert compare_readings_keyed(_c8(), cur) == []
