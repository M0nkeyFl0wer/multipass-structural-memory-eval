"""Adapter interface for SME (spec v5).

Every memory system under test implements SMEAdapter. The benchmark suite
never touches a database directly — it talks to this thin interface.

Three required methods: ingest_corpus, query, get_graph_snapshot.
Two optional: get_flat_retrieval, get_ontology_source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class Entity:
    id: str
    name: str
    entity_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None  # shape (dim,) when present


@dataclass
class Edge:
    source_id: str
    target_id: str
    edge_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    # Reserved property keys for Cat 6b provenance:
    #   _created_by:    str  — extraction pattern or process that created this edge
    #   _created_at:    str  — ISO timestamp
    #   _superseded_by: str  — edge id that replaced this one (if applicable)


@dataclass
class ContradictionPair:
    """Structured response for Cat 3. Systems that don't surface
    contradictions leave this empty and score 0."""

    claim_a: str
    claim_b: str
    source_a: str  # entity/session id
    source_b: str


@dataclass
class QueryResult:
    answer: str
    # The exact text the adapter would inject into the LLM prompt.
    # SME tokenizes this with tiktoken (cl100k_base) to compute Cat 7
    # metrics. Adapters cannot game the token count.
    context_string: str = ""
    retrieved_entities: list[Entity] = field(default_factory=list)
    retrieved_edges: list[Edge] = field(default_factory=list)
    retrieval_path: list[Any] = field(default_factory=list)
    contradictions: list[ContradictionPair] = field(default_factory=list)
    # If query() fails, set this instead of raising. SME distinguishes
    # "errored" from "answered wrong" in the scorecard.
    error: Optional[str] = None


class SMEAdapter(ABC):
    """Implement this for your database/memory system.

    Three required methods. Two optional.
    """

    # --- Required ------------------------------------------------------

    @abstractmethod
    def ingest_corpus(self, corpus: list[dict]) -> dict:
        """Load the seeded test corpus.

        Returns a dict with at least:
            entities_created: int
            edges_created: int
            errors: list[str]
            warnings: list[str]
        """

    @abstractmethod
    def query(self, question: str) -> QueryResult:
        """Run a natural language query through the full pipeline.

        Must populate `context_string` with the exact text the adapter
        would send to the LLM.
        """

    @abstractmethod
    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """Return the full graph state for topology analysis.

        For systems without a graph, return ([], []).
        """

    # --- Optional (have sensible defaults) -----------------------------

    def get_flat_retrieval(self, question: str) -> QueryResult:
        """Vector-only retrieval with no graph traversal.

        Used as Cat 7 Condition A. If not implemented, SME falls back to
        its built-in FlatBaseline adapter using the same corpus and
        embedding model.
        """
        raise NotImplementedError

    def get_ontology_source(self) -> dict:
        """Return ontology documentation for Category 8.

        Priority order:
          1. declared — declared schema, ONTOLOGY.md, typed tables
          2. readme   — documentation claims (pre-extracted YAML)
          3. inferred — no docs, analyze graph directly

        Returns:
            {'type': 'declared'|'readme'|'inferred',
             'schema': list,
             'documentation': str}
        """
        return {"type": "inferred", "schema": [], "documentation": ""}

    # --- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        """Release any resources. Safe to call multiple times."""
