"""Random retrieval baseline — TREC-standard lower bound.

Returns K uniformly random items from the ingested corpus, seeded
for reproducibility. Any memory system that can't beat this isn't
doing retrieval — it's doing random selection.
"""

from __future__ import annotations

import random as random_mod

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter


class RandomRetrievalAdapter(SMEAdapter):
    def __init__(self, *, seed: int = 42, n_results: int = 10):
        self._seed = seed
        self._rng = random_mod.Random(seed)
        self._n_results = n_results
        self._corpus: list[dict] = []

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        self._corpus = list(corpus)
        return {
            "entities_created": len(corpus),
            "edges_created": 0,
            "errors": [],
            "warnings": [],
        }

    def query(self, question: str, n_results: int | None = None) -> QueryResult:
        if not self._corpus:
            return QueryResult(answer="", context_string="", error="NO_CORPUS")
        n = self._n_results if n_results is None else n_results
        k = min(n, len(self._corpus))
        selected = self._rng.sample(self._corpus, k)
        context_parts: list[str] = []
        entities: list[Entity] = []
        for i, item in enumerate(selected):
            item_id = item.get("id") or item.get("source_file") or f"item_{i}"
            source = item.get("source_file", item.get("id", f"random_{i}"))
            text = item.get("text", item.get("content", ""))
            context_parts.append(f"[{i+1}] {source}\n{text}")
            entities.append(
                Entity(
                    id=f"random:{item_id}",
                    name=str(source),
                    entity_type="random_selection",
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
