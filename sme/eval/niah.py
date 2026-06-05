"""Needle-in-a-haystack (NIAH) stress tests for SME adapters.

Provides synthetic literal and sequential needle insertion against a
distractor corpus, then probes an SME adapter to see whether each
needle is present in the returned context or retrieved entities.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from sme.adapters.base import QueryResult, SMEAdapter

# -- Data classes -------------------------------------------------------


@dataclass
class NeedleResult:
    needle: str
    depth_pct: float  # 0.0 = start, 1.0 = end
    found: bool
    found_rank: Optional[int]  # position in retrieved results, None if not found


@dataclass
class NIAHReport:
    corpus_size: int
    needle_count: int
    needles_found: int
    needles_found_in_order: int  # for sequential NIAH only
    mean_depth_pct: float
    results: list[NeedleResult]


# -- Distractor generation ----------------------------------------------

_SENTENCE_TEMPLATES = [
    "The weather is {adj} today.",
    "A {noun} walked across the room.",
    "She found a {adj} {noun} in the corner.",
    "It is common to see {noun} during {time}.",
    "The {noun} seems {adj} lately.",
    "They discussed the {noun} for hours.",
    "An {adj} {noun} appeared out of nowhere.",
    "We observed the {noun} with great interest.",
    "The {noun} was {adj} and unremarkable.",
    "During {time}, the {noun} moved slowly.",
]

_ADJECTIVES = [
    "sunny", "rainy", "cloudy", "bright", "dark",
    "cold", "warm", "quiet", "loud", "strange",
    "ordinary", "colorful", "dull", "smooth", "rough",
]

_NOUNS = [
    "cat", "dog", "bird", "tree", "house",
    "car", "book", "phone", "table", "chair",
    "river", "mountain", "cloud", "shadow", "window",
    "door", "garden", "street", "city", "village",
]

_TIMES = [
    "morning", "afternoon", "evening", "night",
    "spring", "summer", "autumn", "winter",
]


def generate_distractor_corpus(size: int, *, seed: int = 42) -> list[str]:
    """Generate synthetic distractor sentences.

    Uses a small vocabulary of sentence templates with random words to
    create semantically bland but varied text.
    """
    rng = random.Random(seed)
    corpus: list[str] = []
    for _ in range(size):
        template = rng.choice(_SENTENCE_TEMPLATES)
        sentence = template.format(
            adj=rng.choice(_ADJECTIVES),
            noun=rng.choice(_NOUNS),
            time=rng.choice(_TIMES),
        )
        corpus.append(sentence)
    return corpus


# -- Needle insertion ---------------------------------------------------


def insert_literal_needles(
    corpus: list[str],
    needles: list[tuple[str, str]],
    *,
    seed: int = 42,
) -> tuple[list[str], list[float]]:
    """Insert needles at random positions.

    Each needle is a ``(needle_text, question)`` tuple.  Only the
    ``needle_text`` is written into the corpus.

    Returns ``(corpus_with_needles, depth_pcts)``.
    """
    rng = random.Random(seed)
    if not needles:
        return corpus.copy(), []

    # Ensure we don't try to sample more indices than available
    n_positions = min(len(needles), len(corpus))
    indices = sorted(rng.sample(range(len(corpus)), n_positions))

    # If there are more needles than corpus sentences, some needles are dropped
    # (this preserves the original corpus size)
    working_needles = needles[:n_positions]

    out = corpus.copy()
    depth_pcts: list[float] = []
    for idx, needle in zip(indices, working_needles):
        out[idx] = needle[0]
        depth_pcts.append(idx / (len(corpus) - 1) if len(corpus) > 1 else 0.0)

    return out, depth_pcts


def insert_sequential_needles(
    corpus: list[str],
    needles: list[tuple[str, str]],
    *,
    seed: int = 42,
) -> tuple[list[str], list[float]]:
    """Insert needles in sequence at increasing depths.

    Each needle is a ``(needle_text, question)`` tuple.  Only the
    ``needle_text`` is written into the corpus.

    Returns ``(corpus_with_needles, depth_pcts)``.
    """
    rng = random.Random(seed)
    if not needles or not corpus:
        return corpus.copy(), []

    out = corpus.copy()
    n = len(needles)

    # Compute target depths with a small random perturbation so they aren't
    # perfectly evenly spaced, while guaranteeing strict increase.
    base_step = 1.0 / (n + 1)
    depths: list[float] = []
    for i in range(n):
        jitter = rng.uniform(-base_step * 0.15, base_step * 0.15)
        d = (i + 1) * base_step + jitter
        d = max(0.05, min(0.95, d))
        depths.append(d)

    # Convert depths to indices, enforcing strict increase
    indices: list[int] = []
    for d in depths:
        idx = int(round(d * (len(corpus) - 1)))
        # Ensure strictly increasing by pushing forward if necessary
        if indices and idx <= indices[-1]:
            idx = indices[-1] + 1
        # Clamp to valid range
        idx = min(idx, len(corpus) - 1)
        indices.append(idx)

    # If clamping caused duplicates at the tail, some later needles may
    # overlap — that is acceptable for the stress test.
    depth_pcts: list[float] = []
    for idx, needle in zip(indices, needles):
        out[idx] = needle[0]
        depth_pcts.append(idx / (len(corpus) - 1) if len(corpus) > 1 else 0.0)

    return out, depth_pcts


# -- Runner -------------------------------------------------------------


def run_niah(
    adapter: SMEAdapter,
    needles: list[tuple[str, str]],
    corpus_size: int = 1000,
    *,
    sequential: bool = False,
    seed: int = 42,
) -> NIAHReport:
    """Run needle-in-a-haystack against an SME adapter.

    Each needle is a ``(needle_text, question)`` tuple.  The ``question``
    is passed to ``adapter.query()``, and the report checks whether
    ``needle_text`` appears in the returned answer, context string, or
    retrieved entities.

    1. Generate distractor corpus
    2. Insert needles (literal or sequential)
    3. Concatenate corpus into a single large text
    4. Call ``adapter.query(question)`` for each needle
    5. Check if ``needle_text`` appears in ``result.answer``,
       ``result.context_string``, or ``result.retrieved_entities``
    6. Return report
    """
    corpus = generate_distractor_corpus(corpus_size, seed=seed)
    if sequential:
        corpus, depth_pcts = insert_sequential_needles(corpus, needles, seed=seed)
    else:
        corpus, depth_pcts = insert_literal_needles(corpus, needles, seed=seed)

    # Ingest as a list of dicts — the standard SME corpus shape.
    doc_corpus = [{"id": f"sent-{i}", "text": sent} for i, sent in enumerate(corpus)]
    adapter.ingest_corpus(doc_corpus)

    results: list[NeedleResult] = []
    found_count = 0

    # If insertion dropped needles (e.g. corpus too small), pad depths so
    # every needle still appears in the report.
    padded_depths = list(depth_pcts) + [0.0] * (len(needles) - len(depth_pcts))

    for (needle_text, question), depth in zip(needles, padded_depths):
        query_result: QueryResult = adapter.query(question)

        found = False
        rank: Optional[int] = None

        # 1. Substring match in the answer
        if query_result.answer and needle_text in str(query_result.answer):
            found = True

        # 2. Substring match in the context string
        if not found and query_result.context_string and needle_text in query_result.context_string:
            found = True

        # 3. Name match in retrieved entities
        if not found and query_result.retrieved_entities:
            for entity in query_result.retrieved_entities:
                if needle_text in entity.name:
                    found = True
                    break

        if found:
            found_count += 1
            # Rank = first entity position whose name contains the needle text
            for i, entity in enumerate(query_result.retrieved_entities):
                if needle_text in entity.name:
                    rank = i
                    break
            if rank is None:
                # Found via answer/context_string but not as a discrete ranked entity
                rank = 0

        results.append(
            NeedleResult(
                needle=needle_text,
                depth_pct=depth,
                found=found,
                found_rank=rank if found else None,
            )
        )

    # For sequential NIAH, count the longest prefix of consecutive finds.
    found_in_order = 0
    if sequential:
        for r in results:
            if r.found:
                found_in_order += 1
            else:
                break
    else:
        # Literal NIAH has no ordering semantics; just report total found.
        found_in_order = 0

    mean_depth = sum(depth_pcts) / len(depth_pcts) if depth_pcts else 0.0

    return NIAHReport(
        corpus_size=corpus_size,
        needle_count=len(needles),
        needles_found=found_count,
        needles_found_in_order=found_in_order,
        mean_depth_pct=mean_depth,
        results=results,
    )
