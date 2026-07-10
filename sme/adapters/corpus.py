"""Corpus adapter for SME — read a markdown vault's answer-key directly.

This is the *backend-free* adapter. Where the other adapters read a live
store (LadybugDB, MemPalace/ChromaDB, a daemon), this one reads a corpus
vault of markdown notes whose YAML frontmatter *is* the graph: each note
declares its `entities:` and `edges:` (the hand-authored ground truth that
ships with a corpus like good-dog-corpus).

Why it exists: the structural categories (Cat 4 ingestion integrity, Cat 5
gap detection, Cat 8 ontology coherence) only call ``get_graph_snapshot()``.
Before this adapter there was no way to run them against a shipped corpus
without first standing up a graph DB and running an (undocumented) ingestion
pipeline — so a fresh user could not reproduce the demo. This adapter turns

    sme-eval cat5 --adapter corpus --db-path sme/corpora/good-dog-corpus/vault

into a one-command run that needs no database at all. It reads the *authored*
graph (the answer key), so the readings describe the corpus-as-designed —
the reference point a real ingestion pipeline is later measured against.

Frontmatter contract (good-dog-corpus shape):

    entities:
      - id: breed_amstaff            # -> Entity.id
        type: breed                  # -> Entity.entity_type
        canonical: "AmStaff"         # -> Entity.name (falls back to id)
        # any other keys -> Entity.properties
    edges:
      - from: pub_x                  # -> Edge.source_id
        type: mentions               # -> Edge.edge_type
        to: breed_amstaff            # -> Edge.target_id
        evidence: "..."              # -> Edge.properties
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)

# Frontmatter is the leading `---\n ... \n---` block. DOTALL so the body
# (which spans many lines) is captured; non-greedy so we stop at the first
# closing fence rather than the last one in the file.
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# Keys consumed into first-class Entity fields; everything else on an entity
# dict is preserved under Entity.properties.
_ENTITY_RESERVED = {"id", "type", "canonical", "name"}


class CorpusAdapter(SMEAdapter):
    """Project a markdown-vault answer key into an SME graph snapshot.

    Snapshot-only: it has no retrieval index, so ``query()`` is not
    meaningful (the structural categories never call it). Use it with
    ``cat4`` / ``cat5`` / ``cat8`` / ``analyze``.
    """

    def __init__(
        self,
        corpus_dir: str | Path,
        *,
        read_only: bool = True,  # accepted for CLI parity; nothing to lock
    ):
        self.corpus_dir = Path(corpus_dir)
        if not self.corpus_dir.exists():
            raise SystemExit(f"corpus dir does not exist: {self.corpus_dir}")
        # Cache the parse — cat commands may ask for the snapshot and the
        # ontology in the same run, and re-walking the tree is wasteful.
        self._snapshot: Optional[tuple[list[Entity], list[Edge]]] = None
        log.info("CorpusAdapter reading vault at %s", self.corpus_dir)

    # --- Required ------------------------------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        """No-op ingest: the corpus *is* the on-disk vault, already 'ingested'.

        Returns the same shape as other adapters so callers can report
        counts. Parsing happens here so the numbers are real.
        """
        entities, edges = self.get_graph_snapshot()
        return {
            "entities_created": len(entities),
            "edges_created": len(edges),
            "errors": [],
            "warnings": [],
        }

    def query(self, question: str) -> QueryResult:
        """Not supported — this adapter has no retrieval index.

        Returns a failed QueryResult with a clear message rather than
        raising, so a mis-pointed Cat 1/7 run degrades gracefully instead
        of stack-tracing.
        """
        return QueryResult(
            answer="",
            context_string="",
            error=(
                "CorpusAdapter is snapshot-only (no retrieval index); it "
                "supports the structural categories cat4/cat5/cat8/analyze, "
                "not retrieval (cat1/cat2c/cat7). Point those at a live "
                "adapter (ladybugdb, mempalace, flat) instead."
            ),
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """Parse every note's frontmatter into (entities, edges).

        - Entities are keyed by id; a later declaration wins (matches the
          corpus validator's "later definition wins" semantics).
        - Edge endpoints referenced but never declared get a stub entity
          (entity_type='unknown', properties={'stub': True}) so no authored
          edge is silently dropped — a dropped edge would distort topology,
          and the stubs themselves are an honest 'referenced-but-undefined'
          signal the structural categories can see.
        """
        if self._snapshot is not None:
            return self._snapshot

        entities: dict[str, Entity] = {}
        edges: list[Edge] = []

        for note in sorted(self.corpus_dir.rglob("*.md")):
            fm = self._parse_frontmatter(note)
            if not fm:
                continue
            rel = note.relative_to(self.corpus_dir)

            for raw in _as_list(fm.get("entities")):
                if not isinstance(raw, dict):
                    log.warning("%s: skipping non-dict entity %r", rel, raw)
                    continue
                eid = raw.get("id")
                if not eid:
                    log.warning("%s: skipping entity with no id", rel)
                    continue
                props = {k: v for k, v in raw.items() if k not in _ENTITY_RESERVED}
                props["source_note"] = str(rel)
                entities[eid] = Entity(
                    id=eid,
                    name=raw.get("canonical") or raw.get("name") or eid,
                    entity_type=raw.get("type") or "unknown",
                    properties=props,
                )

            # _flatten_edges absorbs the double-nested `edges: [[...]]`
            # authoring slip (a YAML indentation bug seen in the corpus) so
            # one malformed note doesn't take down the whole snapshot.
            for raw in self._flatten_edges(fm.get("edges"), rel):
                src = raw.get("from")
                dst = raw.get("to")
                etype = raw.get("type")
                if not (src and dst and etype):
                    log.warning("%s: skipping edge missing from/to/type: %r", rel, raw)
                    continue
                props = {k: v for k, v in raw.items() if k not in {"from", "to", "type"}}
                props["source_note"] = str(rel)
                edges.append(
                    Edge(source_id=src, target_id=dst, edge_type=etype, properties=props)
                )

        # Stub any edge endpoint that was never declared as an entity.
        for e in edges:
            for endpoint in (e.source_id, e.target_id):
                if endpoint not in entities:
                    entities[endpoint] = Entity(
                        id=endpoint,
                        name=endpoint,
                        entity_type="unknown",
                        properties={"stub": True},
                    )

        self._snapshot = (list(entities.values()), edges)
        log.info(
            "CorpusAdapter snapshot: %d entities (%d stubbed), %d edges",
            len(self._snapshot[0]),
            sum(1 for x in self._snapshot[0] if x.properties.get("stub")),
            len(edges),
        )
        return self._snapshot

    # --- Optional overrides --------------------------------------------

    def get_ontology_source(self) -> dict:
        """Return the corpus's declared ontology for Cat 8, if present.

        Looks for ``ontology.yaml`` in the vault dir and its parent (the
        good-dog layout keeps it one level up from ``vault/``). Falls back
        to the base 'inferred' behaviour when there's no declared schema.
        """
        for cand in (self.corpus_dir / "ontology.yaml", self.corpus_dir.parent / "ontology.yaml"):
            if cand.exists():
                doc = yaml.safe_load(cand.read_text()) or {}
                schema = (doc.get("entity_types") or []) + (doc.get("edge_types") or [])
                return {"type": "declared", "schema": schema, "documentation": str(cand)}
        return {"type": "inferred", "schema": [], "documentation": ""}

    # --- Helpers -------------------------------------------------------

    @staticmethod
    def _parse_frontmatter(note: Path) -> Optional[dict]:
        text = note.read_text()
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return None
        try:
            return yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            log.warning("%s: unparseable frontmatter (%s)", note.name, exc)
            return None

    @staticmethod
    def _flatten_edges(raw: Any, rel: Any) -> list[dict]:
        """Yield edge dicts, tolerating a `edges: [[ {...}, {...} ]]` nesting.

        The good-dog corpus had notes where a stray indent double-nested the
        edges list. Rather than crash (the validator did), flatten one level
        and warn — the graph is still recoverable.
        """
        out: list[dict] = []
        for item in _as_list(raw):
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, list):
                log.warning("%s: double-nested edges list flattened", rel)
                out.extend(x for x in item if isinstance(x, dict))
            else:
                log.warning("%s: skipping non-dict edge entry %r", rel, item)
        return out


def _as_list(value: Any) -> list:
    """None -> [], a list stays a list, a scalar becomes a 1-element list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
