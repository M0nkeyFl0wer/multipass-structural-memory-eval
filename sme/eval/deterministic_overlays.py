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


def entity_id_overlap(
    result: QueryResult, expected_sources: list[str]
) -> float | None:
    """Fraction of retrieved entities whose id/name overlaps expected sources.

    This is NOT a general contextual-precision metric — it only works when
    adapter entity IDs are human-readable substrings of the oracle source
    strings. For semantic search with opaque IDs (UUIDs, hashes), this
    returns 0.0 regardless of retrieval quality.

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
        e_id = entity.id.lower()
        e_name = entity.name.lower()
        if any(
            source.lower() in e_id or source.lower() in e_name
            for source in expected_sources
        ):
            matched += 1

    return matched / total


def token_utilization(result: QueryResult) -> float | None:
    """Compression ratio: how much the answer shrinks the context.

    A well-utilized answer is concise and dense. This metric returns
    a *lower* value for bloated or hallucinated answers.

    Formula: min(answer_tokens, context_tokens) / context_tokens
    - 1.0 = answer uses the entire context (or more — capped)
    - 0.05 = answer is a tight 5 % summary of a large context
    - 0.0 = empty answer

    Uses tiktoken with cl100k_base (same as SME's Cat 7) when available.
    Falls back to a naive whitespace split and logs a warning.

    Returns:
        float in [0.0, 1.0] when context_string is non-empty.
        None when context_string is empty (cannot compute).
    """
    if not result.context_string:
        return None

    # Pass-through adapters (e.g. FullContextAdapter, CKGAdapter) set
    # answer=context_string.  The compression ratio is meaningless when
    # the system is not summarising — it is just echoing the context.
    if result.answer.strip() == result.context_string.strip():
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

    # Capped at 1.0: an answer longer than context is no more "utilized"
    # than one that exactly matches context length.
    return min(answer_tokens, context_tokens) / context_tokens
