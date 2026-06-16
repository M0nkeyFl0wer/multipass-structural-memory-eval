"""Tests for sme.categories.multi_hop (Cat 2c).

Covers:

- Hop-bucket grouping over the retrieve-results JSON shape
  (mean_recall, hit_rate, mean_tokens, correct_count per hop).
- A/B/C delta math (delta_B_minus_A, delta_B_minus_C, ratio_B_over_A)
  including pp deltas, token deltas, and infinite ratios when A has
  zero recall at a hop.
- Verdict logic: "structure earns complexity", "neutral tax", "harmful",
  and the ratio-grows-with-depth branch.
- Edge cases: missing Condition A or C, single hop bucket, empty
  question list, single question.
- to_dict() output shape — the JSON consumers downstream depend on
  this.
"""
from __future__ import annotations

import json

import pytest

from sme.categories.multi_hop import (
    Cat2cReport,
    HopBreakdown,
    _build_condition_report,
    _verdict,
    score_cat2c,
)


# ── Helpers ────────────────────────────────────────────────────────


def _write_retrieve_json(path, questions: list[dict]) -> str:
    """Write a minimal retrieve-results JSON payload and return the path."""
    path.write_text(json.dumps({"questions": questions}))
    return str(path)


def _q(min_hops: int, recall: float, tokens: float, hit: bool | None = None) -> dict:
    """Build a single retrieve-results question dict."""
    if hit is None:
        hit = recall > 0
    return {
        "min_hops": min_hops,
        "recall": recall,
        "tokens": tokens,
        "hit": hit,
    }


# ── _build_condition_report ────────────────────────────────────────


def test_build_condition_report_groups_by_hop():
    data = {
        "questions": [
            _q(1, 1.0, 100),
            _q(1, 0.5, 200),
            _q(2, 1.0, 300),
            _q(3, 0.0, 400, hit=False),
        ]
    }
    rep = _build_condition_report("B", "graph", data)
    assert rep.total_questions == 4
    # Three hop buckets
    assert set(rep.by_hop.keys()) == {1, 2, 3}
    # 1-hop bucket: two questions, mean recall = 0.75
    assert rep.by_hop[1].n == 2
    assert rep.by_hop[1].mean_recall == pytest.approx(0.75)
    assert rep.by_hop[1].mean_tokens == pytest.approx(150.0)
    assert rep.by_hop[1].correct_count == 1  # only the recall=1.0 one
    # 2-hop bucket: single full-recall question
    assert rep.by_hop[2].n == 1
    assert rep.by_hop[2].mean_recall == pytest.approx(1.0)
    assert rep.by_hop[2].correct_count == 1
    # 3-hop bucket: missed
    assert rep.by_hop[3].correct_count == 0
    assert rep.by_hop[3].hit_rate == 0.0


def test_build_condition_report_hit_rate_distinct_from_recall():
    """A question with recall < 1 but hit=True still counts as a hit."""
    data = {
        "questions": [
            _q(1, 0.5, 100, hit=True),
            _q(1, 0.5, 100, hit=True),
            _q(1, 0.0, 100, hit=False),
        ]
    }
    rep = _build_condition_report("B", "graph", data)
    assert rep.by_hop[1].hit_rate == pytest.approx(2 / 3)
    assert rep.by_hop[1].correct_count == 0  # no full-recall queries


def test_build_condition_report_overall_totals():
    data = {
        "questions": [
            _q(1, 1.0, 100),
            _q(2, 1.0, 200),
            _q(3, 0.5, 300, hit=True),
        ]
    }
    rep = _build_condition_report("B", "graph", data)
    assert rep.total_questions == 3
    assert rep.full_recall == 2
    assert rep.partial_hits == 3
    assert rep.mean_recall == pytest.approx((1 + 1 + 0.5) / 3)
    assert rep.mean_tokens == pytest.approx((100 + 200 + 300) / 3)
    # tokens_per_correct = total_tokens / full_recall
    assert rep.tokens_per_correct == pytest.approx(600 / 2)


def test_build_condition_report_no_full_recall_yields_none_tokens_per_correct():
    data = {"questions": [_q(1, 0.5, 100, hit=True)]}
    rep = _build_condition_report("B", "graph", data)
    assert rep.full_recall == 0
    assert rep.tokens_per_correct is None


def test_build_condition_report_empty_questions():
    rep = _build_condition_report("B", "graph", {"questions": []})
    assert rep.total_questions == 0
    assert rep.full_recall == 0
    assert rep.mean_recall == 0.0
    assert rep.mean_tokens == 0.0
    assert rep.tokens_per_correct is None
    assert rep.by_hop == {}


def test_build_condition_report_missing_min_hops_defaults_to_zero():
    """Question with no min_hops field still gets grouped — into bucket 0."""
    data = {"questions": [{"recall": 1.0, "tokens": 100, "hit": True}]}
    rep = _build_condition_report("B", "graph", data)
    assert 0 in rep.by_hop
    assert rep.by_hop[0].n == 1


# ── score_cat2c — requires graph_json ─────────────────────────────


