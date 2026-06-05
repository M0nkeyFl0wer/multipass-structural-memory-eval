"""LongMemEval GPT-4o judge wrapper.

Re-implements the question-type-specific grading prompts from LongMemEval
upstream (`src/evaluation/evaluate_qa.py` in xiaowu0162/LongMemEval, MIT)
in a form that's callable from SME's cross-validation harness without
spawning an upstream subprocess.

Public surface is the single function `grade_answer(question_type, ...)`
which returns a dict with `autoeval_label` in
{CORRECT, PARTIAL, INCORRECT, ABSTAIN, ERROR}.

Design notes:

- Prompts mirror the upstream methodology described in arXiv 2410.10813
  §4 ("LLM-Judge Evaluation") and the `evaluate_qa.py` source. They are
  paraphrased rather than copied verbatim — primary-source verification
  was not available in this session, so the prompts here aim for the
  *same scoring intent* (factual / synthesis / current-value / temporal
  / abstention) rather than identical wording. See the ``Open questions``
  section in ``docs/related_work/longmemeval.md``.
- The wrapper uses the ``openai`` SDK if installed; otherwise it falls
  back to a stdlib HTTP POST against the public OpenAI Chat Completions
  endpoint. Tests mock the call entirely, so neither path needs to be
  reachable in CI.
- All failure modes return ``autoeval_label='ERROR'`` rather than
  raising, so the harness can keep running across a 500-question batch
  even when individual judge calls misbehave.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sme.eval.judge_base import (
    PROVIDER_DEFAULT_MODEL,
    RubricJudge,
    VALID_PROVIDERS,
    _default_client,
)

log = logging.getLogger(__name__)

# Default judge model per LongMemEval paper §4 / upstream evaluate_qa.py.
DEFAULT_JUDGE_MODEL = "gpt-4o-2024-08-06"

# Question types that the judge handles. Mirrors LME_QUESTION_TYPES from
# the loader plus the `abstention` pseudo-type used for `_abs` records.
JUDGE_QUESTION_TYPES = {
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "knowledge-update",
    "temporal-reasoning",
    "abstention",
}

# Valid labels the upstream judge emits. ERROR is SME-internal — used
# when the call itself fails, distinct from an INCORRECT verdict.
VALID_LABELS = {"CORRECT", "PARTIAL", "INCORRECT", "ABSTAIN", "ERROR"}


def _rubric_for_question_type(qtype: str) -> str:
    """Build the static (cacheable) rubric for a given question type.

    Same content as the previous monolithic prompt, just split out so
    it can be sent as a cacheable system prefix on Anthropic. The
    five branches reflect the scoring intents described in the
    LongMemEval paper:

    - IE (single-session-*): strict factual match of the gold fact.
    - MR (multi-session): synthesis-required match — credit a hypothesis
      that aggregates the right pieces even if surface form differs.
    - KU (knowledge-update): grade against the *current* (most recently
      stated) value, not the historical one. NOTE: the SME-side caveat
      (Cat 3 vs KU) is handled at aggregation time, not here.
    - TR (temporal-reasoning): date / order correctness; tolerate minor
      paraphrase but not month/year errors.
    - ABS (abstention): the system should refuse. Reward refusal,
      penalize hallucinated answers.
    """
    header = (
        "You are an evaluator for a long-term memory benchmark. "
        "Judge whether the system's answer is correct given the gold answer.\n\n"
    )
    if qtype in ("single-session-user", "single-session-assistant",
                 "single-session-preference"):
        rubric = (
            "Scoring rubric (Information Extraction):\n"
            "- CORRECT: the system answer states the same specific fact as "
            "the gold answer (paraphrase OK).\n"
            "- PARTIAL: the system answer overlaps with the gold but omits "
            "or fuzzes a key detail.\n"
            "- INCORRECT: the system answer is wrong, missing, or unrelated.\n"
        )
    elif qtype == "multi-session":
        rubric = (
            "Scoring rubric (Multi-Session Reasoning):\n"
            "- CORRECT: the system answer reflects the correct synthesis of "
            "facts spread across multiple sessions.\n"
            "- PARTIAL: the system answer captures part of the synthesis but "
            "misses a contributing session.\n"
            "- INCORRECT: the system answer fails the synthesis (wrong "
            "aggregate or comparison).\n"
        )
    elif qtype == "knowledge-update":
        rubric = (
            "Scoring rubric (Knowledge Update):\n"
            "- CORRECT: the system answer reflects the MOST RECENT stated "
            "value (post-overwrite). Returning an older/superseded value is "
            "INCORRECT even if it was true at one point.\n"
            "- PARTIAL: the system answer mentions both old and new without "
            "clearly committing to the current value.\n"
            "- INCORRECT: the system answer is wrong or stale.\n"
        )
    elif qtype == "temporal-reasoning":
        rubric = (
            "Scoring rubric (Temporal Reasoning):\n"
            "- CORRECT: the system answer states the right time/order "
            "(month/year correct, ordering correct).\n"
            "- PARTIAL: the system answer is in the right ballpark but off "
            "by a small amount or imprecise.\n"
            "- INCORRECT: the system answer has the wrong date or wrong "
            "order.\n"
        )
    elif qtype == "abstention":
        rubric = (
            "Scoring rubric (Abstention):\n"
            "- ABSTAIN: the system correctly refuses to answer or says it "
            "doesn't know. This is the desired outcome.\n"
            "- INCORRECT: the system fabricates an answer to a question "
            "that has no grounding in the conversation history.\n"
            "- CORRECT: the gold answer is itself an explicit refusal AND "
            "the system matches it.\n"
        )
    else:
        rubric = (
            "Scoring rubric (Generic):\n"
            "- CORRECT / PARTIAL / INCORRECT based on factual match to "
            "the gold answer.\n"
        )
    instr = (
        "\nReply with a single JSON object on one line:\n"
        '{"label": "CORRECT|PARTIAL|INCORRECT|ABSTAIN", '
        '"rationale": "<one sentence>"}\n'
    )
    return header + rubric + instr


def _user_body(question: str, gold: str, hyp: str) -> str:
    """The per-call (varying) part of the judge prompt.

    Kept as the standard LongMemEval shape: Question / Gold / System.
    Always returned with the `Question:` marker first so
    ``split_for_caching`` can find it when the rubric and body are
    concatenated for non-caching providers.
    """
    return (
        f"Question: {question}\n"
        f"Gold answer: {gold}\n"
        f"System answer: {hyp}\n"
    )


def _parse_judge_reply(content: str) -> tuple[str, str]:
    """Extract (label, rationale) from a judge response string.

    Tolerates extra whitespace, code fences, and prose before/after the
    JSON. Returns ('ERROR', raw_content) on failure.
    """
    if not content:
        return "ERROR", "empty judge response"
    obj = RubricJudge.parse_reply(content)
    if obj is None:
        return "ERROR", f"no JSON object in judge reply: {content[:200]!r}"
    label = str(obj.get("label", "")).strip().upper()
    rationale = str(obj.get("rationale", "")).strip()
    if label not in VALID_LABELS - {"ERROR"}:
        return "ERROR", f"unknown judge label {label!r}: {content[:200]!r}"
    return label, rationale or "(no rationale)"


def grade_answer(
    question_type: str,
    question: str,
    gold_answer: str,
    hypothesis: str,
    *,
    provider: str = "openai",
    judge_model: Optional[str] = None,
    client: Optional[Any] = None,
) -> dict:
    """Grade a system answer against the gold answer with an LLM judge.

    Args:
        question_type: One of LME_QUESTION_TYPES or 'abstention'.
        question: The natural-language question text.
        gold_answer: The reference answer string.
        hypothesis: The system's generated answer.
        provider: 'openai' (default — direct OpenAI), 'openrouter'
            (OpenAI-compatible gateway, used to reach gpt-4o without an
            OpenAI account), or 'anthropic' (uses prompt caching on the
            rubric across calls of the same question_type).
        judge_model: Model id. When None, the provider's default is
            used (gpt-4o-2024-08-06 for openai, openai/gpt-4o-2024-08-06
            for openrouter, claude-sonnet-4-6 for anthropic).
        client: A pre-built provider-shaped client. When None, one is
            constructed lazily from the keyring. Tests pass a fake.

    Returns:
        {
          'autoeval_label': 'CORRECT' | 'PARTIAL' | 'INCORRECT' | 'ABSTAIN' | 'ERROR',
          'judge_model': str,
          'provider': str,
          'methodology_faithful': bool,
          'rationale': str,
          'usage': {prompt_tokens, completion_tokens, total_tokens, ...},
        }
    """
    if provider not in VALID_PROVIDERS:
        return {
            "autoeval_label": "ERROR",
            "judge_model": judge_model or "?",
            "provider": provider,
            "methodology_faithful": False,
            "rationale": (
                f"unknown provider {provider!r}; "
                f"supported: {sorted(VALID_PROVIDERS)}"
            ),
            "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                      "total_tokens": 0},
        }

    if judge_model is None:
        judge_model = PROVIDER_DEFAULT_MODEL[provider]

    # methodology_faithful is True only when the call exactly matches
    # the LongMemEval paper's grading procedure: model id
    # `gpt-4o-2024-08-06`, single-user-message prompt shape, no
    # system block. The Anthropic path is intentionally a different
    # shape (system+user, with prompt caching) — useful for SME-
    # internal cross-validation but not paper-faithful, so its
    # judge readings should be reported separately and not mixed into
    # comparisons against published LongMemEval numbers.
    is_paper_judge_model = judge_model in (
        "gpt-4o-2024-08-06",
        "openai/gpt-4o-2024-08-06",
    )
    methodology_faithful = (
        provider in ("openai", "openrouter") and is_paper_judge_model
    )

    base_result = {
        "autoeval_label": "ERROR",
        "judge_model": judge_model,
        "provider": provider,
        "methodology_faithful": methodology_faithful,
        "rationale": "",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

    if question_type not in JUDGE_QUESTION_TYPES:
        # Unknown type — fall through with a generic rubric, but flag.
        log.info("longmemeval_judge: unknown question_type %r", question_type)

    if client is None:
        client = _default_client(provider)
    if client is None:
        base_result["rationale"] = (
            f"no API key in keyring for service={provider}; judge skipped"
        )
        return base_result

    rubric = _rubric_for_question_type(question_type)
    user_body = _user_body(question, gold_answer, hypothesis)

    judge = RubricJudge(provider=provider, model=judge_model, client=client)
    result = judge.judge(rubric, user_body)

    if result["error"]:
        base_result["rationale"] = result["error"]
        return base_result

    label, rationale = _parse_judge_reply(result["content"])
    return {
        "autoeval_label": label,
        "judge_model": judge_model,
        "provider": provider,
        "methodology_faithful": methodology_faithful,
        "rationale": rationale,
        "usage": result["usage"],
    }
