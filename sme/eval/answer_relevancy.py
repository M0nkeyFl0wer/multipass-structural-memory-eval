"""Answer relevancy rubric: does the answer address the question?

An LLM-judge overlay for the RAG Triad that scores how directly the
answer addresses the user's question.
"""

from __future__ import annotations

from typing import Any, Optional

from sme.eval.judge_base import RubricJudge


def grade_relevancy(
    question: str,
    answer: str,
    *,
    provider: str = "openai",
    judge_model: Optional[str] = None,
    client: Optional[Any] = None,
) -> dict:
    """Grade how directly the answer addresses the question.

    Returns:
        {
            "score": float,  # 0.0-1.0
            "rationale": str,
            "usage": dict,
            "error": str | None,
        }
    """
    rubric = (
        "Rate how directly the ANSWER addresses the QUESTION.\n"
        "- 1.0: fully addresses all aspects\n"
        "- 0.5: partially addresses, misses sub-questions\n"
        "- 0.0: irrelevant or incorrectly refuses\n"
        'Reply as JSON: {"score": 0.0-1.0, "rationale": "<one sentence>"}'
    )

    body = f"QUESTION:\n{question}\n\nANSWER:\n{answer}"

    judge = RubricJudge(provider=provider, model=judge_model, client=client)
    result = judge.judge(rubric, body)

    if result.get("error"):
        return {
            "score": 0.0,
            "rationale": "",
            "usage": result.get("usage", {}),
            "error": result["error"],
        }

    parsed = RubricJudge.parse_reply(result.get("content", ""))
    if parsed is None or not isinstance(parsed, dict):
        return {
            "score": 0.0,
            "rationale": "",
            "usage": result.get("usage", {}),
            "error": "Failed to parse judge response as JSON",
        }

    score = parsed.get("score", 0.0)
    if not isinstance(score, (int, float)):
        score = 0.0

    score = max(0.0, min(1.0, float(score)))

    rationale = str(parsed.get("rationale", ""))

    return {
        "score": score,
        "rationale": rationale,
        "usage": result.get("usage", {}),
        "error": None,
    }
