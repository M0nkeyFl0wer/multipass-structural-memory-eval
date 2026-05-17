"""LadybugDB adapter for SME.

Reads from any LadybugDB `.ldb` database via real_ladybug. Schema-agnostic:
the adapter introspects node and relationship tables at connection time
using CALL SHOW_TABLES(), CALL TABLE_INFO(table), and
CALL SHOW_CONNECTION(rel_table), then builds projection queries
dynamically.

Supports two schema styles observed in the wild:

1. **Consolidated edge tables** (knowledge-corpus pattern): a handful of
   rel tables like ENTITY_TO_ENTITY with an `edge_type` property that
   discriminates the semantic type (SUPPORTS, CONTRADICTS, IMPLEMENTS,
   etc.). One table, many edge types.

2. **Per-type edge tables** (narrative-graph pattern): many rel tables,
   one per semantic type (ADVOCATES_FOR, FRAMES_AS, INFLUENCED_BY, ...),
   where the table name itself IS the edge type.

Auto-detects which style each rel table uses by checking for an
`edge_type` column; falls back to the table name when absent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


# Tables we skip by default because they're operational / logging
# infrastructure, not part of the knowledge layer.
INFRASTRUCTURE_TABLES = {
    "IndexLog",
    "RetrievalLog",
    "TraversalLog",
    "SessionCache",
    "EnrichmentPattern",
    "LifecycleEvent",
}

# Preferred column names when building a node projection. The first
# match in the table's schema wins.
NAME_COLUMN_CANDIDATES = ("name", "title", "label", "text")
TYPE_COLUMN_CANDIDATES = ("entity_type", "node_type", "type", "category", "note_type")

# When an edge table has this column, the row's value is used as the
# semantic edge_type. Otherwise the table name is used.
EDGE_TYPE_DISCRIMINATOR = "edge_type"


class LadybugDBAdapter(SMEAdapter):
    """Schema-agnostic adapter for LadybugDB-backed memory systems."""

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        *,
        read_only: bool = True,
        buffer_pool_size: Optional[int] = None,
        include_node_tables: Optional[Iterable[str]] = None,
        include_edge_tables: Optional[Iterable[str]] = None,
        auto_discover: bool = False,
        skip_infrastructure: bool = True,
        api_url: Optional[str] = None,
        default_query_mode: str = "hybrid",
        api_timeout: float = 120.0,
        vault_path: Optional[str | Path] = None,
    ):
        """Open a LadybugDB file and/or wire up an HTTP-backed search API.

        Two independent access paths:

        * **File mode** (``db_path`` set): opens the .ldb directly via
          real_ladybug. Required for ``get_graph_snapshot()``. Blocked by
          writer locks — use a backup copy when the target has a live
          daemon or API server attached.
        * **API mode** (``api_url`` set): wires ``query()`` to a running
          HTTP search server (POSTs to ``{api_url}/search``). Required
          for the retrieval benchmark on a live graph. Does not need the
          file to be unlocked.

        Either or both can be set. If only ``db_path`` is given,
        ``query()`` uses direct Cypher file access. Set both for full
        Condition B support with content retrieval.

        Args:
            db_path: path to the .ldb file (optional in API mode).
            read_only: open in read-only mode (recommended).
            buffer_pool_size: LadybugDB buffer pool size in bytes.
            include_node_tables: explicit node table list. If None and
                auto_discover is False, defaults to known structural
                tables (Entity, Note, Document, ...).
            include_edge_tables: explicit edge table list. If None and
                auto_discover is False, defaults to every non-empty
                rel table discovered on the DB.
            auto_discover: if True, include every non-empty NODE and
                non-empty REL table found on the DB.
            skip_infrastructure: drop operational tables (logs, caches)
                from auto-discovery.
            api_url: HTTP base URL for a compatible search server (e.g.
                "http://localhost:7720"). When set, query() POSTs to
                ``{api_url}/search`` with {q, limit, mode} and builds
                a QueryResult from the SearchResultItem response.
            default_query_mode: "semantic" | "hybrid" | "graph" | "path".
                Systems exposing all four can use "hybrid" as the full
                pipeline (vector + FTS + graph traversal) — the right
                default for a Condition B measurement — and "semantic"
                for Condition C (structure disabled).
            api_timeout: per-request HTTP timeout in seconds.
            vault_path: path to a vault of markdown notes. When provided,
                the adapter builds a ``note_id -> (relative_path, content)``
                index at init time and uses it to retrieve full note content
                during file-mode queries, enabling Condition B without a
                running HTTP API.
        """
        self.db_path = str(db_path) if db_path is not None else None
        self.api_url = api_url.rstrip("/") if api_url else None
        self.vault_path = str(vault_path) if vault_path is not None else None
        self.default_query_mode = default_query_mode
        self.api_timeout = api_timeout
        self.skip_infrastructure = skip_infrastructure

        # Save raw user-provided table filters for API mode (before
        # _resolve_*_selection runs, which depends on file-mode schema
        # discovery and returns empty when the file isn't opened).
        self._explicit_node_tables = (
            tuple(include_node_tables) if include_node_tables else None
        )
        self._explicit_edge_tables = (
            tuple(include_edge_tables) if include_edge_tables else None
        )

        # --- Vault content index (optional, for file-mode Condition B) ---
        # note_id -> (relative_path, content) built at init from frontmatter
        self._vault_index: dict[str, tuple[str, str]] = {}
        if self.vault_path is not None:
            self._build_vault_index()

        if self.db_path is None and self.api_url is None:
            raise ValueError(
                "LadybugDBAdapter needs either db_path (file mode) or "
                "api_url (API mode) or both. Neither provided."
            )

        # --- File mode init (optional) ----------------------------

        self._db = None
        self._conn = None
        self._node_tables: list[str] = []
        self._rel_tables: list[str] = []
        self._node_columns: dict[str, list[tuple[str, str]]] = {}
        self._rel_columns: dict[str, list[tuple[str, str]]] = {}
        self._rel_connections: dict[str, tuple[str, str]] = {}

        if self.db_path is not None:
            import real_ladybug as lb  # local import so sme loads without lb

            self._lb = lb
            db_kwargs = {"read_only": read_only}
            if buffer_pool_size is not None:
                db_kwargs["buffer_pool_size"] = buffer_pool_size

            log.info(
                "opening LadybugDB at %s (read_only=%s)", self.db_path, read_only
            )
            self._db = lb.Database(self.db_path, **db_kwargs)
            self._conn = lb.Connection(self._db)

            # Discover schema
            self._node_tables, self._rel_tables = self._discover_tables()
            for table in self._node_tables:
                self._node_columns[table] = self._table_columns(table)
            for table in self._rel_tables:
                self._rel_columns[table] = self._table_columns(table)
                self._rel_connections[table] = self._rel_connection(table)

        # Decide which tables to actually include
        resolved_nodes = list(self._resolve_node_selection(include_node_tables, auto_discover))
        # Prioritize Entity table for better semantic matching
        if 'Entity' in resolved_nodes:
            resolved_nodes.remove('Entity')
            resolved_nodes.insert(0, 'Entity')
        self.include_node_tables = tuple(resolved_nodes)
        self.include_edge_tables = tuple(
            self._resolve_edge_selection(include_edge_tables, auto_discover)
        )

        log.info(
            "schema: %d node tables, %d rel tables discovered; "
            "including %d nodes, %d edges",
            len(self._node_tables),
            len(self._rel_tables),
            len(self.include_node_tables),
            len(self.include_edge_tables),
        )

    # --- SMEAdapter required methods -----------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "LadybugDBAdapter does not support ingest_corpus yet. "
            "For the smoke test we read an existing graph; to seed a "
            "fresh corpus, implement this against the target project's "
            "indexer pipeline or use a dedicated benchmark database."
        )

    def query(
        self,
        question: str,
        *,
        n_results: int = 10,
        mode: Optional[str] = None,
        route: bool = True,
    ) -> QueryResult:
        """Query the graph via an HTTP API.

        Targets a ``/search`` endpoint that takes ``{q, limit, mode}``
        and returns ``SearchResultItem[]``. The ``mode`` parameter maps
        directly to the server's retrieval pipeline mode:

        * ``semantic``  — vector similarity only (Condition C for
                          typed-graph systems: no graph traversal)
        * ``hybrid``    — vector + FTS + graph traversal (Condition B,
                          the full pipeline)
        * ``graph``     — graph traversal only, no embeddings
        * ``path``      — path-based traversal ranking

        When ``route=False``, this adapter downgrades to ``semantic``
        mode regardless of the ``mode`` kwarg. That gives the Cat 2c /
        Cat 7 scorers a consistent way to isolate the structural
        contribution across adapters.
        """
        if self.api_url is None:
            if self._conn is None:
                return QueryResult(
                    answer="",
                    context_string="",
                    error=(
                        "NO_API_URL: LadybugDBAdapter was constructed without "
                        "an api_url, and db_path was not provided or could not "
                        "be opened."
                    ),
                )
            return self._file_query(question, n_results=n_results, mode=mode, route=route)

        import json as _json
        import urllib.error
        import urllib.request

        # Resolve mode: route=False forces semantic (no graph),
        # otherwise use the caller's mode or fall back to default.
        chosen_mode = (
            "semantic" if not route else (mode or self.default_query_mode)
        )

        payload = {
            "q": question,
            "limit": n_results,
            "mode": chosen_mode,
        }

        try:
            req = urllib.request.Request(
                f"{self.api_url}/search",
                data=_json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                body = resp.read().decode("utf-8")
            hits = _json.loads(body)
        except urllib.error.HTTPError as e:
            return QueryResult(
                answer="",
                context_string="",
                error=f"HTTP {e.code}: {e.reason}",
                retrieval_path=[f"mode={chosen_mode}"],
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return QueryResult(
                answer="",
                context_string="",
                error=f"CONNECTION: {e}",
                retrieval_path=[f"mode={chosen_mode}"],
            )
        except Exception as e:  # pragma: no cover
            return QueryResult(
                answer="",
                context_string="",
                error=f"INTERNAL: {e}",
                retrieval_path=[f"mode={chosen_mode}"],
            )

        if not isinstance(hits, list):
            err = (
                hits.get("detail")
                if isinstance(hits, dict)
                else "unexpected response"
            )
            return QueryResult(
                answer="",
                context_string="",
                error=f"API_ERROR: {err}",
                retrieval_path=[f"mode={chosen_mode}"],
            )

        if not hits:
            return QueryResult(
                answer="",
                context_string="",
                error="NO_RESULTS",
                retrieval_path=[f"mode={chosen_mode}"],
            )

        context_parts: list[str] = []
        retrieved: list[Entity] = []
        for i, hit in enumerate(hits):
            path = hit.get("path") or hit.get("note_id") or f"hit{i}"
            source_label = Path(str(path)).name if path else f"hit{i}"
            text = hit.get("text", "") or ""
            score = hit.get("score", 0.0)

            context_parts.append(f"[{i + 1}] {source_label}\n{text}")
            retrieved.append(
                Entity(
                    id=f"chunk:{hit.get('chunk_id', f'hit{i}')}",
                    name=source_label,
                    entity_type="chunk",
                    properties={
                        "_table": "api_search_hit",
                        "note_id": hit.get("note_id"),
                        "path": path,
                        "score": score,
                        "weight": hit.get("weight"),
                        "score_breakdown": hit.get("score_breakdown", {}),
                    },
                )
            )

        context_string = "\n\n".join(context_parts)
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved,
            retrieval_path=[f"mode={chosen_mode}"],
        )

    def _file_query(
        self,
        question: str,
        *,
        n_results: int = 10,
        mode: Optional[str] = None,
        route: bool = True,
    ) -> QueryResult:
        """Query the graph via direct Cypher against the open .ldb file.

        Modes:
        - semantic: full-text search on node names + text properties,
          no graph traversal. Mirrors Condition C for typed-graph systems.
        - hybrid: FTS + graph-proximity (first hop from FTS-matched nodes).
          Condition B for this adapter.
        - graph: graph-traversal-only, no FTS. Uses the graph structure
          to find relevant nodes.
        - path: path-based ranking from query terms as starting points.
        """
        chosen_mode = (
            "semantic" if not route else (mode or self.default_query_mode)
        )

        if chosen_mode == "semantic":
            return self._file_query_semantic(question, n_results)
        elif chosen_mode == "hybrid":
            return self._file_query_hybrid(question, n_results)
        elif chosen_mode == "graph":
            return self._file_query_graph(question, n_results)
        elif chosen_mode == "path":
            return self._file_query_path(question, n_results)
        else:
            return QueryResult(
                answer="",
                context_string="",
                error=f"UNKNOWN_MODE: {chosen_mode}",
                retrieval_path=[f"mode={chosen_mode}"],
            )

    def _cypher_contains(self, col: str, term: str) -> str:
        escaped = term.replace('"', '\\"')
        return f'toLower({col}) CONTAINS toLower("{escaped}")'

    def _build_vault_index(self) -> None:
        """Build note_id -> (relative_path, content) index from vault markdown files."""
        import glob as _glob
        import os as _os

        vault_base = self.vault_path
        count = 0
        for md_file in _glob.glob(_os.path.join(vault_base, "**/*.md"), recursive=True):
            try:
                with open(md_file, encoding="utf-8") as f:
                    raw = f.read()
            except Exception:
                continue
            if not raw.lstrip().startswith("---"):
                continue
            try:
                end = raw.index("---", 3)
                frontmatter = raw[3:end]
                note_id = None
                for line in frontmatter.split("\n"):
                    if line.startswith("note_id:"):
                        note_id = line.split(":", 1)[1].strip()
                        break
                if not note_id:
                    continue
                # Compute relative path for display
                rel = _os.path.relpath(md_file, vault_base)
                # Strip frontmatter + blank line to get actual content
                body = raw[end + 3:].strip()
                self._vault_index[note_id] = (rel, body)
                count += 1
            except Exception:
                continue
        log.info("vault index built: %d notes from %s", count, vault_base)

    def _vault_content(self, note_id: str) -> Optional[str]:
        """Return vault content string for a note_id, or None if not found."""
        entry = self._vault_index.get(note_id)
        if entry is None:
            return None
        return entry[1]

    def _file_query_semantic(
        self, question: str, n_results: int
    ) -> QueryResult:
        """Semantic-only: FTS on node name and description, no graph traversal."""
        search_terms = [t for t in question.split() if len(t) > 2][:5]
        if not search_terms:
            search_terms = question.split()[:3]

        # Collect ALL matches first, then rank
        all_matches: list[tuple[str, Entity, int]] = []
        node_ids_seen: set[str] = set()

        for table in self.include_node_tables:
            cols = self._node_columns.get(table, [])
            name_col = next((c[0] for c in cols if c[0] in NAME_COLUMN_CANDIDATES), None)
            desc_col = next((c[0] for c in cols if c[0] == "description"), None)
            if not name_col:
                continue

            try:
                where_parts = []
                for t in search_terms:
                    if desc_col:
                        where_parts.append(
                            f'({self._cypher_contains(f"n.{name_col}", t)} OR {self._cypher_contains(f"n.{desc_col}", t)})'
                        )
                    else:
                        where_parts.append(self._cypher_contains(f"n.{name_col}", t))
                where_clause = " OR ".join(where_parts)

                query = (
                    f"MATCH (n:{table}) "
                    f"WHERE n.{name_col} IS NOT NULL "
                    f"  AND ({where_clause}) "
                    f"RETURN n LIMIT 200"
                )
                rows = list(self._conn.execute(query).rows_as_dict())
                for row in rows:
                    node = row.get("n", row)
                    if not isinstance(node, dict):
                        continue
                    raw_id = str(node.get("id", ""))
                    if raw_id in node_ids_seen:
                        continue
                    node_ids_seen.add(raw_id)
                    node_name = node.get(name_col, raw_id)
                    text_col = next((c[0] for c in cols if c[0] in ("text", "content", "body", "description")), None)
                    text = str(node.get(text_col, node_name)) if text_col else node_name
                    context = f"[{table}/{raw_id}] {node_name}\n{text[:300]}"
                    score = sum(1 for t in search_terms if t.lower() in context.lower())
                    entity = Entity(
                        id=f"{table}:{raw_id}",
                        name=str(node_name),
                        entity_type=table,
                        properties=node,
                    )
                    all_matches.append((context, entity, score))
            except Exception as e:
                log.warning("semantic query failed for table %s: %s", table, e)

        if not all_matches:
            return QueryResult(
                answer="",
                context_string="",
                error="NO_RESULTS",
                retrieval_path=["mode=semantic"],
            )

        # Rank by score, take top n_results
        all_matches.sort(key=lambda x: x[2], reverse=True)
        top_matches = all_matches[:n_results]
        context_parts = [m[0] for m in top_matches]
        retrieved = [m[1] for m in top_matches]

        context_string = "\n\n".join(context_parts)
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved,
            retrieval_path=["mode=semantic"],
        )

    def _file_query_hybrid(
        self, question: str, n_results: int
    ) -> QueryResult:
        """Hybrid: FTS seed + one-hop graph traversal from FTS matches.

        Condition B for the LadybugDB adapter — the full structured pipeline.
        """
        search_terms = [t for t in question.split() if len(t) > 2][:5]
        if not search_terms:
            search_terms = question.split()[:3]

        # Phase 1: FTS seed
        seed_ids: set[str] = set()
        for table in self.include_node_tables:
            cols = self._node_columns.get(table, [])
            name_col = next((c[0] for c in cols if c[0] in NAME_COLUMN_CANDIDATES), None)
            desc_col = next((c[0] for c in cols if c[0] == "description"), None)
            if not name_col:
                continue
            try:
                query = (
                    f"MATCH (n:{table}) "
                    f"WHERE n.{name_col} IS NOT NULL AND ("
                    + " OR ".join(self._cypher_contains(f"n.{name_col}", t) for t in search_terms)
                    + f") RETURN n.id, n.{name_col} LIMIT {n_results}"
                )
                rows = self._conn.execute(query).rows_as_dict()
                for row in rows:
                    n = row.get("n", row)
                    if isinstance(n, dict):
                        seed_ids.add(str(n.get("id", "")))
            except Exception as e:
                log.warning("hybrid seed query failed for table %s: %s", table, e)

        if not seed_ids:
            return self._file_query_semantic(question, n_results)

        # Phase 2: one-hop graph traversal from seeds
        context_parts: list[str] = []
        retrieved: list[Entity] = []
        seen_ids: set[str] = set(seed_ids)

        for rel_table in self.include_edge_tables:
            try:
                src_col = self._rel_columns.get(rel_table, [])
                edge_type_col = next(
                    (c[0] for c in src_col if c[0] == EDGE_TYPE_DISCRIMINATOR),
                    None,
                )
                if edge_type_col:
                    cypher = (
                        f"MATCH (a)-[r:{rel_table}]->(b) "
                        f"WHERE a.id IN {list(seed_ids)} "
                        f"RETURN a.id, b.id, r.{edge_type_col} LIMIT {n_results}"
                    )
                else:
                    cypher = (
                        f"MATCH (a)-[r:{rel_table}]->(b) "
                        f"WHERE a.id IN {list(seed_ids)} "
                        f"RETURN a.id, b.id LIMIT {n_results}"
                    )
                rows = list(self._conn.execute(cypher).rows_as_dict())
                for row in rows:
                    src = str(row.get("a", {}).get("id", ""))
                    tgt = str(row.get("b", {}).get("id", ""))
                    etype = str(row.get("r", {}).get(edge_type_col, rel_table)) if edge_type_col else rel_table
                    other = tgt if src in seed_ids else src
                    if other in seen_ids:
                        continue
                    seen_ids.add(other)
                    # Fetch node content (prefer vault content over node metadata)
                    for ntable in self.include_node_tables:
                        try:
                            nrows = self._conn.execute(
                                f"MATCH (n:{ntable}) WHERE n.id = '{other}' RETURN n"
                            ).rows_as_dict()
                            if nrows:
                                node = nrows[0].get("n", nrows[0])
                                if isinstance(node, dict):
                                    name_col = next((c[0] for c in self._node_columns.get(ntable, []) if c[0] in NAME_COLUMN_CANDIDATES), "id")
                                    node_name = str(node.get(name_col, other))
                                    note_id = node.get("note_id")
                                    if note_id and self._vault_index:
                                        vault_text = self._vault_content(note_id)
                                        if vault_text:
                                            text = vault_text
                                        else:
                                            text_col = next((c[0] for c in self._node_columns.get(ntable, []) if c[0] in ("text", "content", "body")), None)
                                            text = str(node.get(text_col, node_name)) if text_col else node_name
                                    else:
                                        text_col = next((c[0] for c in self._node_columns.get(ntable, []) if c[0] in ("text", "content", "body")), None)
                                        text = str(node.get(text_col, node_name)) if text_col else node_name
                                    context_parts.append(f"[{ntable}/{other}] {node_name}\n{text[:300]}")
                                    retrieved.append(Entity(
                                        id=f"{ntable}:{other}",
                                        name=node_name,
                                        entity_type=ntable,
                                        properties={"_via_edge_type": etype, "note_id": note_id},
                                    ))
                                    break
                        except Exception:
                            pass
            except Exception as e:
                log.warning("hybrid traverse failed for rel %s: %s", rel_table, e)

        # Phase 3: also include seed nodes
        for seed_id in seed_ids:
            for ntable in self.include_node_tables:
                try:
                    nrows = self._conn.execute(
                        f"MATCH (n:{ntable}) WHERE n.id = '{seed_id}' RETURN n"
                    ).rows_as_dict()
                    if nrows:
                        node = nrows[0].get("n", nrows[0])
                        if isinstance(node, dict) and f"{ntable}:{seed_id}" not in seen_ids:
                            name_col = next((c[0] for c in self._node_columns.get(ntable, []) if c[0] in NAME_COLUMN_CANDIDATES), "id")
                            node_name = str(node.get(name_col, seed_id))
                            note_id = node.get("note_id")
                            if note_id and self._vault_index:
                                vault_text = self._vault_content(note_id)
                                if vault_text:
                                    text = vault_text
                                else:
                                    text = str(node)[:300]
                            else:
                                text = str(node)[:300]
                            context_parts.append(f"[{ntable}/{seed_id}] {node_name}\n{text[:300]}")
                            seen_ids.add(f"{ntable}:{seed_id}")
                except Exception:
                    pass

        if not context_parts:
            return self._file_query_semantic(question, n_results)

        context_string = "\n\n".join(context_parts[:n_results])
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved[:n_results],
            retrieval_path=["mode=hybrid"],
        )

    def _file_query_graph(
        self, question: str, n_results: int
    ) -> QueryResult:
        """Graph-only: graph traversal from named starting nodes."""
        search_terms = [t for t in question.split() if len(t) > 2][:3]
        visited: set[str] = set()
        queue: list[tuple[str, int]] = []

        # Seed queue with FTS-matched nodes
        for table in self.include_node_tables:
            cols = self._node_columns.get(table, [])
            name_col = next((c[0] for c in cols if c[0] in NAME_COLUMN_CANDIDATES), None)
            desc_col = next((c[0] for c in cols if c[0] == "description"), None)
            if not name_col:
                continue
            try:
                query = (
                    f"MATCH (n:{table}) WHERE "
                    + " OR ".join(self._cypher_contains(f"n.{name_col}", t) for t in search_terms)
                    + f" RETURN n.id LIMIT {n_results}"
                )
                rows = list(self._conn.execute(query).rows_as_dict())
                for row in rows:
                    if "n" in row:
                        n = row["n"]
                        nid = str(n.get("id", "")) if isinstance(n, dict) else ""
                    elif "n.id" in row:
                        nid = str(row["n.id"])
                    else:
                        nid = ""
                    if nid and nid not in visited:
                        queue.append((nid, 0))
                        visited.add(nid)
            except Exception:
                pass

        # BFS traversal up to depth 3
        context_parts: list[str] = []
        retrieved: list[Entity] = []
        while queue and len(visited) < n_results * 3:
            node_id, depth = queue.pop(0)
            if depth >= 3:
                continue
            for rel_table in self.include_edge_tables:
                try:
                    cypher = (
                        f"MATCH (a:Entity)-[r:{rel_table}]->(b) "
                        f"WHERE a.id = '{node_id}' "
                        f"RETURN b.id LIMIT {n_results}"
                    )
                    rows = self._conn.execute(cypher).rows_as_dict()
                    for row in rows:
                        if "b" in row:
                            b = row["b"]
                            nid = str(b.get("id", "")) if isinstance(b, dict) else ""
                        elif "b.id" in row:
                            nid = str(row["b.id"])
                        else:
                            nid = ""
                        if nid and nid not in visited:
                            queue.append((nid, depth + 1))
                            visited.add(nid)
                except Exception:
                    pass

        # Fetch content for visited nodes
        for nid in list(visited)[:n_results]:
            for ntable in self.include_node_tables:
                try:
                    nrows_result = self._conn.execute(
                        f"MATCH (n:{ntable}) WHERE n.id = '{nid}' RETURN n"
                    )
                    nrows = list(nrows_result.rows_as_dict())
                    if nrows:
                        node = nrows[0].get("n", nrows[0])
                        if isinstance(node, dict):
                            name_col = next((c[0] for c in self._node_columns.get(ntable, []) if c[0] in NAME_COLUMN_CANDIDATES), "id")
                            node_name = str(node.get(name_col, nid))
                            context_parts.append(f"[{ntable}/{nid}] {node_name}\n{str(node)[:300]}")
                            retrieved.append(Entity(
                                id=f"{ntable}:{nid}",
                                name=node_name,
                                entity_type=ntable,
                            ))
                            break
                except Exception:
                    pass

        if not context_parts:
            return QueryResult(
                answer="",
                context_string="",
                error="NO_RESULTS",
                retrieval_path=["mode=graph"],
            )

        context_string = "\n\n".join(context_parts[:n_results])
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved[:n_results],
            retrieval_path=["mode=graph"],
        )

    def _file_query_path(
        self, question: str, n_results: int
    ) -> QueryResult:
        """Path-based: find all paths between FTS-matched term pairs."""
        search_terms = [t for t in question.split() if len(t) > 2]
        if len(search_terms) < 2:
            return self._file_query_semantic(question, n_results)

        term_a, term_b = search_terms[0], search_terms[1]
        found_a, found_b = [], []

        for table in self.include_node_tables:
            cols = self._node_columns.get(table, [])
            name_col = next((c[0] for c in cols if c[0] in NAME_COLUMN_CANDIDATES), None)
            desc_col = next((c[0] for c in cols if c[0] == "description"), None)
            if not name_col:
                continue
            try:
                for term, out_list in [(term_a, found_a), (term_b, found_b)]:
                    rows = list(self._conn.execute(
                        f"MATCH (n:{table}) WHERE " + self._cypher_contains(f"n.{name_col}", term) + " RETURN n.id LIMIT 5"
                    ).rows_as_dict())
                    for row in rows:
                        n = row.get("n", row)
                        if isinstance(n, dict):
                            out_list.append(str(n.get("id", "")))
            except Exception:
                pass

        context_parts = []
        for src in found_a[:3]:
            for rel_table in self.include_edge_tables:
                try:
                    rows = self._conn.execute(
                        f"MATCH path=(a){{id: '{src}'}}-[]->(b){{id: '{found_b[0]}'}} RETURN path LIMIT 3"
                    ).rows_as_dict()
                    for row in rows:
                        path_str = str(row.get("path", ""))
                        context_parts.append(f"path: {path_str[:300]}")
                except Exception:
                    pass

        if not context_parts:
            return self._file_query_hybrid(question, n_results)

        context_string = "\n\n".join(context_parts[:n_results])
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=[],
            retrieval_path=["mode=path"],
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        if self._conn is not None:
            return self._file_graph_snapshot()
        if self.api_url is not None:
            return self._api_graph_snapshot()
        log.warning(
            "get_graph_snapshot() called with no db_path and no api_url. "
            "Returning empty snapshot."
        )
        return [], []

    def _file_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """Pull snapshot via direct file access (original path)."""
        entities: list[Entity] = []
        for table in self.include_node_tables:
            entities.extend(self._pull_nodes_generic(table))

        node_ids = {e.id for e in entities}

        edges: list[Edge] = []
        for table in self.include_edge_tables:
            for edge in self._pull_edges_generic(table):
                if edge.source_id in node_ids and edge.target_id in node_ids:
                    edges.append(edge)

        return entities, edges

    def _api_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """Pull snapshot via the API Cypher endpoint.

        Works against locked databases — queries go through the running
        API server instead of opening the .ldb file directly. Discovers
        schema via ``CALL show_tables()``, then pulls entities and edges
        using the same column-name heuristics as file mode.
        """

        # --- Schema discovery ----------------------------------------

        tables = self._api_cypher("CALL show_tables() RETURN *")
        node_tables = [r[1] for r in tables if r[2] == "NODE"]
        rel_tables = [r[1] for r in tables if r[2] == "REL"]

        if self.skip_infrastructure:
            node_tables = [t for t in node_tables if t not in INFRASTRUCTURE_TABLES]
            rel_tables = [t for t in rel_tables if t not in INFRASTRUCTURE_TABLES]

        # Honour explicit include filters. In API-only mode,
        # self.include_node/edge_tables may be empty (file-mode
        # resolution returned nothing); use the raw user-provided
        # filters instead.
        node_filter = self._explicit_node_tables or self.include_node_tables
        edge_filter = self._explicit_edge_tables or self.include_edge_tables
        if node_filter:
            node_tables = [t for t in node_tables if t in set(node_filter)]
        if edge_filter:
            rel_tables = [t for t in rel_tables if t in set(edge_filter)]

        log.info(
            "API snapshot: node tables %s, rel tables %s", node_tables, rel_tables
        )

        # --- Entities ------------------------------------------------

        entities: list[Entity] = []
        for table in node_tables:
            rows = self._api_cypher_dicts(f"MATCH (n:{table}) RETURN n")
            for row in rows:
                node = row.get("n", row)
                if isinstance(node, dict):
                    raw_id = node.get("id", "")
                    name = None
                    for col in NAME_COLUMN_CANDIDATES:
                        if col in node and node[col]:
                            name = node[col]
                            break
                    etype = None
                    for col in TYPE_COLUMN_CANDIDATES:
                        if col in node and node[col]:
                            etype = node[col]
                            break
                    entities.append(Entity(
                        id=f"{table}:{raw_id}" if raw_id else str(node.get("_ID", "")),
                        name=name or raw_id or "",
                        entity_type=etype or table,
                    ))
            log.info("  %s: %d entities via API", table, len(rows))

        node_ids = {e.id for e in entities}

        # --- Edges ---------------------------------------------------

        edges: list[Edge] = []
        for table in rel_tables:
            # Discover connection endpoints
            conn_rows = self._api_cypher(
                f"CALL SHOW_CONNECTION('{table}') RETURN *"
            )
            if not conn_rows:
                log.warning("no connection info for %s via API — skipping", table)
                continue
            from_label, to_label = conn_rows[0][0], conn_rows[0][1]

            # Check for edge_type discriminator column
            col_rows = self._api_cypher(
                f"CALL TABLE_INFO('{table}') RETURN *"
            )
            col_names = [r[1] for r in col_rows]
            has_disc = EDGE_TYPE_DISCRIMINATOR in col_names

            if has_disc:
                cypher = (
                    f"MATCH (a:{from_label})-[r:{table}]->(b:{to_label}) "
                    f"RETURN a.id, b.id, r.{EDGE_TYPE_DISCRIMINATOR}"
                )
            else:
                cypher = (
                    f"MATCH (a:{from_label})-[r:{table}]->(b:{to_label}) "
                    f"RETURN a.id, b.id"
                )

            rows = self._api_cypher(cypher)
            for r in rows:
                src_id = f"{from_label}:{r[0]}"
                tgt_id = f"{to_label}:{r[1]}"
                if src_id in node_ids and tgt_id in node_ids:
                    etype = r[2] if has_disc and len(r) > 2 and r[2] else table
                    edges.append(Edge(
                        source_id=src_id,
                        target_id=tgt_id,
                        edge_type=etype,
                    ))
            log.info("  %s: %d edges via API", table, len(rows))

        return entities, edges

    def _api_cypher(self, query: str) -> list[list]:
        """Execute Cypher via the API, return raw row arrays.

        Tries ``/api/query?cypher=...`` (FastAPI pattern) then falls
        back to ``/query?cypher=...``.
        """
        import urllib.error
        import urllib.parse
        import urllib.request
        import json as _json

        for path in ("/api/query", "/query"):
            url = f"{self.api_url}{path}?{urllib.parse.urlencode({'cypher': query})}"
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                    body = _json.loads(resp.read().decode("utf-8"))
                results = body.get("results", [])
                if results or body.get("count", -1) == 0:
                    # Convert dict rows to list rows for CALL-style results
                    if results and isinstance(results[0], dict):
                        return [list(r.values()) for r in results]
                    return results
            except urllib.error.HTTPError:
                continue
            except Exception as e:
                log.warning("API Cypher failed on %s: %s", path, e)
                continue
        log.warning("API Cypher query returned no results: %s", query[:80])
        return []

    def _api_cypher_dicts(self, query: str) -> list[dict]:
        """Execute Cypher via the API, return rows as dicts."""
        import urllib.parse
        import urllib.request
        import json as _json

        for path in ("/api/query", "/query"):
            url = f"{self.api_url}{path}?{urllib.parse.urlencode({'cypher': query})}"
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                    body = _json.loads(resp.read().decode("utf-8"))
                return body.get("results", [])
            except Exception:
                continue
        return []

    # --- Cat 8 ontology source -----------------------------------------

    def get_ontology_source(self) -> dict:
        """LadybugDB schemas are declared — return the full table layout."""
        # Distinct edge_type values per rel table (for consolidated-style
        # schemas where the discriminator lives in a column).
        entity_edge_types: list[str] = []
        for rel in self._rel_tables:
            cols = {c[0] for c in self._rel_columns[rel]}
            if EDGE_TYPE_DISCRIMINATOR in cols:
                try:
                    r = self._conn.execute(
                        f"MATCH ()-[r:{rel}]->() "
                        f"RETURN DISTINCT r.{EDGE_TYPE_DISCRIMINATOR}"
                    ).get_all()
                    for row in r:
                        if row[0]:
                            entity_edge_types.append(row[0])
                except Exception:  # pragma: no cover
                    pass

        # For per-type schemas, the rel table names themselves are the
        # edge type vocabulary.
        rel_table_vocab = sorted(
            t for t in self._rel_tables if t not in INFRASTRUCTURE_TABLES
        )

        return {
            "type": "declared",
            "schema": [
                {"kind": "node", "tables": sorted(self._node_tables)},
                {"kind": "rel", "tables": rel_table_vocab},
                {
                    "kind": "entity_edge_types",
                    "values": sorted(set(entity_edge_types)),
                },
            ],
            "documentation": (
                f"LadybugDB graph with {len(self._node_tables)} node tables "
                f"and {len(self._rel_tables)} relationship tables. "
                f"Edge type vocabulary: "
                + (
                    ", ".join(sorted(set(entity_edge_types)))
                    if entity_edge_types
                    else ", ".join(rel_table_vocab) or "<none>"
                )
            ),
        }

    # --- Introspection helpers -----------------------------------------

    def _discover_tables(self) -> tuple[list[str], list[str]]:
        rows = self._conn.execute("CALL SHOW_TABLES() RETURN *").get_all()
        node_tables: list[str] = []
        rel_tables: list[str] = []
        for row in rows:
            # row: [id, name, type, schema, comment]
            name = row[1]
            kind = row[2]
            if kind == "NODE":
                node_tables.append(name)
            elif kind == "REL":
                rel_tables.append(name)
        return node_tables, rel_tables

    def _table_columns(self, table: str) -> list[tuple[str, str]]:
        """Return [(column_name, column_type), ...] for a table."""
        try:
            rows = self._conn.execute(
                f"CALL TABLE_INFO('{table}') RETURN *"
            ).get_all()
        except Exception as e:  # pragma: no cover
            log.warning("TABLE_INFO failed for %s: %s", table, e)
            return []
        # row: [col_id, col_name, col_type, default, is_primary_key]
        return [(r[1], r[2]) for r in rows]

    def _rel_connection(self, rel_table: str) -> tuple[str, str]:
        """Return (from_label, to_label) for a relationship table."""
        try:
            rows = self._conn.execute(
                f"CALL SHOW_CONNECTION('{rel_table}') RETURN *"
            ).get_all()
            if rows:
                return (rows[0][0], rows[0][1])
        except Exception as e:  # pragma: no cover
            log.warning("SHOW_CONNECTION failed for %s: %s", rel_table, e)
        return ("", "")

    def _table_row_count(self, table: str, is_rel: bool) -> int:
        try:
            if is_rel:
                r = self._conn.execute(
                    f"MATCH ()-[r:{table}]->() RETURN count(r)"
                ).get_all()
            else:
                r = self._conn.execute(
                    f"MATCH (n:{table}) RETURN count(n)"
                ).get_all()
            return int(r[0][0]) if r else 0
        except Exception:  # pragma: no cover
            return 0

    def _resolve_node_selection(
        self,
        explicit: Optional[Iterable[str]],
        auto_discover: bool,
    ) -> list[str]:
        if explicit is not None:
            return [t for t in explicit if t in self._node_tables]
        candidates = [
            t
            for t in self._node_tables
            if not self.skip_infrastructure or t not in INFRASTRUCTURE_TABLES
        ]
        if auto_discover:
            return [t for t in candidates if self._table_row_count(t, False) > 0]
        # Default: structural core — Entity + Note + Document + others
        # excluding operational infrastructure.
        return candidates

    def _resolve_edge_selection(
        self,
        explicit: Optional[Iterable[str]],
        auto_discover: bool,
    ) -> list[str]:
        if explicit is not None:
            return [t for t in explicit if t in self._rel_tables]
        candidates = [
            t
            for t in self._rel_tables
            if not self.skip_infrastructure or t not in INFRASTRUCTURE_TABLES
        ]
        # Always filter to non-empty rel tables — analyzing 0-edge
        # tables is just noise.
        return [t for t in candidates if self._table_row_count(t, True) > 0]

    # --- Generic projection --------------------------------------------

    def _pull_nodes_generic(self, table: str) -> list[Entity]:
        """Introspection-driven node projection.

        Projects `id`, picks a name column from NAME_COLUMN_CANDIDATES,
        picks an entity_type from TYPE_COLUMN_CANDIDATES (falling back
        to the table name), and stashes all remaining scalar columns
        in properties.
        """
        cols = self._node_columns.get(table, [])
        col_names = [c[0] for c in cols]

        if "id" not in col_names:
            log.warning("table %s has no id column — skipping", table)
            return []

        name_col = next((c for c in NAME_COLUMN_CANDIDATES if c in col_names), None)
        type_col = next((c for c in TYPE_COLUMN_CANDIDATES if c in col_names), None)

        # Skip embedding-style columns — they're large, vectors not strings
        skip = {"embedding", "vector", "vec"}
        property_cols = [
            c
            for c in col_names
            if c != "id"
            and c != name_col
            and c != type_col
            and c not in skip
        ]

        projection = ["n.id"]
        if name_col:
            projection.append(f"n.{name_col}")
        if type_col:
            projection.append(f"n.{type_col}")
        projection.extend(f"n.{c}" for c in property_cols)

        try:
            rows = self._conn.execute(
                f"MATCH (n:{table}) RETURN {', '.join(projection)}"
            ).get_all()
        except Exception as e:  # pragma: no cover
            log.warning("node pull failed for %s: %s", table, e)
            return []

        out: list[Entity] = []
        for r in rows:
            col_iter = iter(r)
            raw_id = next(col_iter)
            name = next(col_iter) if name_col else raw_id
            etype = next(col_iter) if type_col else table
            props = {"_table": table}
            for c in property_cols:
                props[c] = next(col_iter)
            out.append(
                Entity(
                    id=f"{table}:{raw_id}",
                    name=name or raw_id,
                    entity_type=(etype or table) if type_col else table,
                    properties=props,
                )
            )
        return out

    def _pull_edges_generic(self, table: str) -> list[Edge]:
        """Introspection-driven edge projection.

        Uses SHOW_CONNECTION to find FROM/TO labels, then projects the
        source id, target id, and all scalar columns. If the edge table
        has an `edge_type` column, that value becomes the SME edge type;
        otherwise the rel table name is used.
        """
        from_label, to_label = self._rel_connections.get(table, ("", ""))
        if not from_label or not to_label:
            log.warning("no connection info for rel table %s — skipping", table)
            return []

        cols = self._rel_columns.get(table, [])
        col_names = [c[0] for c in cols]
        has_discriminator = EDGE_TYPE_DISCRIMINATOR in col_names

        skip = {"embedding", "vector", "vec"}
        property_cols = [c for c in col_names if c not in skip]

        projection = ["a.id", "b.id"]
        projection.extend(f"r.{c}" for c in property_cols)

        try:
            rows = self._conn.execute(
                f"MATCH (a:{from_label})-[r:{table}]->(b:{to_label}) "
                f"RETURN {', '.join(projection)}"
            ).get_all()
        except Exception as e:  # pragma: no cover
            log.warning("edge pull failed for %s: %s", table, e)
            return []

        out: list[Edge] = []
        for r in rows:
            it = iter(r)
            src = next(it)
            tgt = next(it)
            props: dict = {"_table": table, "_from_label": from_label, "_to_label": to_label}
            edge_type_val = None
            for c in property_cols:
                v = next(it)
                props[c] = v
                if c == EDGE_TYPE_DISCRIMINATOR:
                    edge_type_val = v
                # Map common provenance column names to reserved keys
                if c == "extraction_source":
                    props["_created_by"] = v
                elif c == "source_pattern":
                    props["_source_pattern"] = v

            edge_type = edge_type_val if has_discriminator and edge_type_val else table

            out.append(
                Edge(
                    source_id=f"{from_label}:{src}",
                    target_id=f"{to_label}:{tgt}",
                    edge_type=edge_type,
                    properties=props,
                )
            )
        return out

    # --- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        self._conn = None
        self._db = None


# Kept for backward compatibility with the initial commit's CLI import
DEFAULT_NODE_TABLES: tuple[str, ...] = ("Entity", "Note", "Document")
DEFAULT_EDGE_TABLES: tuple[str, ...] = ()
