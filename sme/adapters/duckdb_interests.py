"""DuckDB adapter for SME — reads the bens-interests knowledge substrate.

The interests KG uses DuckDB as its single source of truth (see
docs/INTERESTS_ONTOLOGY.md in elephant-room). Entity/edge tables are
typed-relational, not graph-native; this adapter projects them into
the SME Entity/Edge model for topology analysis, ontology coherence,
and retrieval-quality testing.

Schema (generator/interests_store.py):
  entity(id, entity_type, canonical_name, aliases, source_engine, ...)
  edge(id, src_id, dst_id, edge_type, evidence, confidence, ...)
  chunk(id, source_engine, source_uri, source_title, seq, text, embedding, ...)
  discovered_items(id, source_engine, status, ...)
  enrichment_findings(...)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


class DuckDBInterestsAdapter(SMEAdapter):
    """Adapter for the bens-interests DuckDB store."""

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        *,
        read_only: bool = True,
        default_query_mode: str = "hybrid",
    ):
        if db_path is None:
            db_path = Path.home() / "Projects" / "bens-interests" / "interests.duckdb"
        self.db_path = str(db_path)
        self.default_query_mode = default_query_mode
        self._con = None

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Interests DuckDB not found at {self.db_path}. "
                "Set INTERESTS_DB_PATH or pass --db."
            )

        import duckdb

        if read_only:
            self._con = duckdb.connect(self.db_path, read_only=True)
        else:
            self._con = duckdb.connect(self.db_path)
        self._con.execute("LOAD fts")
        self._read_only = read_only

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    def __del__(self):
        self.close()

    # --- SMEAdapter required methods -----------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "DuckDBInterestsAdapter reads an existing interests KG. "
            "Use the elephant-room nightly pipeline for ingestion."
        )

    def query(
        self,
        question: str,
        *,
        n_results: int = 10,
        mode: Optional[str] = None,
        route: bool = True,
    ) -> QueryResult:
        """Hybrid BM25 + cosine retrieval via the interests store.

        Condition B (route=True): hybrid BM25 + cosine RRF.
        Condition C (route=False): BM25-only (no embedding).
        """
        chosen_mode = (
            "semantic" if not route else (mode or self.default_query_mode)
        )

        from generator import interests_store as store

        query_embedding = None
        if chosen_mode in ("hybrid", "semantic") and route:
            try:
                query_embedding = store.default_embed_text(question)
            except Exception as e:
                log.warning("embedding failed, degrading to BM25-only: %s", e)

        results = store.search(
            self._con,
            question,
            query_embedding=query_embedding,
            k=n_results,
        )

        if not results:
            return QueryResult(
                answer="",
                context_string="",
                error="NO_RESULTS",
                retrieval_path=[f"mode={chosen_mode}"],
            )

        context_parts: list[str] = []
        retrieved: list[Entity] = []
        for i, r in enumerate(results):
            title = r.get("source_title", "")
            text = r.get("text", "")
            engine = r.get("source_engine", "")
            score = r.get("rrf_score", 0.0)
            context_parts.append(
                f"[{i + 1}] ({engine}) {title}\n{text[:500]}"
            )
            retrieved.append(
                Entity(
                    id=f"chunk:{r.get('id', f'hit{i}')}",
                    name=title or f"hit{i}",
                    entity_type="chunk",
                    properties={
                        "source_engine": engine,
                        "rrf_score": score,
                        "source_uri": r.get("source_uri"),
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

    def get_flat_retrieval(self, question: str) -> QueryResult:
        """BM25-only retrieval (Condition A baseline)."""
        return self.query(question, route=False)

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """Read all entities and edges from the DuckDB store."""
        entities: list[Entity] = []
        for row in self._con.execute(
            "SELECT id, entity_type, canonical_name, source_engine, "
            "aliases, source_doc, extractor, confidence "
            "FROM entity"
        ).fetchall():
            eid, etype, name, engine, aliases, source_doc, extractor, conf = row
            entities.append(
                Entity(
                    id=eid,
                    name=name or "",
                    entity_type=etype,
                    properties={
                        "source_engine": engine,
                        "aliases": aliases,
                        "source_doc": source_doc,
                        "extractor": extractor,
                        "confidence": conf,
                    },
                )
            )

        entity_ids = {e.id for e in entities}

        edges: list[Edge] = []
        for row in self._con.execute(
            "SELECT src_id, dst_id, edge_type, evidence, confidence, "
            "source_doc, extractor "
            "FROM edge"
        ).fetchall():
            src, dst, etype, evidence, conf, source_doc, extractor = row
            if src in entity_ids and dst in entity_ids:
                edges.append(
                    Edge(
                        source_id=src,
                        target_id=dst,
                        edge_type=etype,
                        properties={
                            "evidence": evidence,
                            "confidence": conf,
                            "source_doc": source_doc,
                            "extractor": extractor,
                        },
                    )
                )

        return entities, edges

    def get_ontology_source(self) -> dict:
        """Return the declared ontology from the interests store constants."""
        from generator import interests_store as store

        schema = [
            {"kind": "entity_types", "values": list(store.ENTITY_TYPES)},
            {"kind": "edge_types", "values": list(store.EDGE_TYPES)},
            {
                "kind": "edge_domain_range",
                "values": {
                    et: {
                        "domain": sorted(d),
                        "range": sorted(r),
                    }
                    for et, (d, r) in store.EDGE_DOMAIN_RANGE.items()
                },
            },
        ]

        return {
            "type": "declared",
            "schema": schema,
            "documentation": (
                f"Interests KG ontology: {len(store.SPINE_ENTITY_TYPES)} "
                f"spine types ({', '.join(store.SPINE_ENTITY_TYPES)}) + "
                f"{len(store.EXTENSION_ENTITY_TYPES)} extensions "
                f"({', '.join(store.EXTENSION_ENTITY_TYPES)}). "
                f"Edge types: {', '.join(store.EDGE_TYPES)}. "
                f"Shared-core spine with per-topic extensions; "
                f"OntoClean +R +I on all spine types; "
                f"roles modelled as edges, never types."
            ),
        }