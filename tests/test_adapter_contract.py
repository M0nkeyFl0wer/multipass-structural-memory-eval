"""SMEAdapter conformance testkit (M0nkeyFl0wer/multipass-structural-memory-eval#8).

Parametric contract tests verifying every registered adapter conforms to the
``sme.adapters.base.SMEAdapter`` ABC: ``query`` returns a typed
``QueryResult``, ``get_graph_snapshot`` is internally consistent, ``ingest_corpus``
accepts a list of dicts (or raises ``NotImplementedError``), and the optional
``get_harness_manifest`` returns a list when present.

Existing per-adapter unit tests (``test_familiar_adapter.py``,
``test_mempalace_daemon_adapter.py`` etc.) verify HTTP deserialization and
adapter-specific behavior. This module verifies *the contract*.

To opt a new adapter in, register a factory at the bottom under
``ADAPTER_FACTORIES``. A factory takes a ``tmp_path`` and returns a constructed
adapter (or skips, via ``pytest.skip``, when its environment is missing).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from sme.adapters.base import (
    Edge,
    Entity,
    HarnessDescriptor,
    QueryResult,
    SMEAdapter,
)


# --- MockAdapter ------------------------------------------------------
#
# Minimal in-memory SMEAdapter used as a contract reference. Concrete enough
# that substring queries return real hits and the graph snapshot has a
# self-consistent entity/edge set.


class MockAdapter(SMEAdapter):
    """In-memory SMEAdapter for contract testing.

    Stores ingested corpus as a list of dicts. ``query`` does substring
    matching over ``text``; ``get_graph_snapshot`` returns a simple
    two-node, one-edge graph.
    """

    def __init__(self) -> None:
        self._corpus: list[dict] = []

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        self._corpus.extend(corpus)
        return {
            "entities_created": len(corpus),
            "edges_created": 0,
            "errors": [],
            "warnings": [],
        }

    def query(self, question: str, n_results: int = 5) -> QueryResult:
        q = (question or "").lower()
        hits = [d for d in self._corpus if q and q in str(d.get("text", "")).lower()]
        hits = hits[:n_results]
        ctx = "\n".join(str(d.get("text", "")) for d in hits)
        entities = [
            Entity(
                id=str(d.get("id", f"mock:{i}")),
                name=str(d.get("id", f"mock:{i}")),
                entity_type="chunk",
                properties={"text": d.get("text", "")},
            )
            for i, d in enumerate(hits)
        ]
        return QueryResult(
            answer=ctx,
            context_string=ctx,
            retrieved_entities=entities,
            retrieval_path=["mock", f"q={question}"],
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        # Trivial but internally consistent: edge endpoints both exist.
        entities = [
            Entity(id="a", name="A", entity_type="topic"),
            Entity(id="b", name="B", entity_type="topic"),
        ]
        edges = [Edge(source_id="a", target_id="b", edge_type="related_to")]
        return entities, edges

    def get_harness_manifest(self) -> list[HarnessDescriptor]:
        return []


# --- Adapter factories ------------------------------------------------
#
# Each factory builds one adapter. Network-dependent adapters use ``pytest.skip``
# from within the factory when their environment is unavailable; that keeps the
# parametrize list flat and the skip reason visible in pytest output.


AdapterFactory = Callable[[Path], SMEAdapter]


def _mock_factory(tmp_path: Path) -> SMEAdapter:
    return MockAdapter()


def _flat_baseline_factory(tmp_path: Path) -> SMEAdapter:
    """FlatBaselineAdapter over an empty ChromaDB collection in tmp_path."""
    try:
        import chromadb
    except ImportError:  # pragma: no cover — chromadb is a project dep
        pytest.skip("chromadb not installed")

    from sme.adapters.flat_baseline import FlatBaselineAdapter

    db_path = tmp_path / "chroma"
    db_path.mkdir()
    client = chromadb.PersistentClient(path=str(db_path))
    client.create_collection("mempalace_drawers")
    # Drop the construction-time handle so the adapter opens its own.
    del client
    return FlatBaselineAdapter(db_path=str(db_path))


def _full_context_factory(tmp_path: Path) -> SMEAdapter:
    """FullContextAdapter over a tiny tmp vault."""
    from sme.conditions.full_context import FullContextAdapter

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# note\nhello world\n", encoding="utf-8")
    return FullContextAdapter(vault)


# Register adapters here. Keep IDs stable — they show in pytest output.
ADAPTER_FACTORIES: dict[str, AdapterFactory] = {
    "mock": _mock_factory,
    "flat_baseline": _flat_baseline_factory,
    "full_context": _full_context_factory,
}


@pytest.fixture(params=sorted(ADAPTER_FACTORIES.keys()))
def adapter(request: pytest.FixtureRequest, tmp_path: Path) -> SMEAdapter:
    factory = ADAPTER_FACTORIES[request.param]
    return factory(tmp_path)


# --- Contract tests ---------------------------------------------------


def test_is_sme_adapter_subclass(adapter: SMEAdapter) -> None:
    assert isinstance(adapter, SMEAdapter)


def test_query_returns_QueryResult(adapter: SMEAdapter) -> None:
    result = adapter.query("test", n_results=3)
    assert isinstance(result, QueryResult)
    assert isinstance(result.context_string, str)
    assert isinstance(result.retrieval_path, list)
    assert all(isinstance(p, (str, int, float)) for p in result.retrieval_path)
    assert isinstance(result.retrieved_entities, list)
    assert all(isinstance(e, Entity) for e in result.retrieved_entities)
    assert isinstance(result.retrieved_edges, list)
    assert all(isinstance(e, Edge) for e in result.retrieved_edges)
    assert isinstance(result.answer, str)
    # ``error`` is Optional[str]; type, not presence.
    assert result.error is None or isinstance(result.error, str)
    # Overlay fields (2026-06) — safe defaults, backward compatible
    assert isinstance(result.latency_ms, (int, float))
    assert result.latency_ms >= 0
    assert isinstance(result.interaction_turns, int)
    assert result.interaction_turns >= 1


def test_query_without_n_results_kwarg(adapter: SMEAdapter) -> None:
    """The ABC signature is ``query(question)``; ``n_results`` is an
    adapter-level extension. The minimum contract is that ``query(question)``
    alone returns a ``QueryResult``."""
    result = adapter.query("test")
    assert isinstance(result, QueryResult)


def test_graph_snapshot_returns_typed_pair(adapter: SMEAdapter) -> None:
    snapshot = adapter.get_graph_snapshot()
    assert isinstance(snapshot, tuple)
    assert len(snapshot) == 2
    entities, edges = snapshot
    assert isinstance(entities, list)
    assert isinstance(edges, list)
    assert all(isinstance(e, Entity) for e in entities)
    assert all(isinstance(e, Edge) for e in edges)


def test_graph_snapshot_internally_consistent(adapter: SMEAdapter) -> None:
    """Every edge's source/target id must exist in the entity list.

    Adapters with no graph return ``([], [])`` — vacuously consistent.
    """
    entities, edges = adapter.get_graph_snapshot()
    entity_ids = {e.id for e in entities}
    for edge in edges:
        assert edge.source_id in entity_ids, (
            f"edge source_id {edge.source_id!r} not in entity ids"
        )
        assert edge.target_id in entity_ids, (
            f"edge target_id {edge.target_id!r} not in entity ids"
        )


def test_ingest_corpus_accepts_list_of_dicts(adapter: SMEAdapter) -> None:
    """``ingest_corpus`` must either succeed with a result dict or raise
    ``NotImplementedError`` — both are valid per the ABC. AttributeError,
    TypeError, or KeyError on the canonical shape would be a contract bug.
    """
    corpus = [{"id": "x", "text": "y"}]
    try:
        result = adapter.ingest_corpus(corpus)
    except NotImplementedError:
        return
    assert isinstance(result, dict)
    for key in ("entities_created", "edges_created", "errors", "warnings"):
        assert key in result, f"ingest result missing required key {key!r}"
    assert isinstance(result["entities_created"], int)
    assert isinstance(result["edges_created"], int)
    assert isinstance(result["errors"], list)
    assert isinstance(result["warnings"], list)


def test_get_harness_manifest_returns_list(adapter: SMEAdapter) -> None:
    """``get_harness_manifest`` defaults to ``[]`` on the ABC. Anything
    that overrides it must still return a list of ``HarnessDescriptor``.
    """
    manifest = adapter.get_harness_manifest()
    assert isinstance(manifest, list)
    assert all(isinstance(d, HarnessDescriptor) for d in manifest)


def test_get_ontology_source_returns_typed_dict(adapter: SMEAdapter) -> None:
    """Optional method with a sensible default on the ABC. When present,
    must return a dict with ``type``, ``schema``, ``documentation``."""
    src = adapter.get_ontology_source()
    assert isinstance(src, dict)
    assert src.get("type") in {"declared", "readme", "inferred"}
    assert isinstance(src.get("schema"), list)
    assert isinstance(src.get("documentation"), str)


def test_close_is_idempotent(adapter: SMEAdapter) -> None:
    """``close`` is part of the lifecycle contract and must tolerate
    being called more than once."""
    adapter.close()
    adapter.close()
