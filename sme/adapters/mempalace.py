"""MemPalace adapter for SME.

Reads a MemPalace installation and projects it as a graph for structural
analysis. Targets Mode B (diagnostic on the user's own palace) — does NOT
require a seeded corpus.

Architecture observed in milla-jovovich/mempalace 3.1.0:

- **ChromaDB** at ``palace_path`` (default ``~/.mempalace/palace``).
  Collection name is ``mempalace_drawers``. Each "drawer" is a chunk of
  verbatim text with metadata:
      wing, room, source_file, added_by, chunk_index, filed_at, source_mtime
  Note: ``hall`` is documented as standard metadata but is NOT populated by
  the project miner — it's only set in convo mining and manual API paths.
  The adapter reads hall if present and falls back to the room name.

- **SQLite knowledge graph** at a separate path (default
  ``~/.mempalace/knowledge_graph.sqlite3``). Two tables:
      entities(id, name, type, properties, created_at)
      triples(id, subject, predicate, object, valid_from, valid_to,
              confidence, source_closet, source_file, extracted_at)
  The KG is optional — not every MemPalace install has one. Adapter
  degrades gracefully.

Graph projection (for ``get_graph_snapshot``):

- Entity per wing (entity_type="wing")
- Entity per room (entity_type=f"room:{primary_hall or 'untyped'}")
  properties: wings (list), halls (list), drawer_count
- Entity per KG entity (entity_type=f"kg:{kg.type}")
- Edge room→wing (edge_type="member_of") for each (room, wing) pairing
- Edge wing↔wing (edge_type="tunnel") for each shared room, with
  ``via_room`` and ``hall`` in properties
- Edge kg_subject→kg_object (edge_type=predicate from the triple)

This follows MemPalace's own mental model from palace_graph.py: wings
are the structural units, rooms that appear in multiple wings are tunnels
between them. The KG entities/triples form a parallel semantic layer.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Optional

from sme.adapters.base import (
    Edge,
    Entity,
    HarnessDescriptor,
    ProbeResult,
    QueryResult,
    SMEAdapter,
)

log = logging.getLogger(__name__)


DEFAULT_COLLECTION_NAME = "mempalace_drawers"
DEFAULT_KG_PATH = os.path.expanduser("~/.mempalace/knowledge_graph.sqlite3")


class MemPalaceAdapter(SMEAdapter):
    """Schema-agnostic adapter for MemPalace's ChromaDB + optional SQLite KG.

    Parameters
    ----------
    db_path:
        Filesystem path to the palace directory (the ChromaDB persistent
        client directory). Named ``db_path`` for CLI compatibility with
        the ``--db`` flag; internally this is the MemPalace "palace_path".
    kg_path:
        Optional path to the SQLite knowledge graph file. If None, the
        adapter looks at ``~/.mempalace/knowledge_graph.sqlite3`` and
        skips the KG layer if the file doesn't exist.
    collection_name:
        ChromaDB collection name. Defaults to ``mempalace_drawers``.
    include_kg:
        If True (default), include KG entities and triples in the snapshot.
        Set False to get the structural-only (wings/rooms/tunnels) view.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        read_only: bool = True,  # accepted for CLI parity; MemPalace has no lock model
        kg_path: Optional[str | Path] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        include_kg: bool = True,
        include_drawers: bool = True,
        max_drawer_nodes: int = 10_000,
    ):
        import chromadb  # local import so sme loads without chromadb

        self._chromadb = chromadb
        self.db_path = str(db_path)
        self.collection_name = collection_name
        self.include_kg = include_kg
        self.include_drawers = include_drawers
        self.max_drawer_nodes = max_drawer_nodes
        self._read_only = read_only  # informational — ChromaDB doesn't lock

        self.kg_path = str(kg_path) if kg_path is not None else DEFAULT_KG_PATH

        log.info("opening MemPalace ChromaDB at %s", self.db_path)
        self._client = chromadb.PersistentClient(path=self.db_path)
        try:
            self._collection = self._client.get_collection(self.collection_name)
        except Exception as e:
            raise RuntimeError(
                f"could not open ChromaDB collection {self.collection_name!r} "
                f"at {self.db_path!r}: {e}. Is this a MemPalace palace? "
                f"Check with: mempalace --palace {self.db_path} status"
            ) from e

        self._kg_conn: Optional[sqlite3.Connection] = None

    # --- SMEAdapter required ------------------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "MemPalaceAdapter is diagnostic-only (Mode B). To seed a test "
            "palace, use MemPalace's own `mempalace init` and `mempalace mine` "
            "commands against a source directory. Mode A (benchmark against "
            "a seeded corpus) is a separate adapter path, not yet implemented."
        )

    def query(
        self,
        question: str,
        *,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        n_results: int = 10,
        route: bool = True,
    ) -> QueryResult:
        """Run a query through palace-structured retrieval.

        Condition B reference: the same ChromaDB collection the
        ``FlatBaselineAdapter`` uses, but with wing/room structural
        metadata honored. The ONLY difference from the flat condition
        is the ``where`` clause on the ChromaDB query. That isolates
        MemPalace's retrieval value to precisely its structural
        metadata contribution.

        When ``wing`` and ``room`` are both None (the default), the
        adapter auto-detects the wing from the query text using simple
        room-name overlap. This mirrors what a MemPalace MCP server
        session would do when the user asks a bare question with no
        explicit scoping — the palace-level benefit comes from
        whatever scoping the system can infer, not from telling it
        which wing to look in.

        We inline the ChromaDB search rather than depending on
        ``mempalace.searcher`` so sme-eval has no runtime dependency
        on the MemPalace package itself. The behavior matches
        ``mempalace.searcher.search_memories`` exactly.
        """
        # --- 1. Inferred wing/room scoping ------------------------
        # When the caller doesn't specify a wing or room, we derive
        # them from the query text using a lightweight lexical match
        # against the distinct rooms in the palace. This is what a
        # palace-structured retrieval pipeline would do in practice:
        # route the question to a specific topic before searching.
        where_clause: Optional[dict] = None
        inferred_path: list[str] = []
        if wing is None and room is None:
            if route:
                room_guess = self._infer_room(question)
                if room_guess:
                    where_clause = {"room": room_guess}
                    inferred_path.append(f"inferred room:{room_guess}")
            else:
                inferred_path.append("route=False (no metadata scoping)")
        elif wing and room:
            where_clause = {"$and": [{"wing": wing}, {"room": room}]}
            inferred_path.append(f"explicit wing:{wing}/room:{room}")
        elif wing:
            where_clause = {"wing": wing}
            inferred_path.append(f"explicit wing:{wing}")
        elif room:
            where_clause = {"room": room}
            inferred_path.append(f"explicit room:{room}")

        # --- 2. ChromaDB search -----------------------------------
        try:
            kwargs = {
                "query_texts": [question],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
            }
            if where_clause:
                kwargs["where"] = where_clause
            results = self._collection.query(**kwargs)
        except Exception as e:  # pragma: no cover
            return QueryResult(
                answer="",
                context_string="",
                error=f"INTERNAL: {e}",
                retrieval_path=inferred_path,
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
                retrieval_path=inferred_path,
            )

        # --- 3. Build context string -----------------------------
        # Format matches FlatBaselineAdapter's context_string so Cat 7
        # token counts are comparable. The wing/room prefix is the
        # extra context MemPalace adds over flat — it costs a few
        # tokens per hit but tells the downstream LLM where passages
        # came from, which is what the palace structure is supposed
        # to give you.
        context_parts: list[str] = []
        retrieved: list[Entity] = []
        for i, (doc, meta, doc_id, dist) in enumerate(
            zip(docs, metas or [{}] * len(docs), ids, dists)
        ):
            meta = meta or {}
            wing_name = meta.get("wing", "?")
            room_name = meta.get("room", "?")
            source = Path(meta.get("source_file", f"hit{i}")).name
            label = f"[{wing_name}/{room_name}] {source}"
            context_parts.append(f"[{i + 1}] {label}\n{doc}")
            retrieved.append(
                Entity(
                    id=f"drawer_hit:{doc_id}",
                    name=source,
                    entity_type=f"drawer:{room_name}",
                    properties={
                        "_table": "mempalace_hit",
                        "wing": wing_name,
                        "room": room_name,
                        "similarity": 1.0 - float(dist),
                        "source_file": meta.get("source_file", ""),
                    },
                )
            )

        context_string = "\n\n".join(context_parts)
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved,
            retrieval_path=inferred_path,
        )

    def _infer_room(self, question: str) -> Optional[str]:
        """Lightweight lexical routing: pick the room whose name
        best matches the query. Used when the caller doesn't scope
        the query explicitly. Returns None if no room dominates.

        This is deliberately minimal — the point is to model what
        "palace-structured retrieval" looks like without requiring
        an LLM classifier. A real MemPalace MCP session would use
        more sophisticated routing, but this is the honest floor."""
        # Get distinct rooms from the collection (cached via first call)
        if not hasattr(self, "_distinct_rooms_cache"):
            try:
                all_meta = self._collection.get(include=["metadatas"])
                rooms = {
                    ((m or {}).get("room") or "").strip()
                    for m in all_meta.get("metadatas", [])
                }
                rooms.discard("")
                rooms.discard("general")
                self._distinct_rooms_cache = sorted(rooms)
            except Exception:
                self._distinct_rooms_cache = []

        rooms = self._distinct_rooms_cache
        if not rooms:
            return None

        q_lower = question.lower()
        q_tokens = {
            t.strip(".,?!;:()[]\"'")
            for t in q_lower.split()
            if len(t) > 3
        }

        # Score each room by how many of its name tokens appear in the
        # query. Handles underscore/hyphen-separated room names.
        best_room = None
        best_score = 0
        for rm in rooms:
            rm_tokens = {
                t
                for t in rm.lower().replace("_", " ").replace("-", " ").split()
                if len(t) > 2
            }
            score = len(rm_tokens & q_tokens)
            if score > best_score:
                best_score = score
                best_room = rm

        # Require at least one token match or don't scope. Better to
        # return unfiltered results than to mis-route.
        return best_room if best_score >= 1 else None

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        entities: list[Entity] = []
        edges: list[Edge] = []

        # --- 1. Read every drawer's metadata --------------------------

        total = self._collection.count()
        log.info("palace has %d drawers", total)

        # room -> {wings: set, halls: set, drawer_count: int, dates: set}
        room_data: dict[str, dict] = defaultdict(
            lambda: {"wings": set(), "halls": set(), "drawer_count": 0, "dates": set()}
        )
        # Track distinct wings for entity creation
        wings_seen: set[str] = set()
        # Collect per-drawer records so we can project drawers as nodes.
        # Each entry: {id, wing, room, hall, source_file, chunk_index, ...}
        drawer_records: list[dict] = []

        offset = 0
        BATCH = 1000
        while offset < total:
            batch = self._collection.get(
                limit=BATCH, offset=offset, include=["metadatas"]
            )
            ids = batch.get("ids", [])
            metas = batch.get("metadatas", [])
            if not ids:
                break
            for drawer_id, meta in zip(ids, metas):
                meta = meta or {}
                wing = meta.get("wing") or ""
                room = meta.get("room") or ""
                hall = meta.get("hall") or ""  # often empty for project-mined palaces
                date = meta.get("filed_at") or meta.get("date") or ""
                if not wing:
                    continue
                wings_seen.add(wing)
                # Skip the "general" room for structural analysis — it's a
                # catch-all bucket that otherwise dominates the graph. Matches
                # palace_graph.build_graph's own filter.
                if room and room != "general":
                    d = room_data[room]
                    d["wings"].add(wing)
                    if hall:
                        d["halls"].add(hall)
                    if date:
                        d["dates"].add(date)
                    d["drawer_count"] += 1
                    drawer_records.append({
                        "id": drawer_id,
                        "wing": wing,
                        "room": room,
                        "hall": hall or "untyped",
                        "source_file": meta.get("source_file") or "",
                        "chunk_index": meta.get("chunk_index", 0),
                    })
            offset += len(ids)

        # --- 2. Entity per wing ------------------------------------------

        for wing in sorted(wings_seen):
            entities.append(
                Entity(
                    id=f"wing:{wing}",
                    name=wing,
                    entity_type="wing",
                    properties={"_table": "wing"},
                )
            )

        # --- 3. Entity per room ------------------------------------------

        for room, data in sorted(room_data.items()):
            primary_hall = (
                sorted(data["halls"])[0] if data["halls"] else "untyped"
            )
            entities.append(
                Entity(
                    id=f"room:{room}",
                    name=room,
                    entity_type=f"room:{primary_hall}",
                    properties={
                        "_table": "room",
                        "wings": sorted(data["wings"]),
                        "halls": sorted(data["halls"]),
                        "drawer_count": data["drawer_count"],
                    },
                )
            )

        # --- 4. Edges: room -> wing (member_of) --------------------------

        for room, data in sorted(room_data.items()):
            for wing in sorted(data["wings"]):
                edges.append(
                    Edge(
                        source_id=f"room:{room}",
                        target_id=f"wing:{wing}",
                        edge_type="member_of",
                        properties={
                            "_table": "structural",
                            "drawer_count": data["drawer_count"],
                        },
                    )
                )

        # --- 5. Edges: wing <-> wing (tunnel via shared room) -----------

        for room, data in sorted(room_data.items()):
            wings = sorted(data["wings"])
            if len(wings) >= 2:
                for i, wa in enumerate(wings):
                    for wb in wings[i + 1:]:
                        edges.append(
                            Edge(
                                source_id=f"wing:{wa}",
                                target_id=f"wing:{wb}",
                                edge_type="tunnel",
                                properties={
                                    "_table": "structural",
                                    "via_room": room,
                                    "hall": (
                                        sorted(data["halls"])[0]
                                        if data["halls"]
                                        else ""
                                    ),
                                    "drawer_count": data["drawer_count"],
                                },
                            )
                        )

        # --- 5b. Drawer entities + chunk-sibling edges ------------------
        # Drawers are the individual ~800-char text chunks. Including them
        # as nodes gives SME the content-layer view a star-topology
        # wing/room graph can't provide. For single-wing KNOWLEDGE_CORPUS
        # palaces (the common case) this is what surfaces actual structural
        # signal: which topics are densely written, which source files have
        # many chunks, which rooms cluster together via shared files.

        if self.include_drawers and len(drawer_records) <= self.max_drawer_nodes:
            # Entity per drawer, entity_type keyed on (hall, room) so
            # Cat 8 can see hall usage.
            source_file_to_drawers: dict[str, list[str]] = defaultdict(list)

            for rec in drawer_records:
                drawer_node_id = f"drawer:{rec['id']}"
                entities.append(
                    Entity(
                        id=drawer_node_id,
                        name=Path(rec["source_file"]).name or rec["id"],
                        entity_type=f"drawer:{rec['hall']}",
                        properties={
                            "_table": "drawer",
                            "wing": rec["wing"],
                            "room": rec["room"],
                            "hall": rec["hall"],
                            "source_file": rec["source_file"],
                            "chunk_index": rec["chunk_index"],
                        },
                    )
                )
                # Filed-in edge: drawer -> room
                edges.append(
                    Edge(
                        source_id=drawer_node_id,
                        target_id=f"room:{rec['room']}",
                        edge_type="filed_in",
                        properties={"_table": "structural"},
                    )
                )
                if rec["source_file"]:
                    source_file_to_drawers[rec["source_file"]].append(drawer_node_id)

            # Sibling edges: chunks from the same source file are linked
            # to each other. This produces tight local clusters for long
            # documents and lets Louvain see file-level community structure.
            for src, sib_ids in source_file_to_drawers.items():
                if len(sib_ids) < 2:
                    continue
                # Star topology within a file: first chunk linked to all
                # others. Keeps edge count linear in chunk count (N-1 per file)
                # instead of quadratic.
                hub = sib_ids[0]
                for other in sib_ids[1:]:
                    edges.append(
                        Edge(
                            source_id=hub,
                            target_id=other,
                            edge_type="same_file",
                            properties={
                                "_table": "structural",
                                "source_file": src,
                            },
                        )
                    )
        elif self.include_drawers and len(drawer_records) > self.max_drawer_nodes:
            log.warning(
                "palace has %d drawers > max_drawer_nodes=%d; "
                "drawer-level projection skipped. Raise --max-drawer-nodes "
                "to include them.",
                len(drawer_records),
                self.max_drawer_nodes,
            )

        # --- 6. KG entities and triples (optional) -----------------------

        if self.include_kg and os.path.exists(self.kg_path):
            log.info("reading KG from %s", self.kg_path)
            try:
                kg_entities, kg_edges = self._read_kg()
                entities.extend(kg_entities)
                edges.extend(kg_edges)
            except Exception as e:  # pragma: no cover
                log.warning("failed to read KG at %s: %s", self.kg_path, e)
        else:
            if self.include_kg:
                log.info(
                    "no KG at %s — skipping (this palace was project-mined "
                    "without triple extraction)",
                    self.kg_path,
                )

        return entities, edges

    def _read_kg(self) -> tuple[list[Entity], list[Edge]]:
        if self._kg_conn is None:
            self._kg_conn = sqlite3.connect(
                self.kg_path, timeout=5, check_same_thread=False
            )
            self._kg_conn.row_factory = sqlite3.Row

        ents: list[Entity] = []
        edges: list[Edge] = []

        # Entities table
        try:
            rows = self._kg_conn.execute(
                "SELECT id, name, type, properties, created_at FROM entities"
            ).fetchall()
            for r in rows:
                try:
                    props = json.loads(r["properties"] or "{}")
                except Exception:
                    props = {}
                props["_table"] = "kg_entity"
                props["_created_at"] = r["created_at"]
                ents.append(
                    Entity(
                        id=f"kg:{r['id']}",
                        name=r["name"],
                        entity_type=f"kg:{r['type'] or 'unknown'}",
                        properties=props,
                    )
                )
        except sqlite3.OperationalError:
            pass

        # Triples table
        try:
            rows = self._kg_conn.execute(
                "SELECT subject, predicate, object, valid_from, valid_to, "
                "confidence, source_closet, source_file FROM triples"
            ).fetchall()
            for r in rows:
                edges.append(
                    Edge(
                        source_id=f"kg:{r['subject']}",
                        target_id=f"kg:{r['object']}",
                        edge_type=r["predicate"] or "kg_related",
                        properties={
                            "_table": "kg_triple",
                            "_created_at": r["valid_from"],
                            "valid_to": r["valid_to"],
                            "confidence": r["confidence"],
                            "source_closet": r["source_closet"],
                            "source_file": r["source_file"],
                        },
                    )
                )
        except sqlite3.OperationalError:
            pass

        return ents, edges

    # --- Cat 8 ontology source ----------------------------------------

    def get_ontology_source(self) -> dict:
        """MemPalace documents wings/rooms/halls/tunnels/closets/drawers.
        Returns a readme-derived ontology description for Cat 8."""
        return {
            "type": "readme",
            "schema": [
                {
                    "kind": "structural",
                    "entities": ["wing", "room", "hall", "tunnel", "closet", "drawer"],
                },
                {
                    "kind": "hall_vocabulary",
                    "values": [
                        "facts",
                        "events",
                        "discoveries",
                        "preferences",
                        "advice",
                    ],
                },
            ],
            "documentation": (
                "MemPalace organizes memories into Wings (projects or people), "
                "Rooms (topics within a wing), Halls (5 standard categories: "
                "facts, events, discoveries, preferences, advice), and Tunnels "
                "(auto-detected when the same room appears in 2+ wings). "
                "Drawers are verbatim ~800-char chunks. Closets are summaries "
                "with references to drawers. KG entities and temporal triples "
                "live in a separate SQLite store."
            ),
        }

    # --- Category 9 harness manifest ----------------------------------

    def get_harness_manifest(self) -> list[HarnessDescriptor]:
        """Declare MemPalace's MCP-style invocation surfaces for Cat 9.

        The adapter itself talks to ChromaDB + SQLite directly — it does
        not spawn the actual mempalace MCP server process. Each probe
        here exercises the same code path that the corresponding MCP
        tool does on the live server, so a probe failure here predicts
        an MCP-side failure on that tool. A probe success does NOT
        guarantee the MCP stdio/JSON-RPC layer is wired correctly —
        that's a separate concern for a future 9f (per-harness
        portability) implementation that actually spawns the server.
        """
        return [
            HarnessDescriptor(
                name="mempalace_search",
                kind="mcp_resource",
                probe_fn=self._probe_search,
                description="MCP tool: semantic search over drawers",
                properties={
                    "tool_name": "mempalace_search",
                    "underlying_call": "query()",
                },
            ),
            HarnessDescriptor(
                name="mempalace_graph_stats",
                kind="mcp_resource",
                probe_fn=self._probe_graph_snapshot,
                description="MCP tool: wing/room/tunnel graph summary",
                properties={
                    "tool_name": "mempalace_graph_stats",
                    "underlying_call": "get_graph_snapshot()",
                },
            ),
            HarnessDescriptor(
                name="mempalace_kg_query",
                kind="mcp_resource",
                probe_fn=self._probe_kg_read,
                description="MCP tool: knowledge-graph triple lookup",
                properties={
                    "tool_name": "mempalace_kg_query",
                    "underlying_call": "_read_kg()",
                    "optional": True,  # skipped gracefully if KG absent
                },
            ),
        ]

    def _probe_search(self) -> ProbeResult:
        """Call query() with a neutral probe string, check shape."""
        import time

        start = time.perf_counter()
        try:
            result = self.query("probe query test")
        except Exception as exc:  # noqa: BLE001 — adapter probe, all errors captured
            return ProbeResult(
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
        latency = (time.perf_counter() - start) * 1000
        if result.error:
            return ProbeResult(success=False, latency_ms=latency, error=result.error)
        # "Success" means the machinery returned a QueryResult with
        # context_string populated. Zero hits is still a successful
        # call-through — that's a retrieval-quality question (Cat 1),
        # not a harness-integration question (Cat 9b).
        return ProbeResult(
            success=True,
            latency_ms=latency,
            output=f"context_string length={len(result.context_string or '')}",
        )

    def _probe_graph_snapshot(self) -> ProbeResult:
        import time

        start = time.perf_counter()
        try:
            entities, edges = self.get_graph_snapshot()
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
        return ProbeResult(
            success=True,
            latency_ms=(time.perf_counter() - start) * 1000,
            output=f"entities={len(entities)} edges={len(edges)}",
        )

    def _probe_kg_read(self) -> ProbeResult:
        """Probe the KG read path. Graceful no-op if KG file absent."""
        import time

        start = time.perf_counter()
        if not (self.kg_path and os.path.isfile(self.kg_path)):
            # No KG file — the corresponding MCP tool would return an
            # empty result, not crash. Report success so we don't
            # penalize palaces without a KG.
            return ProbeResult(
                success=True,
                latency_ms=(time.perf_counter() - start) * 1000,
                output=f"kg file not present at {self.kg_path!r}; probe skipped",
            )
        try:
            entities, edges = self._read_kg()
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
        return ProbeResult(
            success=True,
            latency_ms=(time.perf_counter() - start) * 1000,
            output=f"kg_entities={len(entities)} kg_triples={len(edges)}",
        )

    # --- Lifecycle ----------------------------------------------------

    def close(self) -> None:
        if self._kg_conn is not None:
            try:
                self._kg_conn.close()
            except Exception:
                pass
        self._kg_conn = None
        # ChromaDB PersistentClient has no explicit close
        self._collection = None
        self._client = None
