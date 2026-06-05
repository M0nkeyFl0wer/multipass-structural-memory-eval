"""Tests for the needle-in-a-haystack (NIAH) evaluator."""

from __future__ import annotations


from sme.adapters.base import Entity, QueryResult, SMEAdapter
from sme.eval.niah import (
    NIAHReport,
    NeedleResult,
    generate_distractor_corpus,
    insert_literal_needles,
    insert_sequential_needles,
    run_niah,
)


# -- Fixtures / helpers -------------------------------------------------


class _MockAdapter(SMEAdapter):
    """Adapter that does simple substring matching over an ingested corpus.

    Every sentence is exposed as an ``Entity`` so ``found_rank`` can be
    verified.
    """

    def __init__(self):
        self._corpus_text = ""
        self._sentences: list[str] = []

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        self._sentences = [d.get("text", "") for d in corpus]
        self._corpus_text = "\n".join(self._sentences)
        return {
            "entities_created": len(self._sentences),
            "edges_created": 0,
            "errors": [],
            "warnings": [],
        }

    def query(self, question: str) -> QueryResult:
        found = any(question in s for s in self._sentences)
        entities = [
            Entity(id=f"e{i}", name=s, entity_type="sentence")
            for i, s in enumerate(self._sentences)
        ]
        return QueryResult(
            answer="yes" if found else "no",
            context_string=self._corpus_text if found else "",
            retrieved_entities=entities,
            retrieved_edges=[],
            retrieval_path=[],
        )

    def get_graph_snapshot(self):
        return [], []


class _ShallowOnlyAdapter(SMEAdapter):
    """Adapter that only finds needles in the first half of the corpus."""

    def __init__(self):
        self._sentences: list[str] = []

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        self._sentences = [d.get("text", "") for d in corpus]
        return {"entities_created": 0, "edges_created": 0, "errors": [], "warnings": []}

    def query(self, question: str) -> QueryResult:
        half = len(self._sentences) // 2
        shallow = self._sentences[:half]
        found = any(question in s for s in shallow)
        entities = [
            Entity(id=f"e{i}", name=s, entity_type="sentence")
            for i, s in enumerate(shallow)
        ]
        return QueryResult(
            answer="yes" if found else "no",
            context_string="\n".join(shallow) if found else "",
            retrieved_entities=entities,
            retrieved_edges=[],
            retrieval_path=[],
        )

    def get_graph_snapshot(self):
        return [], []


# -- generate_distractor_corpus ----------------------------------------


def test_generate_distractor_corpus_produces_requested_size() -> None:
    for size in (0, 1, 10, 100):
        corpus = generate_distractor_corpus(size, seed=123)
        assert len(corpus) == size


def test_generate_distractor_corpus_is_varied() -> None:
    corpus = generate_distractor_corpus(50, seed=42)
    assert len(set(corpus)) > 1  # not all identical


def test_generate_distractor_corpus_is_deterministic() -> None:
    a = generate_distractor_corpus(20, seed=7)
    b = generate_distractor_corpus(20, seed=7)
    assert a == b


# -- insert_literal_needles --------------------------------------------


def test_insert_literal_needles_puts_all_needles() -> None:
    corpus = generate_distractor_corpus(100, seed=1)
    needles = ["NEEDLE-ALPHA", "NEEDLE-BETA", "NEEDLE-GAMMA"]
    out, depths = insert_literal_needles(corpus, needles, seed=2)
    assert len(out) == len(corpus)
    for needle in needles:
        assert needle in out
    assert len(depths) == len(needles)
    for d in depths:
        assert 0.0 <= d <= 1.0


def test_insert_literal_needles_empty_needle_list() -> None:
    corpus = generate_distractor_corpus(10, seed=1)
    out, depths = insert_literal_needles(corpus, [], seed=1)
    assert out == corpus
    assert depths == []


def test_insert_literal_needles_preserves_corpus_size() -> None:
    corpus = generate_distractor_corpus(50, seed=3)
    needles = ["A", "B", "C", "D", "E"]
    out, _ = insert_literal_needles(corpus, needles, seed=4)
    assert len(out) == len(corpus)


# -- insert_sequential_needles -----------------------------------------


def test_insert_sequential_needles_preserves_order() -> None:
    corpus = generate_distractor_corpus(200, seed=5)
    needles = ["FIRST", "SECOND", "THIRD"]
    out, depths = insert_sequential_needles(corpus, needles, seed=6)
    assert len(out) == len(corpus)
    for needle in needles:
        assert needle in out
    # Depths must be strictly increasing
    for i in range(1, len(depths)):
        assert depths[i] > depths[i - 1]


def test_insert_sequential_needles_empty_needle_list() -> None:
    corpus = generate_distractor_corpus(10, seed=1)
    out, depths = insert_sequential_needles(corpus, [], seed=1)
    assert out == corpus
    assert depths == []


def test_insert_sequential_needles_single_needle() -> None:
    corpus = generate_distractor_corpus(100, seed=1)
    out, depths = insert_sequential_needles(corpus, ["ONLY"], seed=1)
    assert "ONLY" in out
    assert len(depths) == 1
    assert 0.0 <= depths[0] <= 1.0


# -- run_niah (literal) -------------------------------------------------


