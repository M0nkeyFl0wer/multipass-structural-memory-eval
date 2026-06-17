"""Category 8 — Counterfactual re-projection harness (Phase 2, piece 2).

This module implements the "counterfactual" half of the external-standard-fit
(Cat 8f) work. Once :func:`sme.categories.external_fit.score_external_fit` has
produced a ``corpus_term -> standard_term`` mapping (its ``alignments`` list),
we can ask a principled, SME-shaped question:

    If we RE-TYPE the very same facts under the standard vocabulary and
    RE-RUN the structural probes, what MOVES?

That delta is the "ablation on a multi-relation graph" the project has been
chasing: it isolates what the *vocabulary choice* costs (or buys) the graph's
structure, holding the underlying facts fixed.

Honesty constraints baked into this module
------------------------------------------

1. A *pure* edge_type RENAME (one corpus type -> one distinct standard term,
   no two corpus types landing on the same standard term) changes only
   VOCABULARY-LEVEL quantities:
       - the edge_type distribution / entropy,
       - the number of distinct edge types (only if a rename collides with an
         already-present type, see below).
   It does NOT touch the graph TOPOLOGY: the node set is identical, every
   edge still connects the same (source_id, target_id), so component count,
   largest-component size, and modularity are provably UNCHANGED. We report
   those deltas as 0 and say *why* rather than fabricating movement.

2. A *merge* (two or more corpus types mapped onto the SAME standard term)
   collapses edge types. That DOES move vocabulary-level metrics (fewer
   distinct types, lower-entropy distribution) and can move any analysis that
   is *conditioned on edge_type* (e.g. an edge-type-aware modularity or a
   multi-relation reachability that distinguishes relations). It still does
   not move plain (relation-agnostic) connectivity, because no node or
   (source,target) pair is added or removed. We detect merges and flag them
   (``n_merged_groups``) so a reader knows topology-conditioned deltas are
   *eligible* to move.

3. The #45 precondition (jphein): the structural probes must read the FULL
   graph (or an explicitly uniform sample), never an order-dependent
   LIMIT-N / projected slice — otherwise the delta measures sampling bias,
   not ontology fit. We surface this as the ``full_graph`` flag: callers who
   know they handed us a sampled / projected snapshot pass ``full_graph=
   False``, and we attach a ``caveat`` to the report instead of silently
   emitting a delta. We cannot *prove* a list is the full graph from inside
   this function, so we record the caller's assertion and, when False, warn.

Probes chosen (all cheap, deterministic, computed self-contained here)
----------------------------------------------------------------------
    * ``n_distinct_edge_types`` — vocabulary cardinality. MOVES under a merge,
      and under a rename only if a renamed type collides with an existing one.
    * ``edge_type_entropy`` — Shannon entropy (bits) of the edge_type
      distribution. MOVES under any rename that changes the *labels'*
      multiset partition, i.e. under merges; a pure 1:1 rename leaves the
      partition (and therefore entropy) unchanged.
    * ``edge_type_distribution`` — the raw counts, for transparency.
    * ``n_components`` / ``largest_component_size`` — relation-agnostic
      connectivity via union-find over (source_id, target_id). PROVABLY
      UNCHANGED by any pure type remap (rename or merge); reported to make
      the honesty check explicit (delta must be 0).

Reachability (Cat 2c multi-hop) is deliberately *deferred*: relation-agnostic
reachability is unchanged by a type remap (same edges), and a relation-aware
reachability probe would need a query workload to be meaningful. Including it
here would either be trivially zero or fabricated, so we document the deferral
rather than emit a misleading number.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sme.adapters.base import Edge


# ---------------------------------------------------------------------------
# Mapping extraction
# ---------------------------------------------------------------------------

def edge_type_mapping_from_alignments(
    alignments: Iterable[Mapping[str, Any]],
    *,
    min_confidence: float = 0.0,
) -> Tuple[Dict[str, str], List[str]]:
    """Build a ``corpus_term -> standard_term`` edge-type mapping from the
    ``alignments`` list returned by ``score_external_fit``.

    Each alignment is expected to look like::

        {"corpus_term": ..., "corpus_kind": ..., "standard_term": ...,
         "confidence": ..., "outcome": ...}

    We keep only alignments that describe an *edge type* and that actually
    resolve to a standard term. ``corpus_kind`` is used to identify edge-type
    alignments when present (values containing ``edge``/``relation``/``rel``);
    if ``corpus_kind`` is absent we fall back to accepting any alignment that
    has both a ``corpus_term`` and a ``standard_term`` (the caller is then
    responsible for having filtered to edges).

    Under-specified terms (the same ``corpus_term`` mapped to MORE THAN ONE
    distinct ``standard_term`` across alignments) are AMBIGUOUS. We do NOT
    silently pick: we resolve them deterministically (highest confidence,
    then lexicographically smallest standard_term as a stable tie-break) and
    RECORD the corpus_term in the returned ``ambiguous_terms`` list so the
    report can surface the ambiguity. This keeps the harness reproducible
    (no dict-ordering dependence) while staying honest about the under-spec.

    Returns ``(mapping, ambiguous_terms)``.
    """
    # corpus_term -> list of (confidence, standard_term)
    candidates: Dict[str, List[Tuple[float, str]]] = {}

    for al in alignments:
        corpus_term = al.get("corpus_term")
        standard_term = al.get("standard_term")
        if not corpus_term or not standard_term:
            continue

        kind = al.get("corpus_kind")
        if kind is not None:
            k = str(kind).lower()
            if not ("edge" in k or "relation" in k or k == "rel" or "rel_" in k):
                continue

        conf = al.get("confidence", 0.0)
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.0
        if conf < min_confidence:
            continue

        candidates.setdefault(str(corpus_term), []).append((conf, str(standard_term)))

    mapping: Dict[str, str] = {}
    ambiguous_terms: List[str] = []

    for corpus_term, cands in candidates.items():
        distinct_targets = {st for _, st in cands}
        if len(distinct_targets) > 1:
            ambiguous_terms.append(corpus_term)
        # Deterministic resolution: max confidence, then smallest standard_term.
        best = sorted(cands, key=lambda cs: (-cs[0], cs[1]))[0]
        mapping[corpus_term] = best[1]

    ambiguous_terms.sort()
    return mapping, ambiguous_terms


# ---------------------------------------------------------------------------
# Re-projection
# ---------------------------------------------------------------------------

def reproject_edges(edges: Sequence[Edge], mapping: Mapping[str, str]) -> List[Edge]:
    """Return a NEW list of :class:`Edge` with ``edge_type`` replaced by its
    standard term per ``mapping`` (``corpus_term -> standard_term``).

    Edges whose type is not in ``mapping`` keep their original type. The input
    edges are never mutated; each output edge is a fresh object with a shallow
    copy of ``properties`` (so downstream mutation cannot leak back).
    """
    out: List[Edge] = []
    for e in edges:
        new_type = mapping.get(e.edge_type, e.edge_type)
        out.append(
            Edge(
                source_id=e.source_id,
                target_id=e.target_id,
                edge_type=new_type,
                properties=dict(e.properties) if e.properties else {},
            )
        )
    return out


# ---------------------------------------------------------------------------
# Cheap, deterministic structural probes (self-contained)
# ---------------------------------------------------------------------------

def _edge_type_distribution(edges: Sequence[Edge]) -> Dict[str, int]:
    return dict(Counter(e.edge_type for e in edges))


def _shannon_entropy_bits(counts: Mapping[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log2(p)
    return h


def _connectivity(entities: Sequence[Any], edges: Sequence[Edge]) -> Tuple[int, int]:
    """Relation-agnostic connected components via union-find over node ids.

    Returns ``(n_components, largest_component_size)``. Isolated entities (no
    incident edge) count as their own singleton components. Edge endpoints not
    present in ``entities`` are still treated as nodes (defensive).
    """
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        # path compression
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for ent in entities:
        find(ent.id)
    for e in edges:
        union(e.source_id, e.target_id)

    roots = [find(n) for n in parent]
    sizes = Counter(roots)
    if not sizes:
        return 0, 0
    return len(sizes), max(sizes.values())


def _probe(entities: Sequence[Any], edges: Sequence[Edge]) -> Dict[str, Any]:
    dist = _edge_type_distribution(edges)
    n_comp, largest = _connectivity(entities, edges)
    return {
        "n_distinct_edge_types": len(dist),
        "edge_type_entropy": _shannon_entropy_bits(dist),
        "edge_type_distribution": dist,
        "n_components": n_comp,
        "largest_component_size": largest,
    }


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def counterfactual_report(
    entities: Sequence[Any],
    edges: Sequence[Edge],
    alignments: Iterable[Mapping[str, Any]],
    *,
    full_graph: bool = True,
    reference_set: Optional[str] = None,
    min_confidence: float = 0.0,
) -> Dict[str, Any]:
    """Re-run the structural probes on the original graph and on the re-typed
    graph and return the deltas.

    Parameters
    ----------
    entities, edges:
        The graph in the universal representation. Per the #45 precondition
        these SHOULD be the full graph (or an explicitly uniform sample);
        ``full_graph`` records the caller's assertion about that.
    alignments:
        The ``alignments`` list from ``score_external_fit``. Filtered here to
        edge-type mappings (see :func:`edge_type_mapping_from_alignments`).
    full_graph:
        The #45 precondition flag. When ``False`` the returned report carries
        a ``caveat`` warning that the delta may reflect sampling bias rather
        than ontology fit.
    reference_set:
        Optional name of the external standard (e.g. "PROV-O", "schema.org")
        passed through to the report for provenance.
    min_confidence:
        Drop alignments below this confidence when building the mapping.

    Returns
    -------
    dict with keys:
        reference_set, n_edges, n_remapped, n_unmapped, ambiguous_terms,
        n_merged_groups, merged_groups, full_graph, mapping, before, after,
        deltas, notes, and (only when full_graph is False) caveat.
    """
    edges = list(edges)
    entities = list(entities)

    mapping, ambiguous_terms = edge_type_mapping_from_alignments(
        alignments, min_confidence=min_confidence
    )

    # How many edges actually get a (different) standard label vs. pass through.
    n_remapped = 0
    n_unmapped = 0
    for e in edges:
        if e.edge_type in mapping and mapping[e.edge_type] != e.edge_type:
            n_remapped += 1
        else:
            # Either not in the mapping at all, or maps to itself (a no-op).
            n_unmapped += 1

    # Merge detection: standard terms that multiple ORIGINAL corpus types
    # (present in this graph) collapse onto. Only merges can move
    # edge_type-conditioned topology metrics.
    present_types = {e.edge_type for e in edges}
    target_to_sources: Dict[str, List[str]] = {}
    for src in present_types:
        tgt = mapping.get(src, src)
        target_to_sources.setdefault(tgt, []).append(src)
    merged_groups = {
        tgt: sorted(srcs)
        for tgt, srcs in target_to_sources.items()
        if len(srcs) > 1
    }
    n_merged_groups = len(merged_groups)

    before = _probe(entities, edges)
    reprojected = reproject_edges(edges, mapping)
    after = _probe(entities, reprojected)

    deltas = {
        "n_distinct_edge_types": after["n_distinct_edge_types"]
        - before["n_distinct_edge_types"],
        "edge_type_entropy": after["edge_type_entropy"] - before["edge_type_entropy"],
        "n_components": after["n_components"] - before["n_components"],
        "largest_component_size": after["largest_component_size"]
        - before["largest_component_size"],
    }

    notes: List[str] = []
    notes.append(
        "Connectivity deltas (n_components, largest_component_size) are "
        "expected to be 0: a pure edge_type remap preserves the node set and "
        "every (source_id, target_id) pair, so relation-agnostic topology "
        "cannot change. A non-zero value here would indicate a bug."
    )
    if n_merged_groups == 0:
        notes.append(
            "No edge-type merges detected among edge types present in this "
            "graph: this is a pure 1:1 rename, so edge_type_entropy delta "
            "should also be 0 (the label partition is unchanged) and only "
            "n_distinct_edge_types can move, and only if a renamed type "
            "collides with an already-present standard label."
        )
    else:
        notes.append(
            f"{n_merged_groups} edge-type merge group(s) detected "
            f"({merged_groups}): merges collapse types, so "
            "n_distinct_edge_types and edge_type_entropy are eligible to "
            "move, and any edge_type-conditioned analysis could move. Plain "
            "connectivity still cannot."
        )
    notes.append(
        "Reachability (Cat 2c multi-hop) is deferred: relation-agnostic "
        "reachability is unchanged by a type remap, and a relation-aware "
        "probe needs a query workload to be meaningful."
    )

    report: Dict[str, Any] = {
        "reference_set": reference_set,
        "n_edges": len(edges),
        "n_remapped": n_remapped,
        "n_unmapped": n_unmapped,
        "ambiguous_terms": ambiguous_terms,
        "n_merged_groups": n_merged_groups,
        "merged_groups": merged_groups,
        "full_graph": full_graph,
        "mapping": mapping,
        "before": before,
        "after": after,
        "deltas": deltas,
        "notes": notes,
    }

    if not full_graph:
        report["caveat"] = (
            "full_graph=False: the probes were run over a sampled or "
            "projected slice of the graph, not the full graph. Per #45 the "
            "reported delta may reflect sampling bias (order-dependent "
            "LIMIT-N / projection) rather than genuine ontology fit. Re-run "
            "on the full graph (or an explicitly uniform sample) before "
            "drawing conclusions."
        )

    return report
