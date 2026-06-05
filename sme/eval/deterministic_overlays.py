"""Deterministic evaluation overlays for SME (no API calls).

These metrics are lightweight, reproducible, and complement the
structural-category scorers by providing per-query diagnostics that
can be computed without any LLM inference.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sme.adapters.base import QueryResult

logger = logging.getLogger(__name__)


def contextual_precision_proxy(
    result: QueryResult, expected_sources: list[str]
) -> float | None:
    """Fraction of retrieved entities that are relevant.

    An entity is considered relevant if its ``id`` or ``name`` contains
    at least one of the expected source strings as a substring.

    Returns:
        float in [0.0, 1.0] when expected_sources is non-empty.
        None when expected_sources is empty (no oracle).
    """
    if not expected_sources:
        return None

    total = len(result.retrieved_entities)
    if total == 0:
        return 0.0

    matched = 0
    for entity in result.retrieved_entities:
        if any(
            source in entity.id or source in entity.name
            for source in expected_sources
        ):
            matched += 1

    return matched / total


def token_utilization(result: QueryResult) -> float | None:
    """Ratio of answer tokens to context tokens.

    Uses tiktoken with cl100k_base (same as SME's Cat 7) when available.
    Falls back to a naive whitespace split and logs a warning if tiktoken
    is not installed.

    Returns:
        float > 0.0 when both strings are non-empty.
        None when context_string is empty (cannot compute utilization).
    """
    if not result.context_string:
        return None

    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        context_tokens = len(enc.encode(result.context_string))
        answer_tokens = len(enc.encode(result.answer))
    except ImportError:
        logger.warning(
            "tiktoken not installed; falling back to whitespace token count"
        )
        context_tokens = len(result.context_string.split())
        answer_tokens = len(result.answer.split())

    if context_tokens == 0:
        return None

    return answer_tokens / context_tokens
