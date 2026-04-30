"""Regression tests for MemPalaceAdapter.

ChromaDB can legitimately return ``None`` in the ``metadatas`` list for
drawers that were added without metadata, or whose metadata got orphaned
during compaction. This isn't a corruption state — it's expected-rare
behavior on large palaces over time. The adapter's ChromaDB iteration
loops must guard against ``None`` rather than calling ``.get`` on it.

These tests use a stub collection so they don't need a real ChromaDB
install — the adapter's bug is purely in how it consumes batches, not
in ChromaDB itself.
"""

from __future__ import annotations

from sme.adapters.mempalace import MemPalaceAdapter


class _StubCollection:
    """Mimics the chromadb Collection surface the adapter touches.

    Returns batches with at least one ``None`` metadata, which is the
    state that crashed get_graph_snapshot() in production palaces.
    """

    def __init__(self, rows: list[tuple[str, dict | None]]):
        self._rows = rows

    def count(self) -> int:
        return len(self._rows)

    def get(self, *, limit: int, offset: int, include):
        page = self._rows[offset : offset + limit]
        return {
            "ids": [r[0] for r in page],
            "metadatas": [r[1] for r in page],
        }

    def query(self, **kwargs):  # unused here, but query() also has a guard
        return {"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]}


def _adapter_with_rows(rows):
    """Build an adapter without going through __init__ (no chromadb dep)."""
    a = MemPalaceAdapter.__new__(MemPalaceAdapter)
    a._collection = _StubCollection(rows)
    a.include_drawers = True
    a.include_kg = False
    a.max_drawer_nodes = 10_000
    a.kg_path = "/nonexistent"
    return a


def test_get_graph_snapshot_tolerates_none_metadata():
    """A drawer with metadata=None must not crash the snapshot loop.

    Reproduces the AttributeError reported by jphein on a 165K-drawer
    production palace. The None drawer should be silently skipped (it
    has no wing, so it can't participate in the structural graph),
    and the rest of the palace should project normally.
    """
    rows = [
        ("d1", {"wing": "work", "room": "projects"}),
        ("d2", None),  # the orphan that used to crash
        ("d3", {"wing": "work", "room": "projects"}),
        ("d4", {"wing": "personal", "room": "projects"}),  # tunnel via projects
    ]
    adapter = _adapter_with_rows(rows)

    entities, edges = adapter.get_graph_snapshot()

    wing_ids = {e.id for e in entities if e.entity_type == "wing"}
    assert wing_ids == {"wing:work", "wing:personal"}

    # The two real wings share "projects" → one tunnel edge.
    tunnels = [e for e in edges if e.edge_type == "tunnel"]
    assert len(tunnels) == 1
    assert tunnels[0].properties["via_room"] == "projects"


def test_get_graph_snapshot_all_none_metadata_is_empty_not_crash():
    """A pathological palace where every drawer has None metadata
    should produce an empty graph, not raise."""
    rows = [("d1", None), ("d2", None), ("d3", None)]
    adapter = _adapter_with_rows(rows)

    entities, edges = adapter.get_graph_snapshot()

    assert entities == []
    assert edges == []
