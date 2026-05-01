"""Category 5: Gap Detection — The Missing Room.

Produces a diagnostic reading of structural gaps in a memory system's
graph. External (L3) detection only — uses the topology layer; does
not ask the system to surface its own gaps (that would be L1/L2 and
is adapter-driven).

Signals reported:

  - Components, isolated-node count, structural bridges (L3a): crude
    "these parts of the graph aren't connected at all" reading.
  - Betti-1 persistence on the largest component (L3b): loops that
    survive the Vietoris-Rips filtration are stable structural holes
    inside an otherwise connected region.
  - Candidate gaps (L3c): pairs of components that share an
    entity_type — i.e., they hold the same kind of thing but are
    structurally disconnected. This is a heuristic; a maintainer
    decides whether the missing edge is a real gap or expected.

When called with ``seeded_missing_edges`` (from a fixture or a
hand-curated ground-truth file), the scorer also reports gap recall
and precision against that truth.

The spec defines gap recall as "fraction of seeded gaps the system
identifies." For external detection here, a seeded edge (u, v) is
considered recalled when u and v end up in different components and
the (component_u, component_v) pair is reported as a candidate gap.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

from sme.adapters.base import Edge, Entity
from sme.topology.analyzer import TopologyAnalyzer

log = logging.getLogger(__name__)


@dataclass
class CandidateGap:
    """One candidate missing-edge region between two components.

    The score rewards pairs that share *rare* entity types across
    sizable components. A high score means: "two meaningfully-sized
    regions hold the same kind of uncommon thing but have no edge
    between them." A low score usually reflects a shared-universal-
    type match (e.g., both components contain a 'person' node —
    uninformative on large graphs).
    """

    component_a: int
    component_b: int
    shared_entity_types: list[str]
    size_a: int
    size_b: int
    score: float
    example_ids_a: list[str] = field(default_factory=list)
    example_ids_b: list[str] = field(default_factory=list)


@dataclass
class GapDetectionReport:
    # Structural summary
    nodes: int
    edges: int
    components: int
    largest_component_size: int
    isolated_nodes: int
    bridges: list[tuple[str, str]]  # undirected, structural

    # Persistent homology on the largest component
    betti_0_largest: int
    betti_1_largest: int
    h1_max_persistence: float
    h1_skipped: bool = False
    h1_skip_reason: str = ""

    # Candidate gaps across components (top-K by score, post-filter)
    candidate_gaps: list[CandidateGap] = field(default_factory=list)
    # Pre-filter total, so a maintainer can tell "we filtered 21k → 20"
    candidate_gaps_considered: int = 0

    # When seeded_missing_edges is provided
    gap_recall: Optional[float] = None
    gap_precision: Optional[float] = None

    # Detection level achieved (L1/L2 require adapter introspection,
    # which this scorer does not attempt). L3 is achieved whenever the
    # topology layer produces any external gap signal.
    detection_level: str = "L3"


def _structural_bridges(G: nx.MultiDiGraph) -> list[tuple[str, str]]:
    """Bridges on the undirected, simple projection of G.

    Multi-edges are collapsed so nx.bridges doesn't see parallel edges
    as separate connections.
    """
    simple = nx.Graph()
    simple.add_nodes_from(G.nodes())
    for u, v, _ in G.edges(keys=True):
        if u != v:
            simple.add_edge(u, v)
    return [(u, v) for u, v in nx.bridges(simple)]


def _candidate_gaps(
    analyzer: TopologyAnalyzer,
    components: list[set[str]],
    *,
    min_size: int = 3,
    max_type_prevalence: float = 0.5,
    top_k: int = 20,
) -> tuple[list[CandidateGap], int]:
    """Rank candidate missing-edge pairs across components.

    A pair ``(comp_i, comp_j)`` is considered only when both components
    meet ``min_size``. Shared entity types are weighted by rarity —
    types that appear in more than ``max_type_prevalence`` of the
    sized components are treated as universal and contribute nothing
    to the score (a 'person' node turning up in every component is
    not a signal that any specific pair should be connected).

    Score per pair::

        score = Σ_{t ∈ shared_rare} rarity(t) · √min(size_a, size_b)

    where ``rarity(t) = 1 / (1 + log2(num_sized_components_with_t))``.
    The √min size term prevents a huge component from dominating every
    pair it participates in.

    Returns ``(top_k_gaps, total_pairs_considered)`` so a caller can
    report "showing 20 of 1,847 considered."
    """
    if len(components) < 2:
        return [], 0

    sized_indices = [i for i, c in enumerate(components) if len(c) >= min_size]
    if len(sized_indices) < 2:
        return [], 0

    type_by_comp: dict[int, set[str]] = {}
    nodes_by_comp: dict[int, list[str]] = {}
    for i in sized_indices:
        types: set[str] = set()
        nodes_sorted: list[str] = []
        for node_id in components[i]:
            data = analyzer.G.nodes[node_id]
            t = data.get("entity_type")
            if t:
                types.add(t)
            nodes_sorted.append(node_id)
        type_by_comp[i] = types
        # Deterministic order for "example_ids" rendering
        nodes_sorted.sort()
        nodes_by_comp[i] = nodes_sorted

    # Type prevalence across sized components only
    type_occurrences: dict[str, int] = {}
    for types in type_by_comp.values():
        for t in types:
            type_occurrences[t] = type_occurrences.get(t, 0) + 1

    prevalence_limit = max_type_prevalence * len(sized_indices)

    def is_discriminating(t: str) -> bool:
        """A type is discriminating when it's not ~universal among sized
        components. Small-graph degenerate case: if every sized component
        happens to share one type (e.g., a 2-sized-component fixture),
        fall back to treating all shared types as weakly discriminating
        so the signal isn't lost."""
        return type_occurrences.get(t, 0) <= prevalence_limit

    # Degenerate small-graph case: ≤ 2 sized components means rarity
    # math is meaningless (every shared type is "in 100%"). Keep the
    # pair and rank it with a flat rarity of 1.0.
    flat_rarity_mode = len(sized_indices) <= 2

    def rarity(t: str) -> float:
        if flat_rarity_mode:
            return 1.0
        return 1.0 / (1.0 + math.log2(type_occurrences[t]))

    considered = 0
    scored: list[CandidateGap] = []
    for ii, i in enumerate(sized_indices):
        for j in sized_indices[ii + 1:]:
            considered += 1
            shared = type_by_comp[i] & type_by_comp[j]
            if not shared:
                continue
            rare_shared = (
                shared if flat_rarity_mode else {t for t in shared if is_discriminating(t)}
            )
            if not rare_shared:
                continue

            size_a = len(components[i])
            size_b = len(components[j])
            score = sum(rarity(t) for t in rare_shared) * math.sqrt(
                min(size_a, size_b)
            )
            scored.append(
                CandidateGap(
                    component_a=i,
                    component_b=j,
                    shared_entity_types=sorted(rare_shared),
                    size_a=size_a,
                    size_b=size_b,
                    score=score,
                    example_ids_a=nodes_by_comp[i][:3],
                    example_ids_b=nodes_by_comp[j][:3],
                )
            )

    scored.sort(key=lambda g: g.score, reverse=True)
    return scored[:top_k], considered


