"""Flat baseline adapter for SME.

Reference implementation of Cat 7 Condition A: pure vector similarity
retrieval with no graph traversal, no metadata filtering, no reranking.
Reads a ChromaDB collection and returns top-K by cosine distance.

This is what a vanilla RAG stack does. Every other system is measured
against this baseline. If a graph adapter can't beat flat retrieval on
its target corpus, the graph isn't earning its complexity.

Usage:
    flat = FlatBaselineAdapter(db_path="/path/to/chroma_dir",
                                collection_name="my_collection")
    result = flat.query("what blocked the auth migration?")
    print(result.answer)         # concatenated top-K documents
    print(result.context_string) # the exact text that'd go to an LLM
    # SME's scoring module tokenizes result.context_string via tiktoken

Not to be confused with sme.adapters.mempalace.MemPalaceAdapter, which
reads the same kind of ChromaDB store but respects wing/room/hall
structural metadata during retrieval. The point of having both is the
A-vs-B comparison on the same data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


class FlatBaselineAdapter(SMEAdapter):
    """Pure vector retrieval over a ChromaDB collection.

    Makes no assumptions about metadata schema. Works on any ChromaDB
    persistent directory with any collection — including a MemPalace
    palace directory (where it deliberately ignores the wing/room/hall
    metadata that MemPalaceAdapter uses).
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        read_only: bool = True,  # accepted for CLI parity, ChromaDB has no lock
        collection_name: str = "mempalace_drawers",
        n_results: int = 10,
    ):
        import chromadb

        self._chromadb = chromadb
        self.db_path = str(db_path)
        self.collection_name = collection_name
        self.n_results = n_results

        log.info(
            "opening flat ChromaDB baseline at %s (collection=%s)",
            self.db_path,
            self.collection_name,
        )
        self._client = chromadb.PersistentClient(path=self.db_path)
        try:
            self._collection = self._client.get_collection(self.collection_name)
        except Exception as e:
            raise RuntimeError(
                f"could not open ChromaDB collection {self.collection_name!r} "
                f"at {self.db_path!r}: {e}"
            ) from e

    # --- required SMEAdapter methods ----------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "FlatBaselineAdapter reads an existing ChromaDB collection. "
            "For ingestion, use the target system's own tooling "
            "(e.g. `mempalace mine`) then point FlatBaselineAdapter at "
            "the resulting collection."
        )

    def query(
        self,
        question: str,
        *,
        n_results: Optional[int] = None,
        route: bool = False,  # flat baseline has no routing; accepted for CLI parity
    ) -> QueryResult:
        """Pure vector similarity — no metadata filter, no reranking.

        Per-query ``n_results`` override lets the CLI pass ``--n-results``
        through without requiring a separate constructor. Falls back to
        the value passed at adapter construction."""
        k = n_results if n_results is not None else self.n_results
        try:
            results = self._collection.query(
                query_texts=[question],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            return QueryResult(
                answer="",
                context_string="",
                error=f"INTERNAL: {e}",
            )

        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        ids = (results.get("ids") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]

        if not docs:
            return QueryResult(
                answer="",
                context_string="",
                error="NO_RESULTS",
            )

        # Build context string that would be injected into an LLM prompt.
        # Format: each chunk preceded by a short source label so the
        # downstream model knows where passages came from. SME will
        # tokenize this exact string to compute Cat 7 token efficiency.
        context_parts: list[str] = []
        retrieved: list[Entity] = []
        for i, (doc, meta, doc_id, dist) in enumerate(
            zip(docs, metas or [{}] * len(docs), ids, dists)
        ):
            meta = meta or {}
            source = meta.get("source_file") or meta.get("source") or doc_id
            source_label = Path(str(source)).name if source else f"hit{i}"
            context_parts.append(f"[{i + 1}] {source_label}\n{doc}")
            retrieved.append(
                Entity(
                    id=f"chunk:{doc_id}",
                    name=source_label,
                    entity_type="chunk",
                    properties={
                        "_table": "chromadb_doc",
                        "similarity": 1.0 - float(dist),
                        "source_file": source,
                        # Deliberately NOT including wing/room/hall — flat
                        # baseline ignores structural metadata. If those
                        # fields were respected, this would be MemPalace,
                        # not flat.
                    },
                )
            )

        context_string = "\n\n".join(context_parts)

        # The "answer" from a flat baseline is just the concatenated
        # passages — the downstream LLM would synthesize this. For the
        # first retrieval pass we're not running an answer LLM, so
        # scoring is substring-based on the context_string itself.
        answer = context_string

        return QueryResult(
            answer=answer,
            context_string=context_string,
            retrieved_entities=retrieved,
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """Flat baselines have no structural graph. Return empty —
        Mode B structural categories simply show zeros against flat
        (which is the correct answer: there is no structure)."""
        return [], []

    # --- optional --------------------------------------------------

    def get_flat_retrieval(self, question: str) -> QueryResult:
        """Trivially delegates to query() since this adapter IS the
        flat baseline. Other adapters implement this by disabling their
        structural retrieval path."""
        return self.query(question)

    def get_ontology_source(self) -> dict:
        return {
            "type": "inferred",
            "schema": [],
            "documentation": (
                "Flat baseline has no declared ontology. Every item is "
                "a chunk in a single vector collection with whatever "
                "metadata the source system attached."
            ),
        }

    def close(self) -> None:
        self._collection = None
        self._client = None
