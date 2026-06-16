"""Calibration tests for the faithfulness rubric.

These tests call a real LLM judge and assert that scores fall within ±0.2
of the hand-crafted expected values. Marked ``slow`` so CI can skip them.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from sme.eval.faithfulness import grade_faithfulness
from sme.eval.judge_base import RubricJudge


@pytest.mark.slow
def test_faithfulness_calibration_examples():
    probe = RubricJudge(provider="openai")
    if probe._resolve_client() is None:
        pytest.skip("No API client available for calibration tests")

    fixture_path = (
        pathlib.Path(__file__).parent
        / "fixtures"
        / "calibration"
        / "faithfulness_examples.json"
    )
    examples = json.loads(fixture_path.read_text())
    for ex in examples:
        result = grade_faithfulness(
            context_string=ex["context"],
            answer=ex["answer"],
        )
        expected = ex["expected_score"]
        actual = result["score"]
        assert abs(actual - expected) <= 0.2, (
            f"Example '{ex['description']}' expected ~{expected}, got {actual}. "
            f"Rationale: {result.get('rationale', '')}"
        )
