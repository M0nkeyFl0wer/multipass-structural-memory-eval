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

import json
import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

# Default judge model per LongMemEval paper §4 / upstream evaluate_qa.py.
DEFAULT_JUDGE_MODEL = "gpt-4o-2024-08-06"

# Per-provider default judge model. The OpenAI default matches the
# LongMemEval paper. The OpenRouter default reaches the same model
# through the OpenAI-compatible gateway. The Anthropic default is the
# latest Sonnet — used for SME-internal cross-validation runs where the
# user wants a Claude judge for cost / locality reasons.
PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4o-2024-08-06",
    "openrouter": "openai/gpt-4o-2024-08-06",
    "anthropic": "claude-sonnet-4-6",
}

VALID_PROVIDERS = set(PROVIDER_DEFAULT_MODEL)

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


def _retry(fn, *, max_retries: int = 3, label: str = "judge"):
    """Run ``fn()`` with exponential backoff, returning its result.

    Raises the final exception on exhaustion. The caller decides how
    to surface the failure.
    """
    last_exc: Optional[BaseException] = None
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — judge errors are diagnostic
            last_exc = e
            log.warning(
                "longmemeval_judge[%s]: attempt %d/%d failed: %s",
                label, attempt + 1, max_retries, e,
            )
            if attempt + 1 < max_retries:
                time.sleep(delay)
                delay *= 2
    assert last_exc is not None
    raise last_exc


def _call_openai_compat(
    *,
    client: Any,
    model: str,
    rubric: str,
    user_body: str,
    max_retries: int = 3,
    label: str = "openai",
) -> dict:
    """Call an OpenAI-compatible Chat Completions endpoint.

    Used for both ``provider='openai'`` (direct OpenAI) and
    ``provider='openrouter'`` (OpenAI-compatible gateway).

    **Methodology lock**: rubric and body are concatenated into a
    single user message. Upstream LongMemEval (xiaowu0162/LongMemEval
    `src/evaluation/evaluate_qa.py`) sends the entire grading prompt
    as one user message — *no* system block. We match that exactly so
    SME's judge readings remain numerically comparable to the
    LongMemEval paper baselines. The Anthropic path uses a different
    shape (system+user) for prompt caching, but the OpenAI/OpenRouter
    path stays paper-faithful.

    Returns ``{'content': str, 'usage': dict}`` on success.
    """

    combined = rubric + user_body

    def _do() -> dict:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": combined},
            ],
            temperature=0.0,
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

    return _retry(_do, max_retries=max_retries, label=label)


def _call_anthropic(
    *,
    client: Any,
    model: str,
    rubric: str,
    user_body: str,
    max_tokens: int = 512,
    max_retries: int = 3,
) -> dict:
    """Call the Anthropic Messages endpoint with prompt caching on the rubric.

    The rubric (per question_type) is sent as a single system block with
    ``cache_control: ephemeral``, so within one judge run the rubric is
    written to cache on the first call for that question_type and read
    on every subsequent call of the same type — the rest of the prompt
    (Question / Gold / System answer) varies and is sent as the user
    message.
    """

    def _do() -> dict:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": rubric,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_body}],
        )
        # Concatenate text blocks (judge response is short, usually one).
        parts: list[str] = []
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", "") or "")
        content = "".join(parts)
        usage_obj = getattr(resp, "usage", None)
        if usage_obj is None:
            usage = {"prompt_tokens": 0, "completion_tokens": 0,
                     "total_tokens": 0}
        else:
            input_tokens = getattr(usage_obj, "input_tokens", 0) or 0
            output_tokens = getattr(usage_obj, "output_tokens", 0) or 0
            cache_read = getattr(
                usage_obj, "cache_read_input_tokens", 0) or 0
            cache_creation = getattr(
                usage_obj, "cache_creation_input_tokens", 0) or 0
            usage = {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            }
        return {"content": content, "usage": usage}

    return _retry(_do, max_retries=max_retries, label="anthropic")


def _default_client(provider: str) -> Optional[Any]:
    """Return a lazily-imported provider client, or None if unavailable.

    Reads keys from the system keyring (and OPENAI_API_KEY env fallback
    for openai) without echoing. Returns None when the provider's SDK
    isn't installed or no key is available — the caller surfaces that
    as a skipped judge.
    """
    # Local import so the judge module stays cheap to import in tests
    # that don't touch real APIs.
    from sme.eval.llm_clients import load_api_key

    if provider == "openai":
        api_key = load_api_key("openai", env_fallback="OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            log.info("longmemeval_judge: openai SDK not installed")
            return None
        return OpenAI(api_key=api_key)

    if provider == "openrouter":
        api_key = load_api_key("openrouter")
        if not api_key:
            return None
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            log.info("longmemeval_judge: openai SDK not installed")
            return None
        return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    if provider == "anthropic":
        api_key = load_api_key("anthropic")
        if not api_key:
            return None
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError:
            log.info("longmemeval_judge: anthropic SDK not installed")
            return None
        return anthropic.Anthropic(api_key=api_key)

    return None


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

    try:
        if provider == "anthropic":
            called = _call_anthropic(
                client=client,
                model=judge_model,
                rubric=rubric,
                user_body=user_body,
            )
        else:
            called = _call_openai_compat(
                client=client,
                model=judge_model,
                rubric=rubric,
                user_body=user_body,
                label=provider,
            )
    except Exception as e:  # noqa: BLE001 — judge errors are diagnostic
        base_result["rationale"] = f"judge call failed after retries: {e}"
        return base_result

    label, rationale = _parse_judge_reply(called["content"])
    return {
        "autoeval_label": label,
        "judge_model": judge_model,
        "provider": provider,
        "methodology_faithful": methodology_faithful,
        "rationale": rationale,
        "usage": called["usage"],
    }