def test_score_cat2c_requires_graph_json():
    with pytest.raises(ValueError, match="graph_json"):
        score_cat2c()  # type: ignore[call-arg]


def test_score_cat2c_b_only(tmp_path):
    """With only Condition B, no deltas computed; verdict is 'incomplete'."""
    b = _write_retrieve_json(
        tmp_path / "b.json", [_q(1, 0.5, 100), _q(2, 1.0, 200)]
    )
    report = score_cat2c(graph_json=b)
    assert "B" in report.conditions
    assert "A" not in report.conditions
    assert "C" not in report.conditions
    assert report.delta_B_minus_A == {}
    assert report.delta_B_minus_C == {}
    assert report.ratio_B_over_A == {}
    assert report.verdict == "incomplete"


# ── A/B/C delta math ──────────────────────────────────────────────


def test_score_cat2c_full_abc_deltas(tmp_path):
    """All three conditions, two hop depths each."""
    a = _write_retrieve_json(
        tmp_path / "a.json", [_q(1, 0.8, 100), _q(2, 0.2, 150)]
    )
    b = _write_retrieve_json(
        tmp_path / "b.json", [_q(1, 0.9, 120), _q(2, 0.8, 180)]
    )
    c = _write_retrieve_json(
        tmp_path / "c.json", [_q(1, 0.85, 110), _q(2, 0.4, 160)]
    )
    report = score_cat2c(flat_json=a, graph_json=b, no_structure_json=c)

    # 1-hop: B-A = +10pp recall, +20 tokens
    d1a = report.delta_B_minus_A[1]
    assert d1a["recall_delta_pp"] == pytest.approx(10.0)
    assert d1a["tokens_delta"] == pytest.approx(20.0)
    # 2-hop: B-A = +60pp recall, +30 tokens
    d2a = report.delta_B_minus_A[2]
    assert d2a["recall_delta_pp"] == pytest.approx(60.0)
    assert d2a["tokens_delta"] == pytest.approx(30.0)
    # 1-hop: B-C = +5pp
    d1c = report.delta_B_minus_C[1]
    assert d1c["recall_delta_pp"] == pytest.approx(5.0)
    # 2-hop: B-C = +40pp
    d2c = report.delta_B_minus_C[2]
    assert d2c["recall_delta_pp"] == pytest.approx(40.0)

    # Ratio B/A: 1-hop = 0.9/0.8, 2-hop = 0.8/0.2 = 4.0 — grows with hops
    assert report.ratio_B_over_A[1] == pytest.approx(0.9 / 0.8)
    assert report.ratio_B_over_A[2] == pytest.approx(4.0)


def test_score_cat2c_ratio_infinite_when_a_recall_zero(tmp_path):
    """If Condition A has zero recall at a depth, ratio is +inf."""
    a = _write_retrieve_json(tmp_path / "a.json", [_q(3, 0.0, 100, hit=False)])
    b = _write_retrieve_json(tmp_path / "b.json", [_q(3, 0.7, 200, hit=True)])
    report = score_cat2c(flat_json=a, graph_json=b)
    assert report.ratio_B_over_A[3] == float("inf")


def test_score_cat2c_negative_delta_when_b_worse_than_a(tmp_path):
    a = _write_retrieve_json(tmp_path / "a.json", [_q(2, 0.9, 100)])
    b = _write_retrieve_json(tmp_path / "b.json", [_q(2, 0.4, 200)])
    report = score_cat2c(flat_json=a, graph_json=b)
    assert report.delta_B_minus_A[2]["recall_delta_pp"] == pytest.approx(-50.0)
    assert report.delta_B_minus_A[2]["tokens_delta"] == pytest.approx(100.0)


def test_score_cat2c_alignment_skips_unmatched_hops(tmp_path):
    """If A has 1-hop and B has 2-hop only, no delta is computed for
    hops missing from either side."""
    a = _write_retrieve_json(tmp_path / "a.json", [_q(1, 0.5, 100)])
    b = _write_retrieve_json(tmp_path / "b.json", [_q(2, 0.8, 200)])
    report = score_cat2c(flat_json=a, graph_json=b)
    assert report.delta_B_minus_A == {}  # no overlap → no delta rows


# ── Verdict logic ─────────────────────────────────────────────────


def test_verdict_incomplete_when_no_a():
    report = Cat2cReport()
    # No delta_B_minus_A populated → verdict is "incomplete"
    verdict, details = _verdict(report)
    assert verdict == "incomplete"
    assert any("Condition A" in d for d in details)


def test_verdict_neutral_tax_when_b_matches_a():
    """B - A is near zero at all depths → 'neutral tax'."""
    report = Cat2cReport()
    report.delta_B_minus_A = {
        1: {"recall_delta_pp": 1.0, "tokens_delta": 0},
        2: {"recall_delta_pp": -2.0, "tokens_delta": 0},
    }
    report.delta_B_minus_C = {
        1: {"recall_delta_pp": 0.0, "tokens_delta": 0},
        2: {"recall_delta_pp": 0.0, "tokens_delta": 0},
    }
    verdict, details = _verdict(report)
    assert verdict == "structure is a neutral tax"
    # And the B-C narration should call it "neutral tax / nothing beyond metadata"
    assert any("neutral tax" in d for d in details)


