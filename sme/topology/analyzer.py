"""Topology analyzer for SME.

Backend-agnostic. Takes a graph snapshot (entities + edges from any
adapter) and runs structural analysis. NetworkX-backed.

First pass: structural_health, community_structure, edge_type_distribution,
filtered_subgraph (for Cat 4c monoculture detection).

Persistent homology via Ripser is deliberately left out of the first
pass — it's heavy on large graphs and not needed for the smoke test.
Add `betti_numbers()` when implementing Cat 5 gap detection.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

import networkx as nx

from sme.adapters.base import Edge, Entity

log = logging.getLogger(__name__)


@dataclass
class CommunityReport:
    count: int
    modularity: float
    sizes: list[int]  # descending
    inter_community_edges: int
    inter_community_ratio: float


@dataclass
class BettiReport:
    """Persistent homology result for a graph component.

    Betti-0 = number of connected components (H_0 features)
    Betti-1 = number of independent loops / topological holes (H1 cycles)

    For Cat 5 gap detection, we care about long-persistence H_1 features —
    loops that survive across a wide filtration range are stable
    topological gaps in the knowledge layer. (These are topological holes
    in the TDA sense, NOT Burt structural holes / brokerage — see
    ``TopologyAnalyzer.brokerage``.)
    """

    component_size: int
    betti_0: int
    betti_1: int
    # Each entry: (birth, death, persistence). For H_0, death is 'inf'
    # for the last component. For H_1, death should always be finite.
    h0_bars: list[tuple[float, float, float]]
    h1_bars: list[tuple[float, float, float]]
    max_h1_persistence: float
    # True when Ripser was skipped because the component exceeded
    # max_nodes. betti_0/betti_1 are both zero in that case and
    # should not be interpreted as real topology.
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class Broker:
    """A single entity scored for Burt brokerage."""

    node: str
    name: str
    entity_type: str
    # Burt's network constraint, ~(0, 1.125]. LOWER = more brokerage
    # (the node spans more non-redundant, otherwise-disconnected contacts).
    constraint: float
    # Effective size: number of non-redundant neighbours.
    effective_size: float
    # Distinct Louvain community indices its neighbours fall into.
    spans_communities: list[int]
    degree: int
    # Human-readable labels for spans_communities ("<dominant_type>:<hub>").
    spans_labels: list[str] = field(default_factory=list)


@dataclass
class BrokerageReport:
    """Burt structural-hole brokerage over the Louvain partition.

    A *structural hole* (Burt 1992) is a missing tie between two of a
    node's neighbours; the node bridging it holds a brokerage position.
    Distinct from a *bridge* (a global cut edge) and a *topological hole*
    (an H1 cycle). ``concentration`` is the top-1 share of cross-community
    brokerage mass: ~1.0 means a single fragile broker carries the graph's
    cross-domain reasoning; ~0.0 means brokerage is evenly distributed.
    """

    component_scope: str
    n_nodes_scored: int  # cross-community candidate nodes scored (the frontier)
    n_communities: int
    n_cross_community_brokers: int
    concentration: float  # top-1 share of cross-community brokerage mass [0,1]
    gini: float  # Gini of brokerage mass across cross-community brokers
    component_nodes: int = 0  # total nodes in the analysed component
    top_brokers: list[Broker] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""


def _gini(values: list[float]) -> float:
    """Gini coefficient of a non-negative distribution.

    0.0 = perfectly even, → 1.0 = all mass on one element. Returns 0.0 for
    empty or all-zero input.
    """
    xs = sorted(v for v in values if v is not None and v >= 0)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0:
        return 0.0
    cum = sum(i * x for i, x in enumerate(xs, start=1))
    return (2 * cum) / (n * total) - (n + 1) / n


class TopologyAnalyzer:
    """Analyze the structural properties of a graph snapshot."""

    def __init__(self, entities: list[Entity], edges: list[Edge]):
        self.entities = entities
        self.edges = edges
        self.G = self._build_networkx(entities, edges)

    @staticmethod
    def _build_networkx(entities: list[Entity], edges: list[Edge]) -> nx.MultiDiGraph:
        G = nx.MultiDiGraph()
        for e in entities:
            G.add_node(
                e.id,
                name=e.name,
                entity_type=e.entity_type,
                **{k: v for k, v in e.properties.items() if not k.startswith("_")},
                _table=e.properties.get("_table"),
            )
        for ed in edges:
            if ed.source_id in G and ed.target_id in G:
                # Drop keys that collide with add_edge's named args and
                # any reserved internal keys. `edge_type` is set
                # explicitly from ed.edge_type; anything else in
                # properties with the same name would shadow it.
                extra = {
                    k: v
                    for k, v in ed.properties.items()
                    if not k.startswith("_") and k != "edge_type"
                }
                G.add_edge(
                    ed.source_id,
                    ed.target_id,
                    edge_type=ed.edge_type,
                    **extra,
                )
        return G

    # --- Quick diagnostic ----------------------------------------------

    def structural_health(self) -> dict:
        """Fast diagnostic — no expensive algorithms.

        Reports connected components, largest component ratio, isolated
        nodes, entity type distribution, edge type distribution, and
        degree stats.
        """
        G = self.G
        undirected = G.to_undirected(as_view=False)

        # Weakly connected components via undirected view
        components = list(nx.connected_components(undirected))
        components.sort(key=len, reverse=True)
        n = G.number_of_nodes()
        largest = len(components[0]) if components else 0

        # Entity type distribution
        type_counts: Counter[str] = Counter()
        for _, data in G.nodes(data=True):
            type_counts[data.get("entity_type", "<none>")] += 1

        # Edge type distribution (the semantic discriminator for
        # consolidated edge tables that carry an `edge_type` column)
        edge_type_counts: Counter[str] = Counter()
        for _, _, data in G.edges(data=True):
            edge_type_counts[data.get("edge_type", "<none>")] += 1

        # Degree distribution
        degrees = [d for _, d in undirected.degree()]
        isolated = sum(1 for d in degrees if d == 0)
        avg_degree = (sum(degrees) / len(degrees)) if degrees else 0.0
        max_degree = max(degrees) if degrees else 0

        # Shannon entropy of edge type distribution (bits).
        # Low entropy -> monoculture. High entropy -> diverse vocabulary.
        total_edges = sum(edge_type_counts.values())
        if total_edges and len(edge_type_counts) > 1:
            edge_type_entropy = -sum(
                (c / total_edges) * math.log2(c / total_edges)
                for c in edge_type_counts.values()
            )
            # Clamp to exactly 0.0 to avoid -0.0 display artifacts
            edge_type_entropy = max(edge_type_entropy, 0.0)
        else:
            edge_type_entropy = 0.0

        return {
            "nodes": n,
            "edges": G.number_of_edges(),
            "components": len(components),
            "largest_component_size": largest,
            "largest_component_ratio": (largest / n) if n else 0.0,
            "isolated_nodes": isolated,
            "avg_degree": avg_degree,
            "max_degree": max_degree,
            "entity_type_distribution": dict(type_counts.most_common()),
            "edge_type_distribution": dict(edge_type_counts.most_common()),
            "edge_type_entropy_bits": edge_type_entropy,
        }

    # --- Community structure -------------------------------------------

    def community_structure(
        self,
        method: str = "louvain",
        *,
        resolution: float = 1.0,
        seed: int = 42,
    ) -> CommunityReport:
        """Louvain community detection on the undirected projection."""
        if method != "louvain":
            raise NotImplementedError(f"community method not supported: {method}")

        undirected = nx.Graph()
        for u, v, data in self.G.edges(data=True):
            if undirected.has_edge(u, v):
                undirected[u][v]["weight"] += 1.0
            else:
                undirected.add_edge(u, v, weight=1.0)
        undirected.add_nodes_from(self.G.nodes())

        if undirected.number_of_nodes() == 0:
            return CommunityReport(0, 0.0, [], 0, 0.0)

        from networkx.algorithms.community import (
            louvain_communities,
            modularity,
        )

        communities = louvain_communities(
            undirected, resolution=resolution, seed=seed
        )
        mod = modularity(undirected, communities)

        # Inter-community edge count
        node_to_comm: dict[str, int] = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                node_to_comm[node] = idx

        inter = 0
        for u, v in undirected.edges():
            if node_to_comm.get(u) != node_to_comm.get(v):
                inter += 1

        total = undirected.number_of_edges()
        ratio = (inter / total) if total else 0.0

        sizes = sorted((len(c) for c in communities), reverse=True)
        return CommunityReport(
            count=len(communities),
            modularity=mod,
            sizes=sizes,
            inter_community_edges=inter,
            inter_community_ratio=ratio,
        )

    # --- Brokerage / structural holes (Burt) ---------------------------

    def brokerage(
        self,
        *,
        top_k: int = 10,
        component: str = "largest",
        resolution: float = 1.0,
        seed: int = 42,
        max_nodes: int = 50000,
    ) -> BrokerageReport:
        """Burt structural-hole brokerage over the Louvain partition.

        Burt's *structural hole* is the absence of a tie between two of a
        node's neighbours; the node spanning it holds a brokerage
        position, quantified by low network *constraint* and high
        *effective size*. This is distinct from:

          - a *bridge* — a global cut edge (Cat 5 ``_structural_bridges``);
          - a *topological hole* — an H1 cycle (Cat 5 ``betti_numbers``).

        Reports which entities broker across Louvain communities and how
        concentrated that brokerage is. A single low-constraint broker
        spanning two communities is a single point of structural failure
        for cross-domain reasoning.

        Computed on the undirected, simple, self-loop-free projection,
        restricted by default to the largest connected component (the
        knowledge core). Pure read — never mutates the graph.
        """
        # Undirected simple projection: collapse parallel edges, drop self loops.
        H = nx.Graph()
        H.add_nodes_from(self.G.nodes())
        for u, v in self.G.edges():
            if u != v:
                H.add_edge(u, v)

        if component == "largest" and H.number_of_nodes():
            comps = sorted(nx.connected_components(H), key=len, reverse=True)
            if comps:
                H = H.subgraph(comps[0]).copy()

        n = H.number_of_nodes()
        if n == 0 or H.number_of_edges() == 0:
            return BrokerageReport(
                component_scope=component,
                n_nodes_scored=0,
                n_communities=0,
                n_cross_community_brokers=0,
                concentration=0.0,
                gini=0.0,
            )
        if n > max_nodes:
            return BrokerageReport(
                component_scope=component,
                n_nodes_scored=0,
                n_communities=0,
                n_cross_community_brokers=0,
                concentration=0.0,
                gini=0.0,
                component_nodes=n,
                skipped=True,
                skip_reason=(
                    f"component has {n:,} nodes > max_nodes={max_nodes:,}; "
                    "Louvain over the whole component is the bottleneck at this "
                    "scale. Raise max_nodes to force."
                ),
            )

        from networkx.algorithms.community import louvain_communities

        communities = louvain_communities(H, resolution=resolution, seed=seed)
        node_to_comm: dict[str, int] = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                node_to_comm[node] = idx

        # Per-community display labels: dominant entity_type + hub member,
        # so output names *what* a broker bridges instead of "comm 0+1".
        degree = dict(H.degree())
        comm_label: dict[int, str] = {}
        for idx, members in enumerate(communities):
            types: Counter[str] = Counter(
                self.G.nodes[m].get("entity_type", "<none>") for m in members
            )
            dom_type = types.most_common(1)[0][0]
            hub = max(members, key=lambda m: degree.get(m, 0))
            hub_name = self.G.nodes[hub].get("name", hub)
            comm_label[idx] = f"{dom_type}:{hub_name}"

        # Frontier-scoping (#5 — makes this tractable on large graphs): a node
        # can only broker if its neighbours span >= 2 communities. That set is
        # computable in O(E) by scanning neighbour communities, so we run the
        # costly nx.constraint (~O(n*d^2)) ONLY over this frontier, not all n
        # nodes. constraint/effective_size depend only on a node's ego network,
        # which is fully present in H, so restricting `nodes` is exact — same
        # values as the full computation, far less work.
        candidate_spans: dict[str, list[int]] = {}
        for node in H.nodes():
            spans = sorted({node_to_comm[w] for w in H.neighbors(node)})
            if len(spans) >= 2:
                candidate_spans[node] = spans
        candidates = list(candidate_spans)

        constraint = nx.constraint(H, nodes=candidates) if candidates else {}
        eff_size = nx.effective_size(H, nodes=candidates) if candidates else {}

        brokers: list[Broker] = []
        for node in candidates:
            c = constraint.get(node)
            if c is None or math.isnan(c):
                continue
            spans = candidate_spans[node]
            data = self.G.nodes[node]
            brokers.append(
                Broker(
                    node=node,
                    name=data.get("name", node),
                    entity_type=data.get("entity_type", "<none>"),
                    constraint=float(c),
                    effective_size=float(eff_size.get(node, 0.0)),
                    spans_communities=spans,
                    degree=H.degree(node),
                    spans_labels=[comm_label[i] for i in spans],
                )
            )

        # All candidates are cross-community by construction. Rank by
        # constraint (rim nodes included; the apex broker sorts to the top).
        cross = sorted(brokers, key=lambda b: (b.constraint, -b.effective_size))
        # Brokerage mass = 1/constraint (lower constraint = more brokerage).
        # NOT effective_size, which is degree-biased and can rank a
        # high-degree rim node above the actual low-constraint broker.
        masses = [1.0 / max(b.constraint, 1e-9) for b in cross]
        total_mass = sum(masses)
        concentration = (max(masses) / total_mass) if total_mass > 0 else 0.0

        return BrokerageReport(
            component_scope=component,
            n_nodes_scored=len(brokers),
            n_communities=len(communities),
            n_cross_community_brokers=len(cross),
            concentration=concentration,
            gini=_gini(masses),
            component_nodes=n,
            top_brokers=cross[:top_k],  # cross-community only; empty if none
        )

    # --- Filtered subgraph (Cat 4c monoculture detection) --------------

    def filtered_subgraph(
        self, edge_types: Iterable[str], *, include: bool = True
    ) -> "TopologyAnalyzer":
        """Return a new analyzer over a subgraph with only (or excluding)
        the specified edge types.

        Used by Cat 4c monoculture detection: compare component count
        of the typed-edge subgraph vs the RELATED-only subgraph.
        Large Betti-0 divergence = monoculture severity.
        """
        wanted = set(edge_types)
        keep = (lambda et: et in wanted) if include else (lambda et: et not in wanted)

        sub_edges = [e for e in self.edges if keep(e.edge_type)]
        # Keep all nodes so isolated-node counts make sense vs the full graph.
        return TopologyAnalyzer(self.entities, sub_edges)

    # --- Persistent homology (Cat 5 gap detection) ---------------------

    def betti_numbers(
        self,
        *,
        component: str = "largest",
        max_dim: int = 1,
        max_nodes: int = 2000,
        subsample: bool = False,
        seed: int = 42,
    ) -> BettiReport:
        """Run persistent homology on the graph.

        Strategy: take the specified connected component, compute the
        all-pairs shortest-path distance matrix, feed to Ripser with
        max_dim=1. Returns Betti-0 (components, always 1 for a single
        component), Betti-1 (loops / structural holes), and the
        persistence bars for each dimension.

        For typical knowledge cores (hundreds of nodes) this runs in
        under a second. For larger components, consider subsampling or
        using a sparse filtration.

        Args:
            component: 'largest' (default) or 'all'. 'all' means build
                the distance matrix on the full graph with disconnected
                pairs set to infinity — H_0 will equal total component
                count, but this is more expensive.
            max_dim: maximum homology dimension. Default 1 (H_0 + H_1).
        """
        import numpy as np
        from ripser import ripser  # local import — heavy dep

        undirected = self.G.to_undirected(as_view=False)
        if undirected.number_of_nodes() == 0:
            return BettiReport(0, 0, 0, [], [], 0.0)

        if component == "largest":
            comps = list(nx.connected_components(undirected))
            comps.sort(key=len, reverse=True)
            node_set = comps[0] if comps else set()
            sub = undirected.subgraph(node_set).copy()
        elif component == "all":
            sub = undirected
        else:
            raise ValueError(f"unknown component selector: {component!r}")

        n = sub.number_of_nodes()
        if n < 3:
            # H_1 is trivially 0 below 3 nodes
            return BettiReport(n, 1 if n else 0, 0, [], [], 0.0)

        # Ripser on dense, large components explodes. The filtered Vietoris-
        # Rips complex grows super-linearly with node count × density. Cap
        # the input size: either skip (safe default) or subsample randomly.
        if n > max_nodes:
            if not subsample:
                reason = (
                    f"component has {n} nodes > max_nodes={max_nodes}; "
                    f"Ripser on dense graphs this size can take hours. "
                    f"Re-run with --betti-subsample or raise --betti-max-nodes "
                    f"to force it."
                )
                log.warning(reason)
                return BettiReport(
                    component_size=n,
                    betti_0=0,
                    betti_1=0,
                    h0_bars=[],
                    h1_bars=[],
                    max_h1_persistence=0.0,
                    skipped=True,
                    skip_reason=reason,
                )
            import random

            rng = random.Random(seed)
            sampled = rng.sample(list(sub.nodes()), max_nodes)
            sub = sub.subgraph(sampled).copy()
            n = sub.number_of_nodes()
            log.warning(
                "subsampled largest component to %d nodes (seed=%d). "
                "Betti numbers are approximate.",
                n,
                seed,
            )

        nodes = list(sub.nodes())
        idx = {node: i for i, node in enumerate(nodes)}

        # Build shortest-path distance matrix (unweighted hop count).
        # Disconnected pairs within a component shouldn't happen; we
        # guard by setting unreachable entries to a large finite value
        # so Ripser treats them as "very late birth" rather than NaN.
        INF = float(n + 1)
        dmat = np.full((n, n), INF, dtype=np.float32)
        np.fill_diagonal(dmat, 0.0)
        # nx.all_pairs_shortest_path_length is a generator of (node, dict)
        for src, lengths in nx.all_pairs_shortest_path_length(sub):
            i = idx[src]
            for dst, d in lengths.items():
                dmat[i, idx[dst]] = float(d)

        log.info(
            "persistent homology on %d-node component (distance matrix %dx%d)",
            n,
            n,
            n,
        )
        result = ripser(dmat, distance_matrix=True, maxdim=max_dim)
        diagrams = result["dgms"]  # list per dimension

        def _bars(dgm) -> list[tuple[float, float, float]]:
            out: list[tuple[float, float, float]] = []
            for birth, death in dgm:
                b = float(birth)
                d = float(death) if not math.isinf(death) else float("inf")
                pers = (d - b) if not math.isinf(d) else float("inf")
                out.append((b, d, pers))
            return out

        h0 = _bars(diagrams[0]) if len(diagrams) > 0 else []
        h1 = _bars(diagrams[1]) if len(diagrams) > 1 else []

        # Betti_0 = count of H_0 classes that are still alive at the
        # end of the filtration (essential classes). For a distance
        # matrix with unreachable pairs at INF, any H_0 with death >= INF
        # is an essential class. For a single connected component this
        # should be exactly 1.
        betti_0 = sum(
            1
            for _, d, _ in h0
            if math.isinf(d) or d >= INF - 1e-6
        )
        # All finite-death H_1 bars are real loops.
        finite_h1 = [
            (b, d, p) for (b, d, p) in h1 if not math.isinf(d) and d < INF - 1e-6
        ]
        betti_1 = len(finite_h1)

        max_h1_persistence = max(
            (p for _, _, p in finite_h1), default=0.0
        )

        # Sort bars by persistence descending for the report
        finite_h1.sort(key=lambda t: t[2], reverse=True)
        h0.sort(key=lambda t: (0 if math.isinf(t[1]) else t[2]), reverse=True)

        return BettiReport(
            component_size=n,
            betti_0=betti_0,
            betti_1=betti_1,
            h0_bars=h0,
            h1_bars=finite_h1,
            max_h1_persistence=max_h1_persistence,
        )

    # --- Convenience ---------------------------------------------------

    def edge_type_components(self) -> dict[str, int]:
        """Component count per edge-type subgraph. Quick Cat 4c signal."""
        types_seen = sorted({e.edge_type for e in self.edges})
        out: dict[str, int] = {}
        for et in types_seen:
            sub = self.filtered_subgraph([et], include=True)
            u = sub.G.to_undirected()
            out[et] = nx.number_connected_components(u)
        return out
