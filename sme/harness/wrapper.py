"""Harness-level timing wrapper for adapter.query()."""

from __future__ import annotations

import time

from sme.adapters.base import QueryResult


def timed_query(adapter, question: str, **kwargs) -> QueryResult:
    """Wrap adapter.query() to populate latency_ms.

    Uses ``time.perf_counter()`` for sub-millisecond resolution.  Preserves
    ``interaction_turns`` when the adapter already set it to a value > 1;
    otherwise leaves it at 1 (the dataclass default).
    """
    start = time.perf_counter()
    result = adapter.query(question, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    # The harness layer owns the wall-clock measurement.
    result.latency_ms = elapsed_ms

    # Preserve multi-turn counts; default to 1 if absent or <= 0.
    turns = getattr(result, "interaction_turns", 1)
    if turns < 1:
        turns = 1
    result.interaction_turns = turns

    return result
