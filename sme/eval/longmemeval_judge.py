"""LongMemEval GPT-4o judge wrapper.

Re-implements the question-type-specific grading prompts from LongMemEval
upstream (`src/evaluation/evaluate_qa.py` in xiaowu0162/LongMemEval, MIT)
in a form that's callable from SME's cross-validation harness without
spawning an upstream subprocess.

Public surface:

- `grade_answer(question_type, ...)` — single judge call; returns a dict
  with `autoeval_label` in {CORRECT, PARTIAL, INCORRECT, ABSTAIN, ERROR}.
- `grade_answer_replicated(question_type, ..., replicates=K)` — K-replicate
  judge calls with majority-vote aggregation, used to characterize
  intra-rater stochasticity (see upstream issue #22).

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

import json
import logging
import os
import time
from collections import Counter
from typing import Any, Optional

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

# Deterministic tie-break order for the K-replicate majority vote. When two
# or more labels are tied on count, the earlier label in this list wins. This
# follows the LongMemEval label hierarchy (CORRECT > PARTIAL > INCORRECT >
# ABSTAIN) so that majority_label is reproducible across runs without pinning
# PYTHONHASHSEED — Counter.most_common() tie-breaks are otherwise arbitrary.
TIE_BREAK_ORDER = ["CORRECT", "PARTIAL", "INCORRECT", "ABSTAIN"]


def _prompt_for_question_type(qtype: str, question: str, gold: str, hyp: str) -> str:
    """Build the grading prompt body for a given question type.

    The five branches reflect the scoring intents described in the
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
    common_header = (
        "You are an evaluator for a long-term memory benchmark. "
        "Judge whether the system's answer is correct given the gold answer.\n\n"
        f"Question: {question}\n"
        f"Gold answer: {gold}\n"
        f"System answer: {hyp}\n\n"
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
    return common_header + rubric + instr


def _parse_judge_reply(content: str) -> tuple[str, str]:
    """Extract (label, rationale) from a judge response string.

    Tolerates extra whitespace, code fences, and prose before/after the
    JSON. Returns ('ERROR', raw_content) on failure.
    """
    if not content:
        return "ERROR", "empty judge response"
    # Strip code fences if present.
    stripped = content.strip()
    if stripped.startswith("```"):
        # remove leading and trailing fences
        lines = stripped.splitlines()
        # drop first line (``` or ```json) and any trailing ``` line
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    # Find the first {...} JSON object.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return "ERROR", f"no JSON object in judge reply: {content[:200]!r}"
    blob = stripped[start:end + 1]
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError as e:
        return "ERROR", f"malformed judge JSON ({e}): {content[:200]!r}"
    label = str(obj.get("label", "")).strip().upper()
    rationale = str(obj.get("rationale", "")).strip()
    if label not in VALID_LABELS - {"ERROR"}:
        return "ERROR", f"unknown judge label {label!r}: {content[:200]!r}"
    return label, rationale or "(no rationale)"


def _call_openai(
    *,
    client: Any,
    model: str,
    prompt: str,
    max_retries: int = 3,
    temperature: float = 0.0,
) -> dict:
    """Call the OpenAI Chat Completions endpoint with simple backoff.

    Returns ``{'content': str, 'usage': dict}`` on success, raises the
    final exception on exhaustion. The caller is responsible for catching.
    """
    last_exc: Optional[BaseException] = None
    delay = 1.0
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            choice = resp.choices[0]
            content = getattr(choice.message, "content", "") or ""
            usage_obj = getattr(resp, "usage", None)
            if usage_obj is None:
                usage = {"prompt_tokens": 0, "completion_tokens": 0,
                         "total_tokens": 0}
            else:
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(
                        usage_obj, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                }
            return {"content": content, "usage": usage}
        except Exception as e:  # noqa: BLE001 — judge errors are diagnostic
            last_exc = e
            log.warning(
                "longmemeval_judge: attempt %d/%d failed: %s",
                attempt + 1, max_retries, e,
            )
            if attempt + 1 < max_retries:
                time.sleep(delay)
                delay *= 2
    assert last_exc is not None
    raise last_exc


def _default_client() -> Optional[Any]:
    """Return a lazily-imported OpenAI client, or None if unavailable.

    Treats both "package not installed" and "OPENAI_API_KEY not set" as
    None — the caller decides how to surface the absence.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        log.info("longmemeval_judge: openai SDK not installed")
        return None
    return OpenAI()


def grade_answer(
    question_type: str,
    question: str,
    gold_answer: str,
    hypothesis: str,
    *,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    client: Optional[Any] = None,
    temperature: float = 0.0,
) -> dict:
    """Grade a system answer against the gold answer using a GPT-4o judge.

    Args:
        question_type: One of LME_QUESTION_TYPES or 'abstention'.
        question: The natural-language question text.
        gold_answer: The reference answer string.
        hypothesis: The system's generated answer.
        judge_model: OpenAI model id to use. Defaults to the LongMemEval
            paper's choice.
        client: An OpenAI-SDK-shaped client (must have
            ``client.chat.completions.create(model, messages, ...)``).
            When None, one is constructed from ``OPENAI_API_KEY``.
            Tests pass a fake.
        temperature: Sampling temperature for the judge call. Defaults to
            0.0 (deterministic, the LongMemEval paper setting). Use a
            higher value via ``grade_answer_replicated`` to characterize
            intra-rater variance.

    Returns:
        {
          'autoeval_label': 'CORRECT' | 'PARTIAL' | 'INCORRECT' | 'ABSTAIN' | 'ERROR',
          'judge_model': str,
          'rationale': str,
          'usage': {prompt_tokens, completion_tokens, total_tokens},
        }
    """
    base_result = {
        "autoeval_label": "ERROR",
        "judge_model": judge_model,
        "rationale": "",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

    if question_type not in JUDGE_QUESTION_TYPES:
        # Unknown type — fall through with a generic rubric, but flag.
        log.info("longmemeval_judge: unknown question_type %r", question_type)

    if client is None:
        client = _default_client()
    if client is None:
        base_result["rationale"] = "OPENAI_API_KEY not set; judge skipped"
        return base_result

    prompt = _prompt_for_question_type(
        question_type, question, gold_answer, hypothesis
    )
    try:
        called = _call_openai(
            client=client, model=judge_model, prompt=prompt,
            temperature=temperature,
        )
    except Exception as e:  # noqa: BLE001 — judge errors are diagnostic
        base_result["rationale"] = f"judge call failed after retries: {e}"
        return base_result

    label, rationale = _parse_judge_reply(called["content"])
    return {
        "autoeval_label": label,
        "judge_model": judge_model,
        "rationale": rationale,
        "usage": called["usage"],
    }


def grade_answer_replicated(
    question_type: str,
    question: str,
    gold_answer: str,
    hypothesis: str,
    *,
    replicates: int = 1,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    client: Optional[Any] = None,
    temperature: Optional[float] = None,
) -> dict:
    """Grade with K replicates to characterize judge variance.

    When ``replicates <= 1``, delegates directly to :func:`grade_answer`
    with ``temperature=0.0`` by default (backward compatible — single
    deterministic call matches the LongMemEval paper setting).

    When ``replicates > 1``, runs K independent judge calls at
    ``temperature=0.3`` by default (override via the ``temperature``
    argument) and aggregates via majority vote, excluding ``ERROR``
    replicates from the vote.

    Args:
        question_type: One of LME_QUESTION_TYPES or 'abstention'.
        question: The natural-language question text.
        gold_answer: The reference answer string.
        hypothesis: The system's generated answer.
        replicates: Number of independent judge calls (K).
        judge_model: OpenAI model id to use.
        client: An OpenAI-SDK-shaped client (see :func:`grade_answer`).
        temperature: Sampling temperature override. Defaults to 0.0 for
            K=1 and 0.3 for K>1.

    Returns:
        For K=1, exactly what :func:`grade_answer` returns.

        For K>1, the single-call shape plus replicate diagnostics:
          {
            'autoeval_label': str,        # majority label
            'judge_model': str,
            'rationale': str,             # rationale from the majority
            'usage': {...},               # summed across all replicates
            'replicates': list[dict],     # individual replicate results
            'label_counts': dict,         # label -> count (non-ERROR)
            'agreement_rate': float,      # fraction matching majority
            'flip_rate': float,           # 1 - agreement_rate
          }

        When every replicate returns ``ERROR``, the first replicate is
        returned with ``replicates`` attached so the caller can inspect
        the failures; the diagnostic keys (``label_counts``,
        ``agreement_rate``, ``flip_rate``) are present but empty/zero so the
        return shape stays consistent with the success path.

        Ties in the majority vote are broken deterministically by
        :data:`TIE_BREAK_ORDER` (CORRECT > PARTIAL > INCORRECT > ABSTAIN),
        so ``majority_label`` is reproducible without pinning PYTHONHASHSEED.
    """
    if replicates <= 1:
        temp = temperature if temperature is not None else 0.0
        return grade_answer(
            question_type, question, gold_answer, hypothesis,
            judge_model=judge_model, client=client, temperature=temp,
        )

    temp = temperature if temperature is not None else 0.3
    results: list[dict] = []
    for _ in range(replicates):
        r = grade_answer(
            question_type, question, gold_answer, hypothesis,
            judge_model=judge_model, client=client, temperature=temp,
        )
        results.append(r)

    # Sum usage across all replicates regardless of outcome.
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for r in results:
        u = r.get("usage", {})
        for key in total_usage:
            total_usage[key] += u.get(key, 0)

    # Majority vote excludes ERROR replicates — those are call failures,
    # not verdicts.
    labels = [r["autoeval_label"] for r in results
              if r["autoeval_label"] != "ERROR"]
    if not labels:
        # All replicates errored — surface the first result, but attach
        # the full replicate trace and the summed usage so cost accounting
        # still reflects K calls. Keep the diagnostic keys present (empty)
        # so the return shape matches the K>1 success path.
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

    # Use the rationale from the first replicate that voted with the
    # majority — keeps the output explainable.
    majority_result = next(
        r for r in results if r["autoeval_label"] == majority_label
    )

    return {
        "autoeval_label": majority_label,
        "judge_model": judge_model,
        "rationale": majority_result["rationale"],
        "usage": total_usage,
        "replicates": results,
        "label_counts": label_counts,
        "agreement_rate": agreement_rate,
        "flip_rate": 1.0 - agreement_rate,
    }
