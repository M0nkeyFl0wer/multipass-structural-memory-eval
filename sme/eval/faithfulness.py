"""Faithfulness rubric: are answer claims supported by context?

An LLM-judge overlay for the RAG Triad that scores how many of the
answer's factual claims are supported by the provided context.
"""

from __future__ import annotations

from typing import Any, Optional

from sme.eval.judge_base import RubricJudge


def grade_faithfulness(
    context_string: str,
    answer: str,
    *,
    provider: str = "openai",
    judge_model: Optional[str] = None,
    client: Optional[Any] = None,
    use_cache: bool = True,
) -> dict:
    """Grade whether the answer's claims are supported by the context.

    Returns:
        {
            "score": float,  # fraction of claims supported (0.0-1.0)
            "claims": [{"text": str, "verdict": "SUPPORTED|CONTRADICTED|UNSUPPORTED"}],
            "rationale": str,
            "usage": dict,
            "error": str | None,
        }
    """
    rubric = (
        "You are a fact-checker. Given the CONTEXT and the ANSWER, list each "
        "factual claim in the answer. For each claim, mark it:\n"
        "  - SUPPORTED: directly found in or entailed by the context\n"
        "  - CONTRADICTED: the context says the opposite\n"
        "  - UNSUPPORTED: not in context\n\n"
        "Claim segmentation rules:\n"
        "  - Split compound sentences into separate claims.\n"
        "    'Paris is the capital of France and has 2.1M people' → 2 claims\n"
        "  - Do NOT split clauses that share a single subject.\n"
        "    'The quick brown fox jumps over the lazy dog' → 1 claim\n"
        "  - 'Entailed by context' means the context makes the claim obviously true, "
        "    not that the claim uses the exact same words.\n\n"
        "Examples:\n"
        "  CONTEXT: Python was created by Guido van Rossum.\n"
        "  ANSWER: Python was created by Guido van Rossum and is popular.\n"
        '  → {"claims": [{"text": "Python was created by Guido van Rossum", "verdict": "SUPPORTED"}, '
        '{"text": "Python is popular", "verdict": "UNSUPPORTED"}]}\n\n'
        "  CONTEXT: Paris is the capital of France.\n"
        "  ANSWER: Paris is the capital of Germany.\n"
        '  → {"claims": [{"text": "Paris is the capital of Germany", "verdict": "CONTRADICTED"}]}\n\n'
        'Reply as JSON: {"claims": [{"text": "...", "verdict": "SUPPORTED|CONTRADICTED|UNSUPPORTED"}]}'
    )

    body = f"CONTEXT:\n{context_string}\n\nANSWER:\n{answer}"

    judge = RubricJudge(provider=provider, model=judge_model, client=client)
    result = judge.judge(rubric, body, use_cache=use_cache)

    if result.get("error"):
        return {
            "score": 0.0,
            "claims": [],
            "rationale": "",
            "usage": result.get("usage", {}),
            "error": result["error"],
        }

    raw_content = result.get("content", "")
    parsed = RubricJudge.parse_reply(raw_content)
    if parsed is None or not isinstance(parsed, dict):
        snippet = raw_content[:200] if raw_content else "<empty>"
        return {
            "score": 0.0,
            "claims": [],
            "rationale": "",
            "usage": result.get("usage", {}),
            "error": f"Failed to parse judge response as JSON: {snippet!r}",
        }

    claims = parsed.get("claims", [])
    if not isinstance(claims, list) or not claims:
        return {
            "score": 0.0,
            "claims": [],
            "rationale": "",
            "usage": result.get("usage", {}),
            "error": None,
        }

    supported_count = sum(
        1
        for c in claims
        if isinstance(c, dict) and c.get("verdict") == "SUPPORTED"
    )
    total_claims = len(claims)
    score = supported_count / total_claims if total_claims > 0 else 0.0

    rationale_parts = []
    for c in claims:
        if isinstance(c, dict):
            text = c.get("text", "")
            verdict = c.get("verdict", "UNKNOWN")
            rationale_parts.append(f"{verdict}: {text}")
    rationale = "\n".join(rationale_parts)

    return {
        "score": score,
        "claims": claims,
        "rationale": rationale,
        "usage": result.get("usage", {}),
        "error": None,
    }