def score_gap_detection(
    entities: list[Entity],
    edges: list[Edge],
    *,
    seeded_missing_edges: Optional[list[tuple[str, str]]] = None,
    run_homology: bool = True,
    betti_max_nodes: int = 2000,
    min_component_size: int = 3,
    max_type_prevalence: float = 0.5,
    top_k: int = 20,
) -> GapDetectionReport:
    """Produce a Cat 5 diagnostic reading for a graph snapshot.

    Args:
        entities, edges: the graph snapshot (adapter-agnostic).
        seeded_missing_edges: known ground-truth gaps, for recall/
            precision scoring. Pairs are direction-agnostic.
        run_homology: if False, skip the Ripser pass (handy when the
            optional ``[topology]`` extra isn't installed).
        betti_max_nodes: forwarded to ``TopologyAnalyzer.betti_numbers``
            — components larger than this are skipped to avoid Ripser
            blowing up on dense graphs.
        min_component_size: candidate gaps only consider component
            pairs where both sides have at least this many nodes.
            Filters out orphan-pair noise. Default 3.
        max_type_prevalence: entity types present in more than this
            fraction of sized components are treated as universal and
            ignored when scoring. Default 0.5 (types in > 50% of sized
            components are not signal).
        top_k: cap the returned candidate gaps. The report also
            records how many pairs were considered pre-filter.
    """
    analyzer = TopologyAnalyzer(entities, edges)
    G = analyzer.G
    undirected = G.to_undirected(as_view=False)

    components_raw = list(nx.connected_components(undirected))
    components = sorted(components_raw, key=len, reverse=True)

    isolated = [c for c in components if len(c) == 1]
    largest = components[0] if components else set()

    bridges = _structural_bridges(G)

    betti_0 = 0
    betti_1 = 0
    h1_max_persistence = 0.0
    h1_skipped = False
    h1_skip_reason = ""

    if run_homology and largest:
        try:
            betti = analyzer.betti_numbers(
                component="largest", max_dim=1, max_nodes=betti_max_nodes
            )
            betti_0 = betti.betti_0
            betti_1 = betti.betti_1
            h1_max_persistence = betti.max_h1_persistence
            h1_skipped = betti.skipped
            h1_skip_reason = betti.skip_reason
        except ImportError:
            h1_skipped = True
            h1_skip_reason = (
                "ripser not installed; install the [topology] extra to get "
                "Betti-1 persistence readings"
            )

    candidates, considered = _candidate_gaps(
        analyzer,
        components,
        min_size=min_component_size,
        max_type_prevalence=max_type_prevalence,
        top_k=top_k,
    )

    gap_recall: Optional[float] = None
    gap_precision: Optional[float] = None
    if seeded_missing_edges is not None:
        node_to_comp: dict[str, int] = {}
        for idx, comp in enumerate(components):
            for n in comp:
                node_to_comp[n] = idx

        reported_pairs = {
            frozenset({c.component_a, c.component_b}) for c in candidates
        }

        recalled = 0
        considered = 0
        for u, v in seeded_missing_edges:
            cu = node_to_comp.get(u)
            cv = node_to_comp.get(v)
            if cu is None or cv is None:
                continue
            considered += 1
            if cu == cv:
                continue  # Endpoints already in same component — not a cross-cluster gap
            if frozenset({cu, cv}) in reported_pairs:
                recalled += 1

        gap_recall = (recalled / considered) if considered else 0.0
        gap_precision = (
            (recalled / len(reported_pairs)) if reported_pairs else 0.0
        )

    return GapDetectionReport(
        nodes=G.number_of_nodes(),
        edges=G.number_of_edges(),
        components=len(components),
        largest_component_size=len(largest),
        isolated_nodes=len(isolated),
        bridges=bridges,
        betti_0_largest=betti_0,
        betti_1_largest=betti_1,
        h1_max_persistence=h1_max_persistence,
        h1_skipped=h1_skipped,
        h1_skip_reason=h1_skip_reason,
        candidate_gaps=candidates,
        candidate_gaps_considered=considered,
        gap_recall=gap_recall,
        gap_precision=gap_precision,
    )


