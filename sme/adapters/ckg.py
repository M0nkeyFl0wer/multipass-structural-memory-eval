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

Conditions implemented:
  B (query): k-hop neighborhood retrieval over the DAG, formatted as
    typed triples plus concept definitions.
  A (get_flat_retrieval): token-overlap retrieval over a per-concept
    prose serialization of the same CSV. Stand-in for vanilla RAG;
    deliberately simple — the comparison is on retrieval *form*, not
    embedding model.
  C (condition_c_serialization): same node set B retrieved, prose
    only, no edges. The B-C delta isolates "did the structure earn
    the score, or was it the content?"
"""

from __future__ import annotations

import csv
import re
from collections import deque
from pathlib import Path
from typing import Iterable

from sme.adapters.base import (
    Edge,
    Entity,
    QueryResult,
    SMEAdapter,
)


_TOKEN_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class CKGAdapter(SMEAdapter):
    """Load a single ckg-benchmark domain into SME.

    Args:
      csv_path: path to learning-graph.csv (alternative to passing rows
        through ingest_corpus())
      hop_budget: how many hops B traverses from the target concept.
        Default 2 covers T1_entity / T2_dependency / most T3_path
        queries; T3_path with hop_depth>2 will under-retrieve, which is
        a real-world failure mode worth measuring (graph systems hard-
        cap traversal in practice).
      n_flat_results: top-K passages get_flat_retrieval returns.
    """

    def __init__(
        self,
        csv_path: str | Path | None = None,
        *,
        hop_budget: int = 2,
        n_flat_results: int = 5,
    ):
        self.csv_path: Path | None = Path(csv_path) if csv_path else None
        self.hop_budget = hop_budget
        self.n_flat_results = n_flat_results
        self._entities: list[Entity] = []
        self._edges: list[Edge] = []
        self._by_id: dict[str, Entity] = {}
        self._by_label: dict[str, Entity] = {}
        # adjacency: parents[child] = set(parent_ids); children[parent] = set(child_ids)
        self._parents: dict[str, set[str]] = {}
        self._children: dict[str, set[str]] = {}

    # --- Required interface -------------------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        """Load CKG rows.

        Three accepted corpus shapes:
          1. [{'csv_path': '/path/to/learning-graph.csv'}]
          2. [{'ConceptID': '1', 'ConceptLabel': 'X', 'Dependencies': '',
               'TaxonomyID': 'FOUND'}, ...]
          3. empty list with self.csv_path set on construction
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
            self._parents.setdefault(cid, set())
            self._children.setdefault(cid, set())

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
                self._parents[cid].add(parent_id)
                self._children[parent_id].add(cid)

        return {
            "entities_created": len(self._entities),
            "edges_created": len(self._edges),
            "errors": errors,
            "warnings": warnings,
        }

    def query(self, question: str) -> QueryResult:
        """Condition B: k-hop neighborhood retrieval with typed-triple format."""
        target = self._match_target(question)
        if target is None:
            return QueryResult(
                answer="",
                context_string="",
                error="NO_MATCH",
            )
        node_ids = self._neighborhood(target.id, self.hop_budget)
        retrieved_entities = [self._by_id[i] for i in node_ids]
        retrieved_edges = self._edges_in_subgraph(node_ids)
        context_string = self._format_triples(target, retrieved_entities, retrieved_edges)
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved_entities,
            retrieved_edges=retrieved_edges,
            retrieval_path=[target.id, *(i for i in node_ids if i != target.id)],
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        return list(self._entities), list(self._edges)

    # --- Optional interface --------------------------------------------

    def get_flat_retrieval(self, question: str) -> QueryResult:
        """Condition A: per-concept prose serialization, token-overlap retrieval.

        Stand-in for "vanilla RAG with no graph traversal." Each concept
        is a single chunk; ranking is unweighted token-overlap (no IDF,
        no embedding). This is *deliberately* a weak baseline — the
        point is to keep the comparison about retrieval *form* (flat vs
        structural) rather than embedding-model quality. A stronger
        flat baseline (BM25, dense embeddings) would slot in here later.
        """
        if not self._entities:
            return QueryResult(answer="", context_string="", error="EMPTY_GRAPH")
        q_tokens = set(_tokenize(question))
        if not q_tokens:
            return QueryResult(answer="", context_string="", error="EMPTY_QUERY")

        scored: list[tuple[float, Entity, str]] = []
        for ent in self._entities:
            chunk = self._concept_chunk(ent)
            doc_tokens = _tokenize(chunk)
            if not doc_tokens:
                continue
            overlap = sum(1 for t in doc_tokens if t in q_tokens)
            if overlap == 0:
                continue
            # length-normalized to avoid bias toward long chunks
            score = overlap / (len(doc_tokens) ** 0.5)
            scored.append((score, ent, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: self.n_flat_results]
        if not top:
            return QueryResult(answer="", context_string="", error="NO_RESULTS")

        context_parts = [f"[{i + 1}] {chunk}" for i, (_, _, chunk) in enumerate(top)]
        context_string = "\n\n".join(context_parts)
        retrieved = [ent for _, ent, _ in top]
        return QueryResult(
            answer=context_string,
            context_string=context_string,
            retrieved_entities=retrieved,
        )

    def condition_c_serialization(self, entities: Iterable[Entity]) -> str:
        """Condition C: same nodes B retrieved, prose only — no edges.

        Caller passes the retrieved_entities from a Condition B query
        result. The output preserves entity content (label + taxonomy +
        dependencies as a flat prose list) but omits the typed-triple
        structure. The B-C token delta is the structural overhead;
        the B-C recall delta is the structural retrieval *gain*.
        """
        chunks = [self._concept_chunk(ent) for ent in entities]
        return "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(chunks))

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

    # --- Internals -----------------------------------------------------

    def _match_target(self, question: str) -> Entity | None:
        """Find the concept the question is asking about.

        Strategy: find the longest ConceptLabel that appears as a
        case-insensitive substring of the question. This is a deliberately
        simple matcher; CKG queries are templated ("What is X?",
        "What does X depend on?") so the label is almost always present
        verbatim. If no exact-substring hit, fall back to most token
        overlap with any label.
        """
        q_lower = question.lower()
        best: tuple[int, Entity] | None = None
        for label_lc, ent in self._by_label.items():
            if label_lc and label_lc in q_lower:
                # prefer longer matches (more specific)
                if best is None or len(label_lc) > best[0]:
                    best = (len(label_lc), ent)
        if best:
            return best[1]

        q_tokens = set(_tokenize(question))
        if not q_tokens:
            return None
        best_score = 0
        best_ent: Entity | None = None
        for ent in self._entities:
            l_tokens = set(_tokenize(ent.name))
            overlap = len(l_tokens & q_tokens)
            if overlap > best_score:
                best_score = overlap
                best_ent = ent
        return best_ent

    def _neighborhood(self, root_id: str, k: int) -> list[str]:
        """BFS k hops from root_id over both directions of the DAG."""
        seen = {root_id}
        order = [root_id]
        frontier = deque([(root_id, 0)])
        while frontier:
            nid, d = frontier.popleft()
            if d >= k:
                continue
            for nbr in self._parents.get(nid, set()) | self._children.get(nid, set()):
                if nbr not in seen:
                    seen.add(nbr)
                    order.append(nbr)
                    frontier.append((nbr, d + 1))
        return order

    def _edges_in_subgraph(self, node_ids: Iterable[str]) -> list[Edge]:
        s = set(node_ids)
        return [e for e in self._edges if e.source_id in s and e.target_id in s]

    def _concept_chunk(self, ent: Entity) -> str:
        """One-line prose serialization of a single concept.

        Used for both Condition A (flat retrieval over all concepts)
        and Condition C (prose-only equivalent of B's node set).
        """
        parents = self._parents.get(ent.id, set())
        if parents:
            parent_labels = sorted(self._by_id[p].name for p in parents)
            dep_clause = " Depends on: " + ", ".join(parent_labels) + "."
        else:
            dep_clause = " (no dependencies; root concept.)"
        tax = ent.entity_type or "unknown"
        return f"Concept '{ent.name}' (taxonomy: {tax})." + dep_clause

    def _format_triples(
        self,
        target: Entity,
        entities: list[Entity],
        edges: list[Edge],
    ) -> str:
        """Condition B context: typed triples around the target concept.

        Emits a header line naming the target with its taxonomy, then
        one triple per edge in DEPENDS_ON form. This is the *structural*
        format whose value Yarmoluk's benchmark argues for and which
        Condition C strips out.
        """
        lines: list[str] = []
        tax = target.entity_type or "unknown"
        lines.append(f"<{target.name}> (taxonomy: {tax})")
        for ent in entities:
            if ent.id == target.id:
                continue
            etax = ent.entity_type or "unknown"
            lines.append(f"  - <{ent.name}> (taxonomy: {etax})")
        lines.append("")
        for e in edges:
            src = self._by_id[e.source_id].name
            tgt = self._by_id[e.target_id].name
            lines.append(f"<{src}> --[{e.edge_type}]--> <{tgt}>")
        return "\n".join(lines)