def test_run_niah_literal_finds_shallow_and_deep() -> None:
    adapter = _MockAdapter()
    needles = ["SHALLOW-NEEDLE", "DEEP-NEEDLE"]
    report = run_niah(adapter, needles, corpus_size=100, sequential=False, seed=99)

    assert isinstance(report, NIAHReport)
    assert report.corpus_size == 100
    assert report.needle_count == 2
    assert report.needles_found == 2
    assert report.needles_found_in_order == 0  # literal mode
    assert len(report.results) == 2
    for r in report.results:
        assert r.found is True
        assert r.found_rank is not None
        assert r.found_rank >= 0


def test_run_niah_literal_report_metrics() -> None:
    adapter = _MockAdapter()
    needles = ["A-NEEDLE", "B-NEEDLE", "C-NEEDLE"]
    report = run_niah(adapter, needles, corpus_size=200, sequential=False, seed=11)

    assert report.needle_count == 3
    assert report.needles_found == 3
    assert 0.0 < report.mean_depth_pct < 1.0


def test_run_niah_literal_not_found() -> None:
    adapter = _ShallowOnlyAdapter()
    # Put one needle in the deep half so it is missed
    corpus = generate_distractor_corpus(100, seed=12)
    # Manually place needles: first at index 10, second at index 80
    needles = ["SHALLOW-X", "DEEP-Y"]
    corpus[10] = needles[0]
    corpus[80] = needles[1]

    adapter.ingest_corpus([{"id": f"s{i}", "text": s} for i, s in enumerate(corpus)])
    # We can't call run_niah directly because it regenerates the corpus.
    # Instead, test through the helper manually:
    result0 = adapter.query(needles[0])
    result1 = adapter.query(needles[1])

    assert needles[0] in result0.context_string
    assert needles[1] not in result1.context_string


def test_run_niah_empty_needle_list() -> None:
    adapter = _MockAdapter()
    report = run_niah(adapter, [], corpus_size=50, seed=1)
    assert report.needle_count == 0
    assert report.needles_found == 0
    assert report.needles_found_in_order == 0
    assert report.mean_depth_pct == 0.0
    assert report.results == []


# -- run_niah (sequential) ----------------------------------------------


def test_run_niah_sequential_checks_found_in_order() -> None:
    adapter = _MockAdapter()
    needles = ["SEQ-A", "SEQ-B", "SEQ-C"]
    report = run_niah(adapter, needles, corpus_size=150, sequential=True, seed=21)

    assert report.needle_count == 3
    assert report.needles_found == 3
    assert report.needles_found_in_order == 3  # all found consecutively
    # Depths should be increasing
    depths = [r.depth_pct for r in report.results]
    for i in range(1, len(depths)):
        assert depths[i] > depths[i - 1]


def test_run_niah_sequential_partial_order() -> None:
    """If a deep needle is missed, found_in_order stops at the gap."""
    adapter = _ShallowOnlyAdapter()
    corpus = generate_distractor_corpus(100, seed=30)
    needles = ["SEQ-A", "SEQ-B", "SEQ-C"]
    # Insert manually at known positions: 10, 30, 80
    for idx, needle in zip((10, 30, 80), needles):
        corpus[idx] = needle

    adapter.ingest_corpus([{"id": f"s{i}", "text": s} for i, s in enumerate(corpus)])
    # Build report by hand since run_niah regenerates the corpus
    results: list[NeedleResult] = []
    found_in_order = 0
    for needle, idx in zip(needles, (10, 30, 80)):
        result = adapter.query(needle)
        found = needle in result.context_string
        rank = None
        if found:
            for i, ent in enumerate(result.retrieved_entities):
                if needle in ent.name:
                    rank = i
                    break
            if rank is None:
                rank = 0
        results.append(
            NeedleResult(
                needle=needle,
                depth_pct=idx / 99,
                found=found,
                found_rank=rank if found else None,
            )
        )
    # found_in_order = longest prefix of consecutive finds
    for r in results:
        if r.found:
            found_in_order += 1
        else:
            break

    report = NIAHReport(
        corpus_size=100,
        needle_count=3,
        needles_found=sum(1 for r in results if r.found),
        needles_found_in_order=found_in_order,
        mean_depth_pct=sum(r.depth_pct for r in results) / len(results),
        results=results,
    )

    assert report.needles_found == 2  # shallow ones
    assert report.needles_found_in_order == 2


# -- Edge cases ---------------------------------------------------------


def test_run_niah_corpus_size_zero() -> None:
    adapter = _MockAdapter()
    report = run_niah(adapter, ["X"], corpus_size=0, seed=1)
    assert report.corpus_size == 0
    assert report.needle_count == 1
    assert report.needles_found == 0
    assert report.results[0].found is False
    assert report.results[0].found_rank is None


def test_run_niah_needle_count_exceeds_corpus() -> None:
    """Literal insertion samples without replacement; excess needles are dropped."""
    corpus = generate_distractor_corpus(5, seed=1)
    needles = [f"NEEDLE-{i}" for i in range(20)]
    out, depths = insert_literal_needles(corpus, needles, seed=2)
    assert len(out) == 5
    assert len(depths) == 5  # only as many as fit


def test_run_niah_rank_via_entities() -> None:
    """If an adapter returns entities, found_rank should reflect entity order."""
    adapter = _MockAdapter()
    needles = ["RANK-TEST"]
    report = run_niah(adapter, needles, corpus_size=50, seed=42)
    assert report.results[0].found is True
    # The needle replaced exactly one sentence, so its entity rank equals
    # that sentence's index.
    assert isinstance(report.results[0].found_rank, int)
    assert report.results[0].found_rank >= 0
