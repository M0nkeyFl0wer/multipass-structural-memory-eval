"""Category 8: Ontology Coherence.

Tests whether a memory system's actual graph structure matches what
it claims to do in its README / schema / documentation.

Two modes:
  - **external**: SME analyzes the graph snapshot and compares to the
    declared ontology. Works on any system. This is the default.
  - **introspection**: does the system itself surface its own drift?
    Most systems score 0 here (no health-check API exists). Reported
    separately so "no introspection" isn't conflated with "bad graph."

Sub-tests:
  8a  Type coverage       — do claimed entity types exist in the graph?
  8b  Edge vocabulary     — do claimed edge types exist?
  8c  Schema-data align   — type distribution vs expected, entropy
  8d  Ontology drift      — declared vs effective vocabulary diff
  8e  Claim verification  — structural_claims.yaml pattern matching

Plus MemPalace-specific: hall population check (what % of drawers
have a non-empty hall field, vs the 5 declared standard halls).

The scoring module is adapter-agnostic. It consumes a graph snapshot,
structural_health dict, and optional cross-category results (cat7,
cat3, cat2b) used to verify "improves retrieval" / "contradiction
detection" / "canonicalization" claims via cross-references in the
claim library.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from sme.adapters.base import Edge, Entity

log = logging.getLogger(__name__)


# ── Data types ──────────────────────────────────────────────────────


@dataclass
class ImpliedOntology:
    """Hand-extracted or LLM-extracted claims about what a system does."""

    version: str
    source: str  # "declared" | "readme" | "inferred"
    entity_types: list[str] = field(default_factory=list)
    edge_types: list[str] = field(default_factory=list)
    hall_vocabulary: list[str] = field(default_factory=list)
    structural_claims: list[dict] = field(default_factory=list)
    vocabulary_claims: list[dict] = field(default_factory=list)
    retrieval_claims: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # full YAML for future fields

    @classmethod
    def load(cls, path: str | Path) -> "ImpliedOntology":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(
            version=data.get("version", "?"),
            source=data.get("source", "inferred"),
            entity_types=data.get("entity_types", []) or [],
            edge_types=data.get("edge_types", []) or [],
            hall_vocabulary=data.get("hall_vocabulary", []) or [],
            structural_claims=data.get("structural_claims", []) or [],
            vocabulary_claims=data.get("vocabulary_claims", []) or [],
            retrieval_claims=data.get("retrieval_claims", []) or [],
            raw=data,
        )


@dataclass
class ClaimResult:
    claim_id: str
    claim_text: str
    status: str  # "pass" | "fail" | "untestable" | "skipped"
    operational_definition: str
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class Cat8Report:
    """Full Category 8 scorecard."""

    # 8a
    type_coverage: float = 0.0
    types_declared: list[str] = field(default_factory=list)
    types_found: list[str] = field(default_factory=list)
    types_missing: list[str] = field(default_factory=list)
    types_undeclared: list[str] = field(default_factory=list)

    # 8b
    edge_vocabulary_coverage: float = 0.0
    edges_declared: list[str] = field(default_factory=list)
    edges_found: list[str] = field(default_factory=list)
    edges_missing: list[str] = field(default_factory=list)
    edges_undeclared: list[str] = field(default_factory=list)

    # 8c
    type_distribution: dict[str, int] = field(default_factory=dict)
    edge_type_distribution: dict[str, int] = field(default_factory=dict)
    edge_type_entropy_bits: float = 0.0
    entity_type_concentration: Optional[dict] = None  # top type + pct
    concentration_warning: Optional[str] = None

    # 8d
    drift_score: float = 0.0  # fraction of declared names not in use
    declared_union: list[str] = field(default_factory=list)
    effective_union: list[str] = field(default_factory=list)

    # 8d MemPalace-specific: hall usage
    hall_usage: Optional[dict] = None

    # 8e
    claims: list[ClaimResult] = field(default_factory=list)
    claims_pass_rate: float = 0.0
    claims_tested: int = 0
    claims_passed: int = 0
    claims_untestable: int = 0

    # Introspection (usually 0 — most systems don't self-report)
    introspection_available: list[str] = field(default_factory=list)
    introspection_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "8a_type_coverage": {
                "score": self.type_coverage,
                "declared": self.types_declared,
                "found": self.types_found,
                "missing": self.types_missing,
                "undeclared": self.types_undeclared,
            },
            "8b_edge_vocabulary": {
                "score": self.edge_vocabulary_coverage,
                "declared": self.edges_declared,
                "found": self.edges_found,
                "missing": self.edges_missing,
                "undeclared": self.edges_undeclared,
            },
            "8c_schema_alignment": {
                "entity_type_distribution": self.type_distribution,
                "edge_type_distribution": self.edge_type_distribution,
                "edge_type_entropy_bits": self.edge_type_entropy_bits,
                "entity_type_concentration": self.entity_type_concentration,
                "warning": self.concentration_warning,
            },
            "8d_drift": {
                "score": self.drift_score,
                "declared": self.declared_union,
                "effective": self.effective_union,
                "hall_usage": self.hall_usage,
            },
            "8e_claims": {
                "pass_rate": self.claims_pass_rate,
                "tested": self.claims_tested,
                "passed": self.claims_passed,
                "untestable": self.claims_untestable,
                "detail": [
                    {
                        "id": c.claim_id,
                        "text": c.claim_text,
                        "status": c.status,
                        "definition": c.operational_definition,
                        "metrics": c.metrics,
                        "notes": c.notes,
                    }
                    for c in self.claims
                ],
            },
            "introspection": {
                "available": self.introspection_available,
                "score": self.introspection_score,
            },
        }


# ── Claim library loading ──────────────────────────────────────────


def load_claim_library(
    path: str | Path = "sme/claims/structural_claims.yaml",
) -> dict:
    """Load the operationalized claim library. Returns the raw dict."""
    p = Path(path)
    if not p.is_absolute():
        # Resolve relative to the package repo root
        here = Path(__file__).resolve().parent.parent.parent
        p = here / path
    with open(p) as f:
        return yaml.safe_load(f)


def match_claim_pattern(claim_text: str, library: dict) -> Optional[dict]:
    """Find the first library entry whose regex pattern matches the claim."""
    for entry in library.get("claims", []):
        pattern = entry.get("pattern", "")
        if pattern and re.search(pattern, claim_text, re.IGNORECASE):
            return entry
    return None


def is_untestable(claim_text: str, library: dict) -> bool:
    """Check if the claim matches the denylist of untestable patterns."""
    for pattern in library.get("untestable_patterns", []):
        if re.search(pattern, claim_text, re.IGNORECASE):
            return True
    return False


# ── Metric computation ─────────────────────────────────────────────


def _compute_type_homogeneity(
    entities: list[Entity], edges: list[Edge]
) -> float:
    """For each Louvain community, find the dominant entity_type and
    compute its share within the community. Average weighted by
    community size. Returns a value in [0, 1] — higher is more
    homogeneous."""
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except ImportError:
        return 0.0

    if not entities:
        return 0.0

    G = nx.Graph()
    for e in entities:
        G.add_node(e.id, entity_type=e.entity_type)
    for ed in edges:
        if ed.source_id in G and ed.target_id in G:
            G.add_edge(ed.source_id, ed.target_id)

    if G.number_of_edges() == 0:
        return 0.0

    try:
        communities = louvain_communities(G, seed=42)
    except Exception:
        return 0.0

    total = 0
    weighted_sum = 0.0
    for comm in communities:
        if not comm:
            continue
        size = len(comm)
        type_counts: dict[str, int] = {}
        for node in comm:
            t = G.nodes[node].get("entity_type", "?")
            type_counts[t] = type_counts.get(t, 0) + 1
        dominant = max(type_counts.values())
        weighted_sum += dominant
        total += size

    return weighted_sum / total if total else 0.0


def _compute_inter_community_edge_density(
    entities: list[Entity], edges: list[Edge]
) -> tuple[float, int]:
    """Fraction of edges crossing Louvain community boundaries.
    Returns (density, inter_count)."""
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except ImportError:
        return 0.0, 0

    if not entities or not edges:
        return 0.0, 0

    G = nx.Graph()
    for e in entities:
        G.add_node(e.id)
    for ed in edges:
        if ed.source_id in G and ed.target_id in G:
            G.add_edge(ed.source_id, ed.target_id)

    if G.number_of_edges() == 0:
        return 0.0, 0

    try:
        communities = louvain_communities(G, seed=42)
    except Exception:
        return 0.0, 0

    node_to_comm: dict[str, int] = {}
    for i, comm in enumerate(communities):
        for n in comm:
            node_to_comm[n] = i

    inter = 0
    for u, v in G.edges():
        if node_to_comm.get(u) != node_to_comm.get(v):
            inter += 1

    return inter / G.number_of_edges(), inter


def _compute_modularity(
    entities: list[Entity], edges: list[Edge]
) -> float:
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities, modularity
    except ImportError:
        return 0.0

    G = nx.Graph()
    for e in entities:
        G.add_node(e.id)
    for ed in edges:
        if ed.source_id in G and ed.target_id in G:
            G.add_edge(ed.source_id, ed.target_id)

    if G.number_of_edges() == 0:
        return 0.0

    try:
        communities = louvain_communities(G, seed=42)
        return modularity(G, communities)
    except Exception:
        return 0.0


# ── Main scoring function ──────────────────────────────────────────


def score_cat8(
    implied: ImpliedOntology,
    entities: list[Entity],
    edges: list[Edge],
    structural_health: dict,
    *,
    cat7_results: Optional[dict] = None,
    cat3_results: Optional[dict] = None,
    cat2b_results: Optional[dict] = None,
    claim_library: Optional[dict] = None,
) -> Cat8Report:
    """Produce a Cat 8 scorecard.

    cat7_results should be a dict like the one emitted by
    ``sme-eval retrieve --json``. When provided, claims matching the
    "improves retrieval" pattern are scored against it. Otherwise
    those claims are marked "untestable (no Cat 7 data)".
    """
    report = Cat8Report()

    if claim_library is None:
        claim_library = load_claim_library()

    # --- 8a: type coverage --------------------------------------

    # For entity types, we match the declared types against the
    # *primary* entity_type string of each node. For adapters that
    # prefix types (e.g. "drawer:hall_facts" or "room:untyped"), we
    # also check the prefix so "drawer" declared matches "drawer:X".
    def _types_match(declared: str, found: str) -> bool:
        if declared == found:
            return True
        if found.startswith(declared + ":"):
            return True
        return False

    entity_types_in_graph: set[str] = {e.entity_type for e in entities}
    type_counts: dict[str, int] = {}
    for e in entities:
        type_counts[e.entity_type] = type_counts.get(e.entity_type, 0) + 1
    report.type_distribution = dict(
        sorted(type_counts.items(), key=lambda kv: -kv[1])
    )

    declared_types = set(implied.entity_types)
    found_types: list[str] = []
    missing_types: list[str] = []
    for dt in sorted(declared_types):
        matched = any(_types_match(dt, g) for g in entity_types_in_graph)
        (found_types if matched else missing_types).append(dt)

    # Undeclared types: entity_type values in the graph that don't
    # fall under any declared prefix
    undeclared: list[str] = []
    for g in sorted(entity_types_in_graph):
        prefix = g.split(":", 1)[0]
        if prefix not in declared_types and g not in declared_types:
            undeclared.append(g)

    report.types_declared = sorted(declared_types)
    report.types_found = found_types
    report.types_missing = missing_types
    report.types_undeclared = undeclared
    report.type_coverage = (
        len(found_types) / len(declared_types) if declared_types else 1.0
    )

    # --- 8b: edge vocabulary -----------------------------------

    edge_types_in_graph: set[str] = {e.edge_type for e in edges}
    edge_counts: dict[str, int] = {}
    for ed in edges:
        edge_counts[ed.edge_type] = edge_counts.get(ed.edge_type, 0) + 1
    report.edge_type_distribution = dict(
        sorted(edge_counts.items(), key=lambda kv: -kv[1])
    )

    declared_edges = set(implied.edge_types)
    found_edges: list[str] = []
    missing_edges: list[str] = []
    for de in sorted(declared_edges):
        # Edge types typically match exactly. Also allow a case-
        # insensitive fallback for schemas that vary on case.
        if de in edge_types_in_graph:
            found_edges.append(de)
        elif any(de.lower() == eg.lower() for eg in edge_types_in_graph):
            found_edges.append(de)
        else:
            missing_edges.append(de)

    undeclared_edges = sorted(
        e for e in edge_types_in_graph if e not in declared_edges
    )

    report.edges_declared = sorted(declared_edges)
    report.edges_found = found_edges
    report.edges_missing = missing_edges
    report.edges_undeclared = undeclared_edges
    report.edge_vocabulary_coverage = (
        len(found_edges) / len(declared_edges) if declared_edges else 1.0
    )

    # --- 8c: schema-data alignment -----------------------------

    report.edge_type_entropy_bits = structural_health.get(
        "edge_type_entropy_bits", 0.0
    )

    total_entities = len(entities)
    if total_entities and type_counts:
        top_type, top_count = max(type_counts.items(), key=lambda kv: kv[1])
        pct = top_count / total_entities
        report.entity_type_concentration = {
            "top_type": top_type,
            "count": top_count,
            "total": total_entities,
            "fraction": pct,
        }
        if pct > 0.8:
            report.concentration_warning = (
                f"{pct:.1%} of entities are type {top_type!r} — "
                "possible under-classification or over-specified ontology"
            )

    # --- 8d: drift ---------------------------------------------

    declared_union = sorted(declared_types | declared_edges)
    effective_union = sorted(entity_types_in_graph | edge_types_in_graph)

    # Drift = fraction of declared names not used. We count a declared
    # type as "used" if it matches exactly or via prefix (for entity
    # types) or exactly (for edge types).
    declared_count = len(declared_types) + len(declared_edges)
    used_count = len(found_types) + len(found_edges)
    report.drift_score = (
        (declared_count - used_count) / declared_count
        if declared_count
        else 0.0
    )
    report.declared_union = declared_union
    report.effective_union = effective_union

    # --- 8d MemPalace-specific: hall usage ---------------------

    if implied.hall_vocabulary:
        report.hall_usage = _score_hall_usage(entities, implied.hall_vocabulary)

    # --- 8e: claim verification --------------------------------

    for claim in implied.structural_claims:
        report.claims.append(
            _score_claim(
                claim,
                entities,
                edges,
                structural_health,
                claim_library,
                cat7_results=cat7_results,
                cat3_results=cat3_results,
                cat2b_results=cat2b_results,
            )
        )

    # Include retrieval claims too — they map to Cat 7 deferral
    for rc in implied.retrieval_claims:
        report.claims.append(
            _score_claim(
                rc,
                entities,
                edges,
                structural_health,
                claim_library,
                cat7_results=cat7_results,
                cat3_results=cat3_results,
                cat2b_results=cat2b_results,
            )
        )

    # Include vocabulary claims as informational rows (most are
    # "untestable via structural metrics" — they're reported but
    # don't count in the pass rate).
    for vc in implied.vocabulary_claims:
        res = ClaimResult(
            claim_id=vc.get("id", "?"),
            claim_text=vc.get("text", ""),
            status="untestable",
            operational_definition=(
                "vocabulary existence claim — no structural operationalization"
            ),
        )
        # MemPalace hall vocab specifically gets a concrete answer
        if vc.get("id") == "five_standard_halls" and report.hall_usage:
            hu = report.hall_usage
            fraction_populated = hu["fraction_populated"]
            if fraction_populated >= 0.5:
                res.status = "pass"
            elif fraction_populated > 0:
                res.status = "fail"
            else:
                res.status = "fail"
            res.operational_definition = (
                "fraction of drawers with non-empty hall >= 0.5"
            )
            res.metrics = hu
            res.notes = (
                f"{hu['populated_count']}/{hu['total_drawers']} drawers "
                f"have hall set ({fraction_populated:.1%})"
            )
        report.claims.append(res)

    tested = [c for c in report.claims if c.status in ("pass", "fail")]
    passed = [c for c in tested if c.status == "pass"]
    untestable = [c for c in report.claims if c.status == "untestable"]

    report.claims_tested = len(tested)
    report.claims_passed = len(passed)
    report.claims_untestable = len(untestable)
    report.claims_pass_rate = (
        len(passed) / len(tested) if tested else 0.0
    )

    # --- Introspection --------------------------------------

    # Most systems don't self-report drift. We check for the presence
    # of health-check attributes on the adapter — this is wired at
    # the CLI level. The scoring module reports 0 unless evidence
    # is passed in.
    report.introspection_available = []
    report.introspection_score = 0.0

    return report


# ── Hall usage scorer (MemPalace-specific detail) ────────────────


def _score_hall_usage(
    entities: list[Entity], declared_halls: list[str]
) -> dict:
    """Count drawers and their hall values.

    Drawers are identified by entity_type starting with 'drawer:'
    (matching the MemPalaceAdapter convention). The hall value comes
    from the properties dict or the entity_type suffix after the colon.
    Returns a detailed usage dict with counts, distribution, and the
    fraction of drawers that have a populated, in-vocabulary hall.
    """
    drawers = [e for e in entities if e.entity_type.startswith("drawer")]
    total = len(drawers)
    if not total:
        return {
            "total_drawers": 0,
            "populated_count": 0,
            "fraction_populated": 0.0,
            "declared_vocabulary": declared_halls,
            "distribution": {},
            "in_vocabulary_fraction": 0.0,
        }

    hall_counts: dict[str, int] = {}
    populated = 0
    in_vocab = 0
    for d in drawers:
        hall = d.properties.get("hall", "") or ""
        if not hall or hall == "untyped":
            # Fallback: try extracting from entity_type suffix
            parts = d.entity_type.split(":", 1)
            if len(parts) == 2:
                hall_from_type = parts[1]
                if hall_from_type and hall_from_type != "untyped":
                    hall = hall_from_type
        if hall and hall != "untyped":
            populated += 1
            hall_counts[hall] = hall_counts.get(hall, 0) + 1
            if hall in declared_halls or hall.replace("hall_", "") in declared_halls:
                in_vocab += 1

    return {
        "total_drawers": total,
        "populated_count": populated,
        "fraction_populated": populated / total,
        "declared_vocabulary": declared_halls,
        "distribution": dict(
            sorted(hall_counts.items(), key=lambda kv: -kv[1])
        ),
        "in_vocabulary_count": in_vocab,
        "in_vocabulary_fraction": in_vocab / total if total else 0.0,
    }


# ── Individual claim scoring ─────────────────────────────────────


def _score_claim(
    claim: dict,
    entities: list[Entity],
    edges: list[Edge],
    structural_health: dict,
    library: dict,
    *,
    cat7_results: Optional[dict] = None,
    cat3_results: Optional[dict] = None,
    cat2b_results: Optional[dict] = None,
) -> ClaimResult:
    claim_id = claim.get("id", "?")
    claim_text = claim.get("text", "")

    # Denylist: untestable UX/scalability/security claims
    if is_untestable(claim_text, library):
        return ClaimResult(
            claim_id=claim_id,
            claim_text=claim_text,
            status="untestable",
            operational_definition="matches untestable_patterns denylist",
            notes="UX, scalability, security, or vague performance claim",
        )

    # Inline operational_override (claim carries its own definition)
    override = claim.get("operational_override")
    if override:
        return _score_override(
            claim_id,
            claim_text,
            override,
            structural_health,
            cat7_results=cat7_results,
            cat3_results=cat3_results,
            cat2b_results=cat2b_results,
        )

    # Match against the claim library
    entry = match_claim_pattern(claim_text, library)
    if not entry:
        return ClaimResult(
            claim_id=claim_id,
            claim_text=claim_text,
            status="untestable",
            operational_definition="no library pattern matched",
        )

    op_name = entry.get("name", entry.get("pattern", "?"))
    op_def = entry.get("method", "").strip() or op_name
    thr = entry.get("threshold", {}) or {}

    # --- Dispatch by metric key -----------------------------

    metric = entry.get("metric", "")
    metrics: dict[str, Any] = {}
    status = "fail"
    notes = ""

    if "modularity" in metric.lower() and "degree" in metric.lower():
        # Hierarchical structure: modularity > 0.5 AND degree power-law
        mod = _compute_modularity(entities, edges)
        metrics["modularity"] = mod
        mod_min = thr.get("modularity_min", 0.5)
        # Power-law fitting requires the `powerlaw` package. If not
        # available, we skip the power-law requirement and accept
        # modularity alone as a weaker signal.
        try:
            import powerlaw  # noqa: F401

            _powerlaw_available = True
        except ImportError:
            _powerlaw_available = False
            metrics["powerlaw_note"] = (
                "powerlaw package not installed; modularity checked alone"
            )
        if _powerlaw_available:
            import networkx as nx
            import powerlaw

            G = nx.Graph()
            for e in entities:
                G.add_node(e.id)
            for ed in edges:
                if ed.source_id in G and ed.target_id in G:
                    G.add_edge(ed.source_id, ed.target_id)
            degrees = [d for _, d in G.degree() if d > 0]
            if len(degrees) >= 10:
                try:
                    fit = powerlaw.Fit(degrees, verbose=False)
                    p = fit.distribution_compare(
                        "power_law", "exponential", normalized_ratio=True
                    )[1]
                    metrics["powerlaw_p"] = p
                    passed = mod > mod_min and p < thr.get(
                        "degree_ks_test_p_max", 0.05
                    )
                    status = "pass" if passed else "fail"
                except Exception as e:
                    status = "pass" if mod > mod_min else "fail"
                    metrics["powerlaw_error"] = str(e)
            else:
                status = "pass" if mod > mod_min else "fail"
                metrics["powerlaw_note"] = "too few nodes for power-law fit"
        else:
            status = "pass" if mod > mod_min else "fail"
        notes = f"modularity={mod:.3f} (threshold {mod_min})"

    elif "inter-community" in metric.lower() or "inter_community" in metric.lower():
        density, inter = _compute_inter_community_edge_density(entities, edges)
        metrics["inter_community_edges"] = inter
        metrics["inter_community_density"] = density
        thresh = thr.get("inter_community_density_min", 0.0)
        status = "pass" if density > thresh else "fail"
        notes = f"{inter} inter-community edges ({density:.1%})"

    elif "type homogeneity" in metric.lower() or "homogeneity" in metric.lower():
        homog = _compute_type_homogeneity(entities, edges)
        metrics["type_homogeneity"] = homog
        thresh = thr.get("type_homogeneity_min", 0.9)
        status = "pass" if homog >= thresh else "fail"
        notes = f"weighted homogeneity {homog:.1%} (threshold {thresh:.0%})"

    elif "cat 7" in metric.lower() or "cat7" in metric.lower() or "pairwise win" in metric.lower():
        # Deferred to Cat 7 results. We don't have pairwise judge
        # data from the retrieval benchmark yet, so we use recall
        # delta as a proxy:
        #   graph condition recall vs flat condition recall
        if cat7_results is None:
            return ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                status="skipped",
                operational_definition=op_def,
                notes="no Cat 7 data available — pass --cat7-results",
            )
        graph_recall = cat7_results.get("graph_mean_recall")
        flat_recall = cat7_results.get("flat_mean_recall")
        if graph_recall is None or flat_recall is None:
            return ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                status="skipped",
                operational_definition=op_def,
                notes="Cat 7 data missing graph_mean_recall or flat_mean_recall",
            )
        metrics["graph_mean_recall"] = graph_recall
        metrics["flat_mean_recall"] = flat_recall
        metrics["delta_recall"] = graph_recall - flat_recall
        # "Improves" means clearly better. We use >5pp as a real
        # improvement threshold (the spec's 55% pairwise win rate
        # roughly corresponds to a meaningful recall lift).
        status = "pass" if (graph_recall - flat_recall) > 0.05 else "fail"
        notes = (
            f"graph recall {graph_recall:.1%} vs flat {flat_recall:.1%} "
            f"(delta {(graph_recall - flat_recall)*100:+.1f}pp)"
        )

    elif "cat 3" in metric.lower() or "contradictionpair" in metric.lower():
        if cat3_results is None:
            return ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                status="skipped",
                operational_definition=op_def,
                notes="no Cat 3 data available",
            )
        pairs = cat3_results.get("contradiction_pairs", 0)
        metrics["contradiction_pairs"] = pairs
        status = "pass" if pairs > 0 else "fail"

    elif "cat 2b" in metric.lower() or "canonicalization" in metric.lower():
        if cat2b_results is None:
            return ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                status="skipped",
                operational_definition=op_def,
                notes="no Cat 2b data available",
            )
        recall = cat2b_results.get("canonicalization_recall", 0.0)
        metrics["canonicalization_recall"] = recall
        status = "pass" if recall > 0.5 else "fail"

    elif "temporal" in metric.lower() or "_created_at" in metric.lower():
        # Fraction of edges with _created_at
        total = len(edges)
        with_temporal = sum(
            1 for ed in edges if ed.properties.get("_created_at")
        )
        metrics["fraction_edges_with_created_at"] = (
            with_temporal / total if total else 0.0
        )
        thresh = thr.get("temporal_coverage_min", 0.5)
        status = (
            "pass"
            if total and (with_temporal / total) > thresh
            else "fail"
        )
        notes = f"{with_temporal}/{total} edges with _created_at"

    elif "provenance" in metric.lower() or "_created_by" in metric.lower():
        total = len(edges)
        with_prov = sum(
            1 for ed in edges if ed.properties.get("_created_by")
        )
        metrics["fraction_edges_with_created_by"] = (
            with_prov / total if total else 0.0
        )
        thresh = thr.get("provenance_coverage_min", 0.5)
        status = (
            "pass"
            if total and (with_prov / total) > thresh
            else "fail"
        )
        notes = f"{with_prov}/{total} edges with _created_by"

    else:
        status = "untestable"
        notes = f"unrecognized metric key: {metric}"

    return ClaimResult(
        claim_id=claim_id,
        claim_text=claim_text,
        status=status,
        operational_definition=op_def.strip(),
        metrics=metrics,
        notes=notes,
    )


def _score_override(
    claim_id: str,
    claim_text: str,
    override: dict,
    structural_health: dict,
    *,
    cat7_results: Optional[dict],
    cat3_results: Optional[dict],
    cat2b_results: Optional[dict],
) -> ClaimResult:
    """Handle claims that carry an inline operational_override."""
    metric = override.get("metric", "")
    pass_condition = override.get("pass_condition", "")
    description = override.get("description", "").strip() or pass_condition

    if metric == "cat7_delta_recall":
        if cat7_results is None:
            return ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                status="skipped",
                operational_definition=description,
                notes="no Cat 7 data passed",
            )
        graph_recall = cat7_results.get("graph_mean_recall")
        flat_recall = cat7_results.get("flat_mean_recall")
        if graph_recall is None or flat_recall is None:
            return ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                status="skipped",
                operational_definition=description,
                notes="Cat 7 results missing recall fields",
            )
        delta = graph_recall - flat_recall
        # "not a moat" passes if delta is near zero (within 10pp)
        status = "pass" if abs(delta) < 0.1 else "fail"
        return ClaimResult(
            claim_id=claim_id,
            claim_text=claim_text,
            status=status,
            operational_definition=description,
            metrics={
                "graph_mean_recall": graph_recall,
                "flat_mean_recall": flat_recall,
                "delta_recall": delta,
            },
            notes=(
                f"delta={delta*100:+.1f}pp "
                f"({'within' if abs(delta) < 0.1 else 'outside'} ±10pp band)"
            ),
        )

    return ClaimResult(
        claim_id=claim_id,
        claim_text=claim_text,
        status="untestable",
        operational_definition=description,
        notes=f"no override handler for metric: {metric}",
    )
