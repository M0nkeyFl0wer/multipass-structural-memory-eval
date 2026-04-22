"""Adapter interface for SME (spec v5).

Every memory system under test implements SMEAdapter. The benchmark suite
never touches a database directly — it talks to this thin interface.

Three required methods: ingest_corpus, query, get_graph_snapshot.
Two optional: get_flat_retrieval, get_ontology_source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

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
class ProbeResult:
    """Outcome of probing a single HarnessDescriptor.

    Minimum viable shape for Cat 9b (call-through success). A future
    Cat 9a/9c implementation that involves a real model API will likely
    extend this with ``reply_text``, ``model_invoked``, ``context_used``
    etc. — treat this as a stable floor, not a frozen schema.
    """

    success: bool
    latency_ms: float = 0.0
    error: Optional[str] = None
    # Free-form for diagnostics; not parsed by the scorecard.
    output: Optional[str] = None


@dataclass
class HarnessDescriptor:
    """Declaration of one way an external caller can reach this memory system.

    Adapters return a list of these from ``get_harness_manifest()``. The
    ``kind`` field follows the spec v8 § Cat 9 taxonomy. For the current
    minimum-viable 9b, SME only needs ``probe_fn`` to do an end-to-end
    dry call and report success/failure.

    ``kind`` values:
      - ``"tool_call"``       — a generic tool-call surface (OpenAI
                                tool-calls, Anthropic tool-use, etc.)
      - ``"mcp_resource"``    — an MCP server method the client calls
                                over stdio/http
      - ``"claude_code_hook"``— a Claude Code hook (Stop, PreCompact,
                                UserPromptSubmit, SessionStart,
                                PreToolUse, PostToolUse)
      - ``"slash_command"``   — a harness-level slash command
      - ``"custom_action"``   — arbitrary shape; the adapter owns the
                                invocation semantics

    Future sub-tests (9a/9c/9d/9e/9f/9g) will need the schema/URI/hook-
    type info on top of ``probe_fn``; put them in ``properties`` for now.
    """

    name: str
    kind: str
    probe_fn: Callable[[], ProbeResult]
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


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

    def get_harness_manifest(self) -> list[HarnessDescriptor]:
        """Return the invocation surfaces this memory system exposes.

        Used by Category 9 (Harness Integration). Each descriptor describes
        one surface through which an external caller (a model, a hook, a
        tool) can reach the memory system. Systems that don't expose any
        harness surface — pure library APIs — return ``[]``.

        The current minimum-viable consumer (Cat 9b call-through success)
        only invokes ``probe_fn`` on each descriptor. Future sub-tests
        will need the ``kind`` + ``properties`` metadata to run model
        calls and compose with Cat 7.
        """
        return []

    # --- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        """Release any resources. Safe to call multiple times."""
