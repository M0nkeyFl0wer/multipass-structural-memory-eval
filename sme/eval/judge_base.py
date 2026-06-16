"""Generic LLM rubric judge infrastructure.

Extracted from ``longmemeval_judge.py`` so future rubrics can reuse the
provider calling, retry, and JSON-parsing plumbing without inheriting
LongMemEval-specific prompt construction.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

# Per-provider default judge model.
PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4o-2024-08-06",
    "openrouter": "openai/gpt-4o-2024-08-06",
    "anthropic": "claude-sonnet-4-6",
}

VALID_PROVIDERS = set(PROVIDER_DEFAULT_MODEL)

# Lazily-built tuple of exception types that justify a retry.
_RETRYABLE_TYPES: tuple[type[BaseException], ...] | None = None


def _retryable_types() -> tuple[type[BaseException], ...]:
    """Return exception types that indicate a transient failure.

    Includes standard network errors plus SDK-specific API errors.
    Non-retryable exceptions (ValueError, TypeError, AssertionError,
    etc.) are NOT in this list so bugs surface immediately.
    """
    global _RETRYABLE_TYPES
    if _RETRYABLE_TYPES is not None:
        return _RETRYABLE_TYPES

    types: list[type[BaseException]] = [ConnectionError, TimeoutError]
    try:
        import openai  # type: ignore[import-not-found]

        types.extend([
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.InternalServerError,
        ])
    except ImportError:
        pass
    try:
        import anthropic  # type: ignore[import-not-found]

        types.extend([
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
        ])
    except ImportError:
        pass
    _RETRYABLE_TYPES = tuple(types)
    return _RETRYABLE_TYPES


def _default_client(provider: str) -> Optional[Any]:
    """Return a lazily-imported provider client, or None if unavailable.

    Reads keys from the system keyring (and OPENAI_API_KEY env fallback
    for openai) without echoing. Returns None when the provider's SDK
    isn't installed or no key is available.
    """
    from sme.eval.llm_clients import load_api_key

    if provider == "openai":
        api_key = load_api_key("openai", env_fallback="OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            log.info("RubricJudge: openai SDK not installed")
            return None
        return OpenAI(api_key=api_key)

    if provider == "openrouter":
        api_key = load_api_key("openrouter")
        if not api_key:
            return None
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            log.info("RubricJudge: openai SDK not installed")
            return None
        return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    if provider == "anthropic":
        api_key = load_api_key("anthropic")
        if not api_key:
            return None
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError:
            log.info("RubricJudge: anthropic SDK not installed")
            return None
        return anthropic.Anthropic(api_key=api_key)

    return None


class RubricJudge:
    """Generic rubric-based LLM judge.

    Encapsulates provider validation, model resolution, API calling,
    retry logic with exponential backoff, and JSON reply extraction.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        self.provider = provider
        self.model = model or PROVIDER_DEFAULT_MODEL.get(provider)
        self.client = client

    def _resolve_client(self) -> Optional[Any]:
        if self.client is not None:
            return self.client
        self.client = _default_client(self.provider)
        return self.client

    @staticmethod
    def _retry(fn, *, max_retries: int = 3, label: str = "judge"):
        """Run ``fn()`` with exponential backoff, returning its result.

        Only retries on transient API/network errors (ConnectionError,
        TimeoutError, and SDK-specific rate-limit / server-error types).
        Programming bugs (ValueError, TypeError, AttributeError, etc.)
        are re-raised immediately so they don't get masked by retries.

        Raises the final exception on exhaustion.
        """
        retryable = _retryable_types()
        last_exc: Optional[BaseException] = None
        delay = 1.0
        for attempt in range(max_retries):
            try:
                return fn()
            except retryable as e:
                last_exc = e
                log.info(
                    "RubricJudge[%s]: attempt %d/%d failed (%s): %s",
                    label, attempt + 1, max_retries,
                    e.__class__.__name__, e,
                )
                if attempt + 1 < max_retries:
                    time.sleep(delay)
                    delay *= 2
        assert last_exc is not None
        raise last_exc

    def _call_openai_compat(
        self,
        rubric: str,
        body: str,
        *,
        max_retries: int = 3,
        label: str = "openai",
    ) -> dict:
        """Call an OpenAI-compatible Chat Completions endpoint.

        Used for both ``provider='openai'`` and ``provider='openrouter'``.
        Returns ``{'content': str, 'usage': dict}`` on success.
        """
        # Ensure a clean boundary between rubric and body so callers don't
        # have to remember to append a trailing newline to every rubric.
        combined = rubric.rstrip() + "\n\n" + body.lstrip()

        def _do() -> dict:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": combined},
                ],
                temperature=0.0,
            )
            choice = resp.choices[0]
            content = getattr(choice.message, "content", "") or ""
            usage_obj = getattr(resp, "usage", None)
            if usage_obj is None:
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            else:
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(
                        usage_obj, "completion_tokens", 0
                    ) or 0,
                    "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                }
            return {"content": content, "usage": usage}

        return self._retry(_do, max_retries=max_retries, label=label)

    def _call_anthropic(
        self,
        rubric: str,
        body: str,
        *,
        max_tokens: int = 512,
        max_retries: int = 3,
    ) -> dict:
        """Call the Anthropic Messages endpoint with prompt caching on the rubric.

        The rubric is sent as a single system block with
        ``cache_control: ephemeral``; the body is sent as the user message.
        Returns ``{'content': str, 'usage': dict}`` on success.
        """

        def _do() -> dict:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": rubric,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": body}],
            )
            parts: list[str] = []
            for block in getattr(resp, "content", []) or []:
                if getattr(block, "type", None) == "text":
                    parts.append(getattr(block, "text", "") or "")
            content = "".join(parts)
            usage_obj = getattr(resp, "usage", None)
            if usage_obj is None:
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            else:
                input_tokens = getattr(usage_obj, "input_tokens", 0) or 0
                output_tokens = getattr(usage_obj, "output_tokens", 0) or 0
                cache_read = getattr(
                    usage_obj, "cache_read_input_tokens", 0
                ) or 0
                cache_creation = getattr(
                    usage_obj, "cache_creation_input_tokens", 0
                ) or 0
                usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "cache_read_input_tokens": cache_read,
                    "cache_creation_input_tokens": cache_creation,
                }
            return {"content": content, "usage": usage}

        return self._retry(_do, max_retries=max_retries, label="anthropic")

    def judge(
        self,
        rubric: str,
        body: str,
        *,
        use_cache: bool = True,
    ) -> dict:
        """Call the LLM judge with a rubric and body.

        Args:
            rubric: The static (cacheable) rubric text.
            body: The per-call (varying) user prompt body.
            use_cache: When True, read from and write to the disk cache.

        Returns a dict::

            {
                "content": str,      # the raw judge response text
                "usage": dict,       # token usage metadata
                "error": str | None, # error message if call failed
            }
        """
        if self.provider not in VALID_PROVIDERS:
            return {
                "content": "",
                "usage": {},
                "error": (
                    f"unknown provider {self.provider!r}; "
                    f"supported: {sorted(VALID_PROVIDERS)}"
                ),
            }

        # -- Cache read -------------------------------------------------
        if use_cache:
            try:
                from sme.eval.judge_cache import get_cached

                cached = get_cached(rubric, body, self.model, self.provider)
                if cached is not None:
                    log.debug("RubricJudge: cache hit")
                    return {
                        "content": cached.get("content", ""),
                        "usage": cached.get("usage", {}),
                        "error": None,
                    }
            except Exception:  # noqa: BLE001
                # Cache errors must not break the judge pipeline.
                log.warning("RubricJudge: cache read failed, proceeding to API")

        client = self._resolve_client()
        if client is None:
            return {
                "content": "",
                "usage": {},
                "error": (
                    f"no API key in keyring for service={self.provider}; "
                    f"judge skipped"
                ),
            }

        try:
            if self.provider == "anthropic":
                result = self._call_anthropic(rubric, body)
            else:
                result = self._call_openai_compat(
                    rubric, body, label=self.provider
                )
        except Exception as e:  # noqa: BLE001
            return {
                "content": "",
                "usage": {},
                "error": f"judge call failed after retries: {e}",
            }

        # -- Cache write ------------------------------------------------
        if use_cache:
            try:
                from sme.eval.judge_cache import set_cache

                set_cache(result, rubric, body, self.model, self.provider)
            except Exception:  # noqa: BLE001
                log.warning("RubricJudge: cache write failed, result not cached")

        return {
            "content": result["content"],
            "usage": result["usage"],
            "error": None,
        }

    @staticmethod
    def parse_reply(content: str) -> Optional[dict]:
        """Extract the first JSON object from a judge response string.

        Tolerates extra whitespace, code fences, and prose before/after
        the JSON. Returns ``None`` on failure.
        """
        if not content:
            return None
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        blob = stripped[start:end + 1]
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            log.warning(
                "RubricJudge.parse_reply: malformed JSON in first 200 chars: %r",
                stripped[:200],
            )
            return None
