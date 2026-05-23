"""Tests for Category 2c multi-hop retrieval scorer (issue #18).

Exercises score_cat2c, _build_condition_report, and the verdict logic
with synthetic retrieve-results JSONs — no file I/O, no adapters.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sme.categories.multi_hop import (
    _build_condition_report,
    format_report,
    score_cat2c,
)


def _write_retrieve_json(tmp_path: Path, name: str, questions: list[dict]) -> Path:
    """Write a minimal retrieve-results JSON to disk."""
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"questions": questions}))
    return path


def _make_questions(specs: list[tuple[int, float, int]]) -> list[dict]:
    """Create question dicts from (min_hops, recall, tokens) tuples."""
    return [
        {
            "id": f"q{i}",
            "text": f"question {i}",
            "min_hops": hops,
            "recall": recall,
            "hit": recall > 0,
            "tokens": tokens,
        }
        for i, (hops, recall, tokens) in enumerate(specs)
    ]


class TestBuildConditionReport:
    def test_basic_aggregation(self):
        data = {
            "questions": _make_questions([
                (0, 1.0, 100),
                (0, 0.5, 200),
                (1, 1.0, 300),
            ])
        }
        cr = _build_condition_report("B", "test", data)
        assert cr.total_questions == 3
        assert cr.full_recall == 2
        assert cr.partial_hits == 3
        assert cr.by_hop[0].n == 2
        assert cr.by_hop[1].n == 1
        assert cr.by_hop[0].mean_recall == pytest.approx(0.75)
        assert cr.by_hop[1].mean_recall == pytest.approx(1.0)

    def test_tokens_per_correct_none_when_zero(self):
        data = {"questions": _make_questions([(0, 0.0, 100)])}
        cr = _build_condition_report("A", "t", data)
        assert cr.tokens_per_correct is None

    def test_empty_questions(self):
        data = {"questions": []}
        cr = _build_condition_report("A", "t", data)
        assert cr.total_questions == 0
        assert cr.mean_recall == 0.0


class TestScoreCat2c:
    def test_graph_only(self, tmp_path):
        graph = _write_retrieve_json(
            tmp_path, "B", _make_questions([(0, 0.8, 100), (1, 0.6, 200)])
        )
        report = score_cat2c(graph_json=graph)
        assert "B" in report.conditions
        assert report.conditions["B"].total_questions == 2
        assert report.verdict == "incomplete"

    def test_graph_json_required(self, tmp_path):
        with pytest.raises(ValueError, match="required"):
            score_cat2c(graph_json=None)

    def test_two_conditions_delta(self, tmp_path):
        flat = _write_retrieve_json(
            tmp_path, "A", _make_questions([(0, 0.4, 100), (1, 0.2, 200)])
        )
        graph = _write_retrieve_json(
            tmp_path, "B", _make_questions([(0, 0.8, 150), (1, 0.7, 250)])
        )
        report = score_cat2c(flat_json=flat, graph_json=graph)
        assert 0 in report.delta_B_minus_A
        assert report.delta_B_minus_A[0]["recall_delta_pp"] == pytest.approx(40.0)
        assert report.ratio_B_over_A[0] == pytest.approx(2.0)

    def test_three_conditions_full(self, tmp_path):
        flat = _write_retrieve_json(
            tmp_path, "A", _make_questions([(0, 0.3, 100)])
        )
        graph = _write_retrieve_json(
            tmp_path, "B", _make_questions([(0, 0.9, 150)])
        )
        no_struct = _write_retrieve_json(
            tmp_path, "C", _make_questions([(0, 0.5, 120)])
        )
        report = score_cat2c(
            flat_json=flat, graph_json=graph, no_structure_json=no_struct
        )
        assert "A" in report.conditions
        assert "C" in report.conditions
        assert 0 in report.delta_B_minus_C
        assert report.delta_B_minus_C[0]["recall_delta_pp"] == pytest.approx(40.0)


class TestVerdict:
    def test_structure_earns_complexity(self, tmp_path):
        flat = _write_retrieve_json(tmp_path, "A", _make_questions([
            (0, 0.5, 100), (0, 0.5, 100),
            (1, 0.3, 200), (1, 0.3, 200),
            (2, 0.1, 300), (2, 0.1, 300),
        ]))
        graph = _write_retrieve_json(tmp_path, "B", _make_questions([
            (0, 0.6, 100), (0, 0.6, 100),
            (1, 0.7, 200), (1, 0.7, 200),
            (2, 0.8, 300), (2, 0.8, 300),
        ]))
        report = score_cat2c(flat_json=flat, graph_json=graph)
        assert "scales with depth" in report.verdict

    def test_structure_harmful(self, tmp_path):
        flat = _write_retrieve_json(tmp_path, "A", _make_questions([
            (0, 0.8, 100), (1, 0.8, 200),
        ]))
        graph = _write_retrieve_json(tmp_path, "B", _make_questions([
            (0, 0.2, 100), (1, 0.2, 200),
        ]))
        report = score_cat2c(flat_json=flat, graph_json=graph)
        assert "harmful" in report.verdict

    def test_neutral_tax(self, tmp_path):
        flat = _write_retrieve_json(tmp_path, "A", _make_questions([
            (0, 0.5, 100), (1, 0.5, 200),
        ]))
        graph = _write_retrieve_json(tmp_path, "B", _make_questions([
            (0, 0.5, 100), (1, 0.5, 200),
        ]))
        report = score_cat2c(flat_json=flat, graph_json=graph)
        assert "neutral" in report.verdict


class TestToDict:
    def test_roundtrip_serializable(self, tmp_path):
        graph = _write_retrieve_json(
            tmp_path, "B", _make_questions([(0, 0.8, 100)])
        )
        report = score_cat2c(graph_json=graph)
        d = report.to_dict()
        json.dumps(d)


class TestFormatReport:
    def test_format_does_not_crash(self, tmp_path):
        flat = _write_retrieve_json(tmp_path, "A", _make_questions([(0, 0.5, 100)]))
        graph = _write_retrieve_json(tmp_path, "B", _make_questions([(0, 0.8, 150)]))
        report = score_cat2c(flat_json=flat, graph_json=graph)
        text = format_report(report)
        assert "Category 2c" in text
        assert "VERDICT" in text
