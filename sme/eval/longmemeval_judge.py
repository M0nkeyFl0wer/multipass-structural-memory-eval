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
from collections import Counter
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

# Deterministic tie-break order for the K-replicate majority vote. When
# two or more labels tie on count, the earlier label here wins. Follows
# the LongMemEval label hierarchy (CORRECT > PARTIAL > INCORRECT >
# ABSTAIN) so majority_label is reproducible without pinning
# PYTHONHASHSEED — Counter.most_common() tie-breaks are otherwise
# arbitrary. (Originally PR #35; preserved verbatim across the
# RubricJudge refactor.)
TIE_BREAK_ORDER = ["CORRECT", "PARTIAL", "INCORRECT", "ABSTAIN"]


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
    use_cache: bool = True,
    temperature: float = 0.0,
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

    judge = RubricJudge(
        provider=provider, model=judge_model, client=client,
        temperature=temperature,
    )
    result = judge.judge(rubric, user_body, use_cache=use_cache)

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


def grade_answer_replicated(
    question_type: str,
    question: str,
    gold_answer: str,
    hypothesis: str,
    *,
    replicates: int = 1,
    provider: str = "openai",
    judge_model: Optional[str] = None,
    client: Optional[Any] = None,
    temperature: Optional[float] = None,
    use_cache: bool = True,
) -> dict:
    """Grade with K replicates to characterize judge variance.

    Originally PR #35 (jphein); ported onto the RubricJudge refactor.
    The replicate sampling now flows through ``grade_answer``'s
    ``temperature`` argument, and each replicate runs with
    ``use_cache=False`` so the disk cache can't collapse the variance
    being measured (RubricJudge also force-disables caching whenever
    temperature > 0, as a second guard).

    When ``replicates <= 1``, delegates to :func:`grade_answer` at
    ``temperature=0.0`` (backward compatible — a single deterministic
    call matching the LongMemEval paper setting).

    When ``replicates > 1``, runs K independent judge calls at
    ``temperature=0.3`` by default (override via ``temperature``) and
    aggregates via majority vote, excluding ``ERROR`` replicates.

    Args:
        replicates: Number of independent judge calls (K).
        provider: 'openai' | 'openrouter' | 'anthropic' (see grade_answer).
        judge_model: Model id; None resolves the provider default.
        client: A pre-built provider-shaped client (tests pass a fake).
        temperature: Sampling override. Defaults to 0.0 for K=1, 0.3 for K>1.

    Returns:
        For K=1, exactly what :func:`grade_answer` returns.

        For K>1, the single-call shape plus replicate diagnostics::

          {
            'autoeval_label': str,      # majority label
            'judge_model': str,
            'provider': str,
            'rationale': str,           # rationale from a majority voter
            'usage': {...},             # summed across all replicates
            'replicates': list[dict],   # individual replicate results
            'label_counts': dict,       # label -> count (non-ERROR)
            'agreement_rate': float,    # fraction matching majority
            'flip_rate': float,         # 1 - agreement_rate
          }

        When every replicate returns ``ERROR``, the first replicate is
        returned with ``replicates`` attached and the diagnostic keys
        present but empty/zero, so the return shape stays consistent.

        Ties are broken deterministically by :data:`TIE_BREAK_ORDER`
        (CORRECT > PARTIAL > INCORRECT > ABSTAIN), so ``majority_label``
        is reproducible without pinning PYTHONHASHSEED.
    """
    if replicates <= 1:
        temp = temperature if temperature is not None else 0.0
        return grade_answer(
            question_type, question, gold_answer, hypothesis,
            provider=provider, judge_model=judge_model, client=client,
            temperature=temp, use_cache=use_cache,
        )

    temp = temperature if temperature is not None else 0.3
    results: list[dict] = []
    for _ in range(replicates):
        r = grade_answer(
            question_type, question, gold_answer, hypothesis,
            provider=provider, judge_model=judge_model, client=client,
            temperature=temp, use_cache=False,
        )
        results.append(r)

    # Sum usage across all replicates regardless of outcome.
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for r in results:
        u = r.get("usage", {})
        for key in total_usage:
            total_usage[key] += u.get(key, 0)

    resolved_model = results[0].get("judge_model", judge_model)

    # Majority vote excludes ERROR replicates — those are call failures,
    # not verdicts.
    labels = [r["autoeval_label"] for r in results
              if r["autoeval_label"] != "ERROR"]
    if not labels:
        # All replicates errored — surface the first result, attach the
        # full replicate trace and summed usage so cost accounting still
        # reflects K calls. Keep the diagnostic keys present (empty) so
        # the return shape matches the K>1 success path.
        first = dict(results[0])
        first["usage"] = total_usage
        first["replicates"] = results
        first["label_counts"] = {}
        first["agreement_rate"] = 0.0
        first["flip_rate"] = 1.0
        return first

    counter = Counter(labels)
    label_counts = dict(counter.most_common())
    # Deterministic majority: highest count, ties broken by TIE_BREAK_ORDER.
    # Unknown labels (shouldn't occur given VALID_LABELS) sort last.
    majority_label = max(
        counter,
        key=lambda lbl: (
            counter[lbl],
            -(TIE_BREAK_ORDER.index(lbl) if lbl in TIE_BREAK_ORDER
              else len(TIE_BREAK_ORDER)),
        ),
    )
    agreement_count = label_counts[majority_label]
    agreement_rate = agreement_count / len(labels)

    # Rationale from the first replicate that voted with the majority —
    # keeps the output explainable.
    majority_result = next(
        r for r in results if r["autoeval_label"] == majority_label
    )

    return {
        "autoeval_label": majority_label,
        "judge_model": resolved_model,
        "provider": provider,
        "rationale": majority_result["rationale"],
        "usage": total_usage,
        "replicates": results,
        "label_counts": label_counts,
        "agreement_rate": agreement_rate,
        "flip_rate": 1.0 - agreement_rate,
    }
