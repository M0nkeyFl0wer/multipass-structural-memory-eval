"""Oracle retrieval baseline — TREC-standard upper bound.

Reads ``expected_sources`` from the gold question set and returns
exactly those items. This is the ceiling — any system that matches
this has perfect retrieval (at the substring level the current
scorer operates on).
"""

from __future__ import annotations

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter


class OracleRetrievalAdapter(SMEAdapter):
    def __init__(self, *, questions: list[dict] | None = None):
        self._corpus: list[dict] = []
        self._questions = questions or []
        # Build a lookup: question text -> expected_sources
        self._gold: dict[str, list[str]] = {}
        for q in self._questions:
            text = q.get("text", "")
            sources = q.get("expected_sources", [])
            if text and sources:
                self._gold[text] = sources

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        self._corpus = list(corpus)
        return {
            "entities_created": len(corpus),
            "edges_created": 0,
            "errors": [],
            "warnings": [],
        }

    def query(self, question: str, n_results: int | None = None) -> QueryResult:
        # n_results is accepted for CLI/testkit parity but ignored: the
        # oracle returns exactly the gold expected_sources, no more, no
        # fewer — that is what makes it the substring-scorer ceiling.
        sources = self._gold.get(question, [])
        if not sources:
            return QueryResult(
                answer="", context_string="", error="NO_GOLD_ANSWER"
            )
        # Build context_string that contains all expected source substrings.
        # The SME scorer uses substring matching, so including the expected
        # substrings verbatim guarantees a perfect score.
        context_parts: list[str] = []
        entities: list[Entity] = []
        for i, source in enumerate(sources):
            context_parts.append(f"[{i+1}] oracle\n{source}")
            entities.append(
                Entity(
                    id=f"oracle:{source}",
                    name=source,
                    entity_type="oracle_source",
                )
            )
        context_string = "\n\n".join(context_parts)
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=entities,
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        return [], []