# --- Interpretive bands -----------------------------------------------
#
# Default thresholds for knowledge-graph-shaped data. Document-centric
# or narrative graphs routinely exceed these (every Document→Entity
# leaf is a bridge by definition) — the "Reading" section says so
# explicitly rather than flagging every narrative graph as broken.

_CONNECTIVITY_HEALTHY = 0.95
_CONNECTIVITY_WARN = 0.80

_ISOLATE_HEALTHY = 0.01
_ISOLATE_WARN = 0.05

_BRIDGE_HEALTHY = 0.10
_BRIDGE_WARN = 0.25


def _band(value: float, healthy: float, warn: float, *, lower_is_better: bool) -> str:
    """Return 'healthy' / 'warning' / 'concerning' — mechanism language,
    not pass/fail. The spec's diagnostic-not-benchmark rule means these
    bands describe where the reading sits, not whether the system is
    good or bad."""
    if lower_is_better:
        if value <= healthy:
            return "healthy"
        if value <= warn:
            return "warning"
        return "concerning"
    if value >= healthy:
        return "healthy"
    if value >= warn:
        return "warning"
    return "concerning"


def format_report(report: GapDetectionReport) -> str:
    """Human-readable rendering with an interpretive Reading section.

    The top block is raw measurements. The Reading block translates
    each measurement into a band (healthy / warning / concerning) and
    states the mechanism behind it, so a maintainer running this on
    their own graph can tell the difference between "number is big
    because my graph is shaped like that" and "number is big because
    enrichment has a problem."
    """
    lines = [
        "Cat 5 — The Missing Room",
        "════════════════════════",
        "",
        "Measurements",
        "─" * 60,
        f"  Nodes:                 {report.nodes:,}",
        f"  Edges:                 {report.edges:,}",
        f"  Components:            {report.components:,}",
        f"  Largest component:     {report.largest_component_size:,}",
        f"  Isolated nodes:        {report.isolated_nodes:,}",
        f"  Structural bridges:    {len(report.bridges):,}",
    ]
    if report.bridges and len(report.bridges) <= 10:
        for u, v in report.bridges[:10]:
            lines.append(f"    {u} — {v}")

    lines.append("")
    lines.append(f"  Betti-0 (largest):     {report.betti_0_largest}")
    lines.append(f"  Betti-1 (largest):     {report.betti_1_largest}")
    lines.append(
        f"  H1 max persistence:    {report.h1_max_persistence:.3f}"
    )
    if report.h1_skipped:
        lines.append(f"    (homology skipped: {report.h1_skip_reason})")

    lines.append("")
    lines.append(
        f"  Candidate gaps:        {len(report.candidate_gaps):,} shown"
        f" of {report.candidate_gaps_considered:,} considered"
    )
    for gap in report.candidate_gaps[:5]:
        lines.append(
            f"    [score {gap.score:5.2f}]  "
            f"comp#{gap.component_a} ({gap.size_a}) ↔ comp#{gap.component_b} ({gap.size_b})"
        )
        lines.append(
            f"        shared rare types: {', '.join(gap.shared_entity_types)}"
        )
        if gap.example_ids_a or gap.example_ids_b:
            lines.append(
                f"        example a: {', '.join(gap.example_ids_a)}"
            )
            lines.append(
                f"        example b: {', '.join(gap.example_ids_b)}"
            )
    if len(report.candidate_gaps) > 5:
        lines.append(f"    ... +{len(report.candidate_gaps) - 5} more (increase --top-k to see)")

    if report.gap_recall is not None:
        lines.append("")
        lines.append(
            f"  Seeded-gap recall:     {report.gap_recall:.2f}"
        )
        lines.append(
            f"  Seeded-gap precision:  {report.gap_precision:.2f}"
        )

    # --- Reading --------------------------------------------------

    lines.append("")
    lines.append("Reading")
    lines.append("─" * 60)

    if report.nodes == 0:
        lines.append("  Empty graph — nothing to read.")
        lines.append("")
        lines.append(f"  Detection level:       {report.detection_level}")
        return "\n".join(lines)

    connectivity = report.largest_component_size / report.nodes
    isolate_pct = report.isolated_nodes / report.nodes
    bridge_ratio = (len(report.bridges) / report.edges) if report.edges else 0.0

    conn_band = _band(
        connectivity, _CONNECTIVITY_HEALTHY, _CONNECTIVITY_WARN, lower_is_better=False
    )
    iso_band = _band(
        isolate_pct, _ISOLATE_HEALTHY, _ISOLATE_WARN, lower_is_better=True
    )
    br_band = _band(
        bridge_ratio, _BRIDGE_HEALTHY, _BRIDGE_WARN, lower_is_better=True
    )

    lines.append(
        f"  ● Connectivity: {connectivity:.1%} of entities in the largest "
        f"component [{conn_band}]."
    )
    if conn_band == "healthy":
        lines.append(
            "      Knowledge-graph band: >95%. Enrichment is integrating "
            "most content into one connected region."
        )
    elif conn_band == "warning":
        lines.append(
            "      Knowledge-graph band: 80–95%. Some content islands "
            "aren't being linked. Check whether the extractor creates "
            "cross-document entity references."
        )
    else:
        lines.append(
            "      Knowledge-graph band: <80%. Substantial fragmentation. "
            "Either the domain is genuinely disjoint (multiple unrelated "
            "corpora) or the extractor isn't producing bridging edges."
        )

    lines.append(
        f"  ● Isolates: {isolate_pct:.1%} of entities have no edges "
        f"({report.isolated_nodes:,} of {report.nodes:,}) [{iso_band}]."
    )
    if iso_band == "healthy":
        lines.append(
            "      Extractor is producing entities with accompanying "
            "relationships — the usual shape."
        )
    elif iso_band == "warning":
        lines.append(
            "      Elevated isolate fraction. Likely cause: extractor "
            "promotes mentions to entities without attaching a relationship. "
            "These entities are unreachable from any traversal and waste "
            "the extraction cost."
        )
    else:
        lines.append(
            "      High isolate fraction. The extraction pipeline is "
            "producing orphan nodes at a rate that suggests a prompt or "
            "post-processing bug — orphans should be rare by design."
        )

    lines.append(
        f"  ● Bridge fragility: {bridge_ratio:.1%} of edges are structural "
        f"bridges [{br_band}]."
    )
    if br_band == "healthy":
        lines.append(
            "      Edges are redundant — removing one rarely disconnects "
            "a subregion. Robust shape."
        )
    elif br_band == "warning":
        lines.append(
            "      Moderate bridge density. Watch for enrichment patterns "
            "that create single-edge connections (e.g., a long chain of "
            "1-hop extractions)."
        )
    else:
        lines.append(
            "      High bridge density. Common in document-centric graphs "
            "where every Document→Entity edge is a bridge by construction. "
            "If your graph is a Document→Entity star, this is structural, "
            "not a bug. If it's a semantic knowledge graph, tighten entity "
            "linking — every bridge is a single point of failure."
        )

    if not report.h1_skipped and report.betti_1_largest > 0:
        lines.append(
            f"  ● Structural holes: {report.betti_1_largest} persistent H1 "
            f"feature(s) on the largest component "
            f"(max persistence {report.h1_max_persistence:.2f} hops)."
        )
        lines.append(
            "      Loops in the knowledge core that don't fill in under "
            "the Vietoris-Rips filtration. Long-persistence H1 bars usually "
            "mark real gaps where an enriching edge would close the loop."
        )
    elif report.h1_skipped:
        lines.append(
            "  ● Structural holes: not measured "
            f"({report.h1_skip_reason})."
        )
    else:
        lines.append(
            "  ● Structural holes: none on the largest component."
        )
        lines.append(
            "      Either your graph is genuinely tree-like, or cycles "
            "all close fast enough that triangles fill them in. For a "
            "dense knowledge graph, this is expected."
        )

    # Candidate gap framing
    if report.candidate_gaps:
        kept = len(report.candidate_gaps)
        considered = report.candidate_gaps_considered
        lines.append(
            f"  ● Missing rooms: {kept} top-scoring candidate gap(s), "
            f"filtered from {considered} component pairs."
        )
        lines.append(
            "      Each candidate is two sized components that share a "
            "RARE entity type but have no edge between them. Investigate "
            "the highest-scoring pair first — if it looks like an "
            "enrichment drop-off, the fix is an extractor rule; if it "
            "looks genuinely distinct, the components are correctly "
            "separate and the heuristic over-fired."
        )
    elif report.components > 1:
        lines.append(
            "  ● Missing rooms: none detected above the min-size / "
            "rare-type bar."
        )
        lines.append(
            "      Smaller components exist but either fall below "
            "--min-component-size or share only universal types with "
            "the rest of the graph. Lower the thresholds to see them."
        )

    if report.gap_recall is not None:
        lines.append("")
        lines.append(
            f"  Seeded-gap scoring: recall={report.gap_recall:.2f}, "
            f"precision={report.gap_precision:.2f}."
        )

    lines.append("")
    lines.append(f"  Detection level:       {report.detection_level}")
    lines.append(
        "  (L3 = external topology reading; L1/L2 require adapter-side "
        "introspection APIs that most systems don't expose.)"
    )
    return "\n".join(lines)
