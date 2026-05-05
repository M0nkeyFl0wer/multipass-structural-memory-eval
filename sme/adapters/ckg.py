"""SMEAdapter for danyarm/ckg-benchmark CSV-format Compact Knowledge Graphs.

A CKG is a hand-authored DAG distributed as a single CSV with schema

    ConceptID, ConceptLabel, Dependencies, TaxonomyID

where Dependencies is a pipe-separated list of ConceptIDs (parent
concepts this one depends on) and TaxonomyID labels the concept's
kind (FOUND, MECHANISM, ENZYME, …).

This adapter loads one such CSV and exposes the SME interface so the
graph can be probed by Categories 1, 2, 7, 8 and run through A/B/C
isolation. See docs/ckg_benchmark_experiment.md for the experiment
methodology and the falsifiable predictions this is set up to test.

Three required methods only at this scaffold stage; query() and
get_flat_retrieval() are stubs that raise NotImplementedError. Filling
them in is task #3 in the experiment plan.
"""

from __future__ import annotations

import csv
from pathlib import Path

from sme.adapters.base import (
    Edge,
    Entity,
    QueryResult,
    SMEAdapter,
)


class CKGAdapter(SMEAdapter):
    """Load a single ckg-benchmark domain into SME.

    Construction-time, not ingest-time, parameters: which CSV file. The
    SME ingest_corpus() method takes a `corpus: list[dict]` per the spec,
    so we accept that shape too — each dict can either be a row from the
    CSV (already-parsed) or carry a 'csv_path' key to point at a file.
    """

    def __init__(self, csv_path: str | Path | None = None):
        self.csv_path: Path | None = Path(csv_path) if csv_path else None
        self._entities: list[Entity] = []
        self._edges: list[Edge] = []
        self._by_id: dict[str, Entity] = {}
        self._by_label: dict[str, Entity] = {}

    # --- Required interface -------------------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        """Load CKG rows.

        Two accepted corpus shapes:
          1. [{'csv_path': '/path/to/learning-graph.csv'}]
          2. [{'ConceptID': '1', 'ConceptLabel': 'X', 'Dependencies': '',
               'TaxonomyID': 'FOUND'}, ...]
        """
        errors: list[str] = []
        warnings: list[str] = []
        rows: list[dict] = []

        if corpus and "csv_path" in corpus[0]:
            for c in corpus:
                with open(c["csv_path"], newline="") as f:
                    rows.extend(csv.DictReader(f))
        elif self.csv_path is not None and not corpus:
            with open(self.csv_path, newline="") as f:
                rows = list(csv.DictReader(f))
        else:
            rows = corpus

        for row in rows:
            cid = row["ConceptID"]
            ent = Entity(
                id=cid,
                name=row["ConceptLabel"],
                entity_type=row.get("TaxonomyID", ""),
                properties={"taxonomy_id": row.get("TaxonomyID", "")},
            )
            if cid in self._by_id:
                warnings.append(f"duplicate ConceptID: {cid}")
            self._by_id[cid] = ent
            self._by_label[ent.name.lower()] = ent
            self._entities.append(ent)

        for row in rows:
            cid = row["ConceptID"]
            deps = row.get("Dependencies", "")
            if not deps:
                continue
            for parent_id in deps.split("|"):
                parent_id = parent_id.strip()
                if not parent_id:
                    continue
                if parent_id not in self._by_id:
                    errors.append(
                        f"phantom dependency: {cid} -> {parent_id} (parent not in graph)"
                    )
                    continue
                self._edges.append(
                    Edge(
                        source_id=cid,
                        target_id=parent_id,
                        edge_type="DEPENDS_ON",
                        properties={
                            "child_taxonomy": self._by_id[cid].entity_type,
                            "parent_taxonomy": self._by_id[parent_id].entity_type,
                        },
                    )
                )

        return {
            "entities_created": len(self._entities),
            "edges_created": len(self._edges),
            "errors": errors,
            "warnings": warnings,
        }

    def query(self, question: str) -> QueryResult:
        raise NotImplementedError(
            "CKG query traversal not yet implemented — see experiment task #3"
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        return list(self._entities), list(self._edges)

    # --- Optional interface --------------------------------------------

    def get_flat_retrieval(self, question: str) -> QueryResult:
        raise NotImplementedError(
            "CKG flat-baseline serializer not yet implemented — see experiment task #3"
        )

    def get_ontology_source(self) -> dict:
        """CKG schema is declared by the CSV header — Concept/Dep/Taxonomy."""
        return {
            "type": "declared",
            "schema": [
                {"field": "ConceptID", "role": "node_id"},
                {"field": "ConceptLabel", "role": "node_name"},
                {"field": "Dependencies", "role": "parent_ids", "delimiter": "|"},
                {"field": "TaxonomyID", "role": "node_type"},
            ],
            "documentation": (
                "Compact Knowledge Graph (Yarmoluk 2026): hand-authored DAG. "
                "Each row is a concept; Dependencies lists parent ConceptIDs "
                "this concept depends on; TaxonomyID labels the concept kind."
            ),
        }