def test_verdict_earns_complexity_when_ratio_grows():
    """B beats A at multiple depths AND the ratio grows with hop depth."""
    report = Cat2cReport()
    report.delta_B_minus_A = {
        1: {"recall_delta_pp": 10.0, "tokens_delta": 50},
        2: {"recall_delta_pp": 40.0, "tokens_delta": 100},
        3: {"recall_delta_pp": 60.0, "tokens_delta": 200},
    }
    report.ratio_B_over_A = {1: 1.1, 2: 2.0, 3: 5.0}  # clearly grows
    report.delta_B_minus_C = {
        1: {"recall_delta_pp": 8.0, "tokens_delta": 0},
        2: {"recall_delta_pp": 30.0, "tokens_delta": 0},
    }
    verdict, details = _verdict(report)
    assert verdict == "structure earns complexity (scales with depth)"
    assert any("ratio grows" in d.lower() or "spec predicts" in d.lower() for d in details)


def test_verdict_uniform_scale_when_b_wins_flat_but_ratio_flat():
    """B beats A but the B/A ratio is roughly constant across depths."""
    report = Cat2cReport()
    report.delta_B_minus_A = {
        1: {"recall_delta_pp": 10.0, "tokens_delta": 0},
        2: {"recall_delta_pp": 10.0, "tokens_delta": 0},
    }
    # 1.5x at 1-hop, 1.5x at 2-hop — last is NOT > first * 1.2
    report.ratio_B_over_A = {1: 1.5, 2: 1.5}
    verdict, _ = _verdict(report)
    assert verdict == "structure adds value at uniform scale"


def test_verdict_harmful_when_b_loses_to_a_only():
    report = Cat2cReport()
    report.delta_B_minus_A = {
        1: {"recall_delta_pp": -10.0, "tokens_delta": 100},
        2: {"recall_delta_pp": -20.0, "tokens_delta": 200},
    }
    report.ratio_B_over_A = {1: 0.6, 2: 0.5}
    verdict, _ = _verdict(report)
    assert verdict == "structure harmful at multi-hop"


def test_verdict_mixed_when_some_win_some_lose():
    report = Cat2cReport()
    report.delta_B_minus_A = {
        1: {"recall_delta_pp": -10.0, "tokens_delta": 0},
        2: {"recall_delta_pp": 20.0, "tokens_delta": 0},
    }
    report.ratio_B_over_A = {1: 0.7, 2: 1.5}
    verdict, _ = _verdict(report)
    assert verdict == "mixed: structure helps at some depths and hurts at others"


def test_verdict_b_minus_c_negative_flagged_in_details():
    """Even if B beats A, a negative B-C is surfaced as 'structurally harmful'
    in the details."""
    report = Cat2cReport()
    report.delta_B_minus_A = {
        2: {"recall_delta_pp": 20.0, "tokens_delta": 0},
    }
    report.ratio_B_over_A = {2: 1.4}
    report.delta_B_minus_C = {
        2: {"recall_delta_pp": -15.0, "tokens_delta": 0},
    }
    _, details = _verdict(report)
    assert any("structural routing is actively harmful" in d for d in details)


# ── to_dict() shape contract ─────────────────────────────────────


def test_to_dict_keys_and_string_hop_keys(tmp_path):
    """to_dict converts integer hop keys to strings (JSON-friendly)."""
    a = _write_retrieve_json(tmp_path / "a.json", [_q(1, 0.5, 100)])
    b = _write_retrieve_json(tmp_path / "b.json", [_q(1, 0.7, 110)])
    report = score_cat2c(flat_json=a, graph_json=b)
    d = report.to_dict()
    # Top-level keys
    assert {
        "conditions",
        "delta_B_minus_A",
        "delta_B_minus_C",
        "ratio_B_over_A",
        "verdict",
        "verdict_details",
    } <= set(d.keys())
    # Hop keys serialized as strings
    assert all(isinstance(k, str) for k in d["delta_B_minus_A"].keys())
    assert all(isinstance(k, str) for k in d["ratio_B_over_A"].keys())
    # The condition payload also string-keyed by hop
    by_hop = d["conditions"]["B"]["by_hop"]
    assert all(isinstance(k, str) for k in by_hop.keys())


def test_to_dict_roundtrip_through_json(tmp_path):
    """The whole report should be JSON-serializable end-to-end."""
    b = _write_retrieve_json(tmp_path / "b.json", [_q(1, 1.0, 100)])
    report = score_cat2c(graph_json=b)
    payload = json.dumps(report.to_dict())
    parsed = json.loads(payload)
    assert parsed["conditions"]["B"]["full_recall"] == 1


# ── HopBreakdown dataclass sanity ────────────────────────────────


def test_hop_breakdown_dataclass_fields():
    bk = HopBreakdown(
        hops=2,
        n=4,
        mean_recall=0.5,
        hit_rate=0.75,
        mean_tokens=200.0,
        correct_count=2,
    )
    assert bk.hops == 2
    assert bk.correct_count == 2
