"""Multi-provider LLM clients for SME's compile-wiki + judge pipelines.

Constitutional principle (per docs/industry_standards_integration.md):
SME stays lightweight. Every provider here is a thin wrapper — no
framework dependencies, no langchain/llama-index, no heavy SDK trees.
Each provider only imports its own SDK lazily so SME's base install
stays small.

Providers (all share an `LLMClient`-shaped interface — `complete(prompt)
-> str`):

  - StubLLMClient        — deterministic no-LLM summaries; no deps,
                           used in tests / CI / smoke runs
  - OpenAILLMClient      — direct OpenAI Chat Completions
  - OpenRouterLLMClient  — OpenAI-compatible gateway (different
                           base_url + api_key); used to reach GPT-4o
                           via OpenRouter without an OpenAI account
  - AnthropicLLMClient   — direct Anthropic SDK with prompt caching
                           on the stable static prefix (system) so
                           re-use across many notes / questions in a
                           single run is cheap. Uses adaptive thinking.

Key access:
    Each non-stub client reads its API key from the system keyring at
    construction time via `secret-tool lookup service <service>`. No
    keys are echoed, logged, or cached in environment variables.
    Service-name conventions match the user's keyring layout:

        anthropic   →  Anthropic API key
        openrouter  →  OpenRouter API key
        openai      →  OpenAI API key (falls back to OPENAI_API_KEY
                       env var if no keyring entry)

    See `~/.claude/CLAUDE.md` § Credential Access Policy for the
    discipline rules.
"""
from __future__ import annotations

import logging
import os
import subprocess
from typing import Any, Optional, Protocol

log = logging.getLogger(__name__)


# Default models per provider. The user requested Sonnet for compile +
# judge — `claude-sonnet-4-6` is the latest Sonnet. For OpenRouter the
# LongMemEval judge methodology uses gpt-4o-2024-08-06.
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
OPENROUTER_DEFAULT_JUDGE_MODEL = "openai/gpt-4o-2024-08-06"


# --- API-key loading (no env exposure, no echoing) ----------------------


def load_api_key(
    service: str,
    *,
    env_fallback: Optional[str] = None,
    timeout_s: int = 5,
) -> Optional[str]:
    """Load an API key from the system keyring without echoing it.

    Tries `secret-tool lookup service <service>` first. If that fails
    or returns empty, falls back to the named environment variable
    (when provided). Returns None if neither source has a key — the
    caller decides whether to error or skip.

    Never prints, logs, or returns the key in a debugging surface.
    """
    try:
        result = subprocess.run(
            ["secret-tool", "lookup", "service", service],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,  # missing entry returns 1; not exceptional
        )
        if result.returncode == 0:
            key = result.stdout.strip()
            if key:
                return key
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        log.info("keyring lookup unavailable: %s", exc.__class__.__name__)

    if env_fallback:
        key = os.environ.get(env_fallback, "").strip()
        if key:
            return key
    return None


# --- LLMClient Protocol -------------------------------------------------


class LLMClient(Protocol):
    """Minimal interface every provider implements."""

    def complete(self, prompt: str, **kwargs) -> str:
        ...


# --- Prompt splitting for cacheable prefix detection -------------------


# Markers that delimit the static prompt prefix from the per-call body
# in SME's wiki_compiler + judge templates. Anything BEFORE the marker
# can be cached as a system block; anything AFTER goes in the user
# message. These are the **single source of truth** — every prompt
# template that wants to participate in prefix caching must contain
# one of these markers verbatim.
#
# Named constants so prompt templates can import them by name and stay
# coupled at the language level, not the string-literal level. If you
# rename one of these, every prompt template that references it will
# need to update too — but at least it'll be a real Python rename, not
# a silent string drift that produces a 0% cache-hit rate.
ARTICLE_PROMPT_MARKER = "Source path:"
INDEX_PROMPT_MARKER = "Articles:"
JUDGE_PROMPT_MARKER = "Question:"

CACHEABLE_PREFIX_MARKERS = (
    ARTICLE_PROMPT_MARKER,
    INDEX_PROMPT_MARKER,
    JUDGE_PROMPT_MARKER,
)


def split_for_caching(prompt: str) -> tuple[str, str]:
    """Split a prompt into (cacheable_system, varying_user).

    Looks for the first occurrence of any known marker and splits
    there. The marker itself goes into the user portion so the prompt
    template stays self-describing on the user side.

    If no marker is found the entire prompt becomes the user message
    and the system stays empty — providers without prompt caching
    won't notice; providers with caching just won't get a cache benefit
    for that call.
    """
    for marker in CACHEABLE_PREFIX_MARKERS:
        idx = prompt.find(marker)
        if idx > 0:
            return prompt[:idx].rstrip(), prompt[idx:]
    return "", prompt


# --- StubLLMClient (no deps) -------------------------------------------


class StubLLMClient:
    """Deterministic LLM stub.

    Produces a reproducible summary per note so the compile pipeline can
    be exercised end-to-end without real LLM credits, and so cross-
    validation runs that don't need true LLM compilation can still use
    Condition D2 as a sanity baseline.
    """

    def complete(self, prompt: str, **kwargs) -> str:
        if "Source path:" in prompt:
            for line in prompt.splitlines():
                if line.startswith("Source path: "):
                    rel = line.split(": ", 1)[1].strip()
                    body_marker = "Source content:\n---\n"
                    end_marker = "\n---"
                    body = ""
                    if body_marker in prompt:
                        body = prompt.split(body_marker, 1)[1]
                        if end_marker in body:
                            body = body.split(end_marker, 1)[0]
                    head = body.strip().split("\n", 1)[0][:160]
                    return (
                        f"# Stub summary of {rel}\n\n"
                        f"First line of source: {head}\n"
                    )
        return "# Index\n\n(stub-generated)\n"


