"""Defect injection: prove `check` catches the damage it claims to catch.

A green nightly means "nothing moved beyond tolerance". On its own that
says nothing about whether real damage WOULD move something beyond
tolerance. This harness answers that directly: take a real snapshot, apply
one realistic defect at several sizes to an in-memory copy, score the copy
with the same `score_reading` the nightly uses, compare it against the
unmutated reading with the same `compare_readings_keyed`, and record
whether the expected finding fired.

The output is a detection matrix: per defect, the smallest size that is
caught. That turns each tolerance from a guess into a measured sensitivity
("losing 10% of PART_OF edges is caught; 5% is not").

Two kinds of rows:

- **Defects** model failures that have happened or plausibly will: an
  extractor that stops emitting one relation, a prune that over-reaches, a
  re-typing bug, an edge writer that dies while nodes keep landing, a
  re-ingest that duplicates entities, an extractor emitting a relation the
  schema never declared. Each names the finding key it should produce.
- **Controls** are changes that must NOT alarm: a no-op, and a legitimate
  document-layer purge. A control that fires is a false alarm, which costs
  as much as a miss: an alarm that cries wolf gets ignored.

Mutations act on copies of the snapshot lists, never on a database. No
graph is written, so none of the LadybugDB write hazards apply.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from sme.adapters.base import Edge, Entity
from sme.check_regression import Tolerances, compare_readings_keyed

Graph = tuple[list[Entity], list[Edge]]

# Name used for the injected undeclared relation. Unmistakable in output.
INJECTED_EDGE_TYPE = "SME_INJECTED_UNDECLARED"


@dataclass
class Target:
    """What the defects aim at, chosen from the snapshot itself."""

    edge_type: str  # the largest relation: the one whose loss matters most
    small_edge_type: Optional[str]  # a small but real relation, for "vanished"
    entity_type: str  # the knowledge type with the most connected entities
    doc_entity_type: Optional[str]  # a document-layer type, for the purge control


@dataclass
class Defect:
    name: str
    description: str
    mutate: Callable[[Graph, float, Target, random.Random], Graph]
    expects: Callable[[Target], str]  # finding-key prefix that must fire
    control: bool = False  # True = must NOT produce any finding


@dataclass
class Row:
    defect: str
    size: float
    control: bool
    expected: str
    fired: list[str] = field(default_factory=list)
    detected: bool = False  # defect: expected key fired; control: nothing fired
    changed: int = 0  # how many edges/entities the mutation touched


# --- target selection ------------------------------------------------------

DOC_LAYER_TYPES = ("Note", "Chunk", "note", "chunk")


def choose_targets(entities: list[Entity], edges: list[Edge]) -> Target:
    """Aim at the parts of THIS graph whose damage would matter most."""
    etypes = Counter(e.edge_type for e in edges)
    if not etypes:
        raise ValueError("snapshot has no edges; nothing to inject into")
    largest = etypes.most_common(1)[0][0]
    small = [t for t, n in etypes.items() if 50 <= n <= 2000 and t != largest]
    small_type = min(small, key=lambda t: etypes[t]) if small else None

    by_id = {e.id: e for e in entities}
    connected = Counter()
    seen: set[str] = set()
    for ed in edges:
        for nid in (ed.source_id, ed.target_id):
            if nid not in seen and nid in by_id:
                seen.add(nid)
                connected[by_id[nid].entity_type] += 1
    knowledge = [(t, n) for t, n in connected.most_common() if t not in DOC_LAYER_TYPES]
    if not knowledge:
        raise ValueError("no connected non-document entity type to aim at")
    present = Counter(e.entity_type for e in entities)
    doc = next((t for t in DOC_LAYER_TYPES if present.get(t, 0) >= 100), None)
    return Target(largest, small_type, knowledge[0][0], doc)


# --- mutations --------------------------------------------------------------
# Each takes (graph, size in 0..1, target, rng) and returns a NEW graph.
# `size` is the fraction of the targeted population that is damaged.


def _drop_edge_type(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """An extractor stops emitting one relation; a prune over-reaches on it."""
    ents, eds = g
    keep = [e for e in eds if e.edge_type != t.edge_type or rng.random() >= size]
    return ents, keep


def _drop_edges(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """Edges lost across the board: a bad dedup, a partial restore."""
    ents, eds = g
    return ents, [e for e in eds if rng.random() >= size]


def _retype(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """A re-typing bug collapses one relation into another."""
    ents, eds = g
    other = next((e.edge_type for e in eds if e.edge_type != t.edge_type), None)
    out = [
        replace(e, edge_type=other) if e.edge_type == t.edge_type and rng.random() < size else e
        for e in eds
    ]
    return ents, out


def _orphan_type(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """Entities of one type lose all their edges (a cascade delete, a bad merge)."""
    ents, eds = g
    hit = {e.id for e in ents if e.entity_type == t.entity_type and rng.random() < size}
    return ents, [e for e in eds if e.source_id not in hit and e.target_id not in hit]


def _unlinked_ingest(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """Nodes keep landing but the edge writer has died: new entities, no edges.

    `size` is new entities as a fraction of the existing count of that type.
    """
    ents, eds = g
    n = int(sum(1 for e in ents if e.entity_type == t.entity_type) * size)
    new = [
        Entity(id=f"sme-injected-{i}", name=f"sme injected entity {i}",
               entity_type=t.entity_type)
        for i in range(n)
    ]
    return ents + new, eds


def _duplicate_entities(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """A re-ingest re-creates existing entities under new ids, with the
    near-miss spellings real duplicates have (case, spacing, punctuation)."""
    ents, eds = g
    variants = (str.upper, str.lower, lambda s: f" {s} ", lambda s: s.replace(" ", "-"))
    pool = [e for e in ents if e.entity_type == t.entity_type and e.name]
    dupes = [
        replace(e, id=f"{e.id}::sme-dup", name=rng.choice(variants)(e.name), properties={})
        for e in pool
        if rng.random() < size
    ]
    return ents + dupes, eds


def _undeclared_relation(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """An extractor starts emitting a relation the schema never declared."""
    ents, eds = g
    out = [
        replace(e, edge_type=INJECTED_EDGE_TYPE)
        if e.edge_type == t.edge_type and rng.random() < size else e
        for e in eds
    ]
    return ents, out


def _vanish_small_type(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """A small but real relation disappears entirely (size is ignored)."""
    ents, eds = g
    return ents, [e for e in eds if e.edge_type != t.small_edge_type]


# Controls: these must NOT alarm.


def _noop(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    return list(g[0]), list(g[1])


def _purge_documents(g: Graph, size: float, t: Target, rng: random.Random) -> Graph:
    """Legitimate de-pollution: drop a share of document-layer nodes and their
    edges, as the 2026-06-27 vendored-tree purge did. Must not read as damage."""
    ents, eds = g
    if not t.doc_entity_type:
        return ents, eds
    gone = {e.id for e in ents if e.entity_type == t.doc_entity_type and rng.random() < size}
    return (
        [e for e in ents if e.id not in gone],
        [e for e in eds if e.source_id not in gone and e.target_id not in gone],
    )


DEFECTS: list[Defect] = [
    Defect("drop_edge_type", "largest relation partly lost",
           _drop_edge_type, lambda t: f"edge_type:{t.edge_type}"),
    Defect("drop_edges", "edges lost across all relations",
           _drop_edges, lambda t: "edges"),
    Defect("retype", "largest relation re-typed into another",
           _retype, lambda t: f"edge_type:{t.edge_type}"),
    Defect("orphan_type", "entities of the main knowledge type lose all edges",
           # Prefix match: the per-type key (isolated_share:<type>) or the
           # global one. Per-type needs >=200 entities of the type; on small
           # graphs only the global share can fire, and that IS a detection.
           _orphan_type, lambda t: "isolated_share"),
    Defect("unlinked_ingest", "new entities arrive with no edges",
           _unlinked_ingest, lambda t: "isolated_share"),
    Defect("duplicate_entities", "re-ingest duplicates entities (near-miss names)",
           _duplicate_entities, lambda t: "canonical_collisions"),
    Defect("undeclared_relation", "extractor emits a relation not in the schema",
           _undeclared_relation, lambda t: f"cat8:undeclared_edge:{INJECTED_EDGE_TYPE}"),
    Defect("vanish_small_type", "a small declared relation disappears",
           _vanish_small_type, lambda t: f"edge_type:{t.small_edge_type}"),
    Defect("noop", "control: nothing changes", _noop, lambda t: "", control=True),
    Defect("purge_documents", "control: legitimate document-layer purge",
           _purge_documents, lambda t: "", control=True),
]


def _changed(before: Graph, after: Graph) -> int:
    """Rough size of a mutation: entities added/removed + edges changed."""
    be, bd = before
    ae, ad = after
    edge_delta = len(set(map(_edge_key, bd)) ^ set(map(_edge_key, ad)))
    return abs(len(ae) - len(be)) + edge_delta


def _edge_key(e: Edge) -> tuple[str, str, str]:
    return (e.source_id, e.target_id, e.edge_type)


def run_matrix(
    entities: list[Entity],
    edges: list[Edge],
    *,
    sizes: tuple[float, ...] = (0.02, 0.05, 0.10, 0.25),
    ontology: Optional[str] = None,
    defects: Optional[list[str]] = None,
    tol: Optional[Tolerances] = None,
    seed: int = 13,
    score: Optional[Callable[[list[Entity], list[Edge]], dict]] = None,
) -> tuple[Target, list[Row]]:
    """Score every (defect, size) against the unmutated baseline reading.

    `score` defaults to the nightly's own `score_reading`; it is injectable
    so the unit tests can run on tiny graphs without the full pipeline.
    """
    if score is None:
        from sme.reading import score_reading

        def score(ents, eds):
            return score_reading(ents, eds, ontology=ontology)[0]

    target = choose_targets(entities, edges)
    baseline = score(entities, edges)
    rows: list[Row] = []
    for d in DEFECTS:
        if defects and d.name not in defects:
            continue
        if d.name == "vanish_small_type" and not target.small_edge_type:
            continue
        if d.name == "undeclared_relation" and not ontology:
            continue  # Cat 8 is what detects it; skip rather than fake a miss
        if d.name == "purge_documents" and not target.doc_entity_type:
            # No document layer to purge: the mutation would be a no-op and
            # the control would "pass" having tested nothing. Skip it.
            continue
        for size in (sizes if d.name not in ("vanish_small_type", "noop") else (1.0,)):
            rng = random.Random(f"{seed}:{d.name}:{size}")
            mutated = d.mutate((entities, edges), size, target, rng)
            keys = [k for k, _ in compare_readings_keyed(baseline, score(*mutated), tol)]
            expected = d.expects(target)
            detected = (not keys) if d.control else any(k.startswith(expected) for k in keys)
            rows.append(Row(d.name, size, d.control, expected, keys, detected,
                            _changed((entities, edges), mutated)))
    return target, rows


def format_matrix(target: Target, rows: list[Row]) -> str:
    lines = [
        f"targets: largest relation={target.edge_type}, small relation="
        f"{target.small_edge_type}, knowledge type={target.entity_type}, "
        f"document type={target.doc_entity_type}",
        "",
        f"{'defect':<22}{'size':>6}  {'result':<10}{'touched':>9}  findings",
    ]
    for r in rows:
        if r.control:
            result = "ok" if r.detected else "FALSE ALARM"
        else:
            result = "caught" if r.detected else "MISSED"
        lines.append(
            f"{r.defect:<22}{r.size:>6.0%}  {result:<10}{r.changed:>9}  "
            f"{', '.join(r.fired) or '-'}"
        )
    # The headline: the smallest size each defect is caught at.
    lines.append("")
    lines.append("smallest size caught:")
    for name in dict.fromkeys(r.defect for r in rows if not r.control):
        caught = [r.size for r in rows if r.defect == name and r.detected]
        lines.append(f"  {name:<22}{min(caught):.0%}" if caught else f"  {name:<22}never (at tested sizes)")
    alarms = [r for r in rows if r.control and not r.detected]
    lines.append(f"false alarms on controls: {len(alarms)}")
    return "\n".join(lines)