# --- OpenAILLMClient ---------------------------------------------------


class OpenAILLMClient:
    """Direct OpenAI Chat Completions client.

    Reads the API key from keyring (service=openai) or the
    OPENAI_API_KEY env var as a fallback.
    """

    def __init__(self, *, model: str = OPENAI_DEFAULT_MODEL) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover — runtime install
            raise SystemExit(
                "openai package not installed; run "
                "`pip install openai` or use --llm-provider stub."
            ) from exc

        api_key = load_api_key("openai", env_fallback="OPENAI_API_KEY")
        if not api_key:
            raise SystemExit(
                "no OpenAI API key in keyring (service=openai) or "
                "OPENAI_API_KEY env var."
            )
        self._client = OpenAI(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""


# --- OpenRouterLLMClient (OpenAI-compatible) --------------------------


class OpenRouterLLMClient:
    """OpenRouter (OpenAI-compatible) client.

    OpenRouter speaks the OpenAI Chat Completions wire format; we use
    the openai SDK with `base_url='https://openrouter.ai/api/v1'`.
    Used primarily for the LongMemEval GPT-4o judge methodology, since
    the published numbers use gpt-4o-2024-08-06 and OpenRouter serves
    it without requiring an OpenAI account.

    Model strings on OpenRouter are namespaced (e.g.
    `openai/gpt-4o-2024-08-06`, `anthropic/claude-sonnet-4-6`).
    """

    def __init__(
        self,
        *,
        model: str = OPENROUTER_DEFAULT_JUDGE_MODEL,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover — runtime install
            raise SystemExit(
                "openai package not installed; required for OpenRouter "
                "(OpenAI-compatible). Install with `pip install openai`."
            ) from exc

        api_key = load_api_key("openrouter")
        if not api_key:
            raise SystemExit(
                "no OpenRouter API key in keyring "
                "(service=openrouter)."
            )
        self._client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""


# --- AnthropicLLMClient with prompt caching ---------------------------


class AnthropicLLMClient:
    """Anthropic SDK client with prompt caching on the static prefix.

    Splits each `complete(prompt)` call into a stable system prefix
    (the prompt template up to the first per-call marker, e.g.
    "Source path:") and a varying user message. The system block is
    sent with `cache_control: ephemeral`, so the cache prefix is
    written on the first call in a run and read by every subsequent
    call — saving ~90% on the static portion across many notes.

    Defaults to Sonnet 4.6 (the most recent Sonnet — Sonnet 4.7 does
    not exist; if the caller meant Opus 4.7, pass model='claude-opus-4-7'
    explicitly).

    Adaptive thinking is enabled by default. To surface reasoning
    summaries in tool output (Opus 4.7 omits them by default), pass
    `display='summarized'`.
    """

    def __init__(
        self,
        *,
        model: str = ANTHROPIC_DEFAULT_MODEL,
        thinking: str = "adaptive",
        display: str = "omitted",
        max_tokens: int = 2048,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover — runtime install
            raise SystemExit(
                "anthropic package not installed; run "
                "`pip install anthropic` or use --llm-provider stub / openai / openrouter."
            ) from exc

        api_key = load_api_key("anthropic")
        if not api_key:
            raise SystemExit(
                "no Anthropic API key in keyring (service=anthropic). "
                "Use `secret-tool store --label='Anthropic' service anthropic` "
                "to add one, or use a non-Anthropic provider."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.thinking = thinking
        self.display = display
        self.max_tokens = max_tokens

    def complete(self, prompt: str, **kwargs) -> str:
        system_text, user_text = split_for_caching(prompt)

        # Build the system block with cache_control on the static
        # prefix. If the prompt didn't split cleanly (no known marker)
        # the system block is empty — caching just doesn't activate
        # for that call, which is fine *if* the caller meant for this
        # prompt to be uncached. But silent cache misses are also the
        # exact failure mode we're trying to prevent (a prompt template
        # rename that drifts away from the markers and quietly loses
        # caching), so log a warning so it's at least visible.
        system_blocks: list[dict[str, Any]] = []
        if system_text:
            system_blocks.append(
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        else:
            log.warning(
                "AnthropicLLMClient: prompt produced no cacheable prefix "
                "(no known marker found among %s) — every call will pay "
                "full input cost. If this is unexpected, the prompt "
                "template has drifted from CACHEABLE_PREFIX_MARKERS.",
                CACHEABLE_PREFIX_MARKERS,
            )

        thinking_param: dict[str, Any] = {"type": "disabled"}
        if self.thinking == "adaptive":
            thinking_param = {"type": "adaptive", "display": self.display}

        kwargs_to_pass: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": user_text}],
            "thinking": thinking_param,
        }
        if system_blocks:
            kwargs_to_pass["system"] = system_blocks

        response = self._client.messages.create(**kwargs_to_pass)

        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text or ""
        return ""
