"""Category 4: Ingestion Integrity — The Threshold.

Measures whether the extraction pipeline is producing a clean graph,
or double-inserting the same entity / letting edge vocabulary sprawl /
dropping required fields. Adapter-agnostic — runs on any graph
snapshot; generalizes the DUP monitor that currently lives
hardcoded in the vault-rag integrity_monitor script.

Sub-tests implemented here:

  4a  Canonical-collision dedup (generalizes vault-rag's DUP)
      — distinct entity IDs whose names canonicalize to the same key
        within the same entity_type. Optionally scored against a
        gold-standard alias clustering via B-Cubed P/R/F1 (see
        `score_alias_resolution_against_gold`).

  4b  Required-field coverage
      — fraction of entities with the core fields (name, entity_type)
        populated. An empty name usually means the extractor fired on
        something it couldn't resolve to a label.

  4c  Edge-type monoculture
      — normalized entropy over the edge-type distribution, plus
        dominant-type fraction and per-type component count (via the
        existing TopologyAnalyzer.edge_type_components signal).

Sub-tests 4a/4b/4d from spec v8 (evidence duplication, evidence
misattribution, runaway extraction pattern) need vault-rag-specific
enrichment metadata (evidence strings, confidence scores, extraction
pattern IDs). Those stay in the content-integrity monitor that ships
with vault-rag, not here.
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from sme.adapters.base import Edge, Entity
from sme.topology.analyzer import TopologyAnalyzer

log = logging.getLogger(__name__)


# --- Canonicalization -------------------------------------------------


def default_canonical_key(name: str, entity_type: str) -> str:
    """Lowercase + whitespace-collapse, scoped by entity_type.

    Matches the vault-rag DUP monitor's canonicalization for the common
    cases (case variants, whitespace variants). Articles/punctuation
    stripping is deliberately *not* included here — that's a more
    aggressive canonicalization that some pipelines want and others
    don't. Adapters that canonicalize more aggressively can pass a
    custom function via ``canonicalize=``.
    """
    if name is None:
        return ""
    norm = " ".join(name.split()).lower()
    return f"{entity_type or ''}::{norm}" if norm else ""


# --- Bands for the Reading section ------------------------------------

_COLLISION_HEALTHY = 0.01   # < 1% of entities collide
_COLLISION_WARN = 0.05      # 1-5% warning
# > 5% concerning

_COVERAGE_HEALTHY = 0.995   # > 99.5% have required fields
_COVERAGE_WARN = 0.95       # 95-99.5% warning

_NORM_ENTROPY_HEALTHY = 0.80
_NORM_ENTROPY_WARN = 0.50


def _band(value: float, healthy: float, warn: float, *, lower_is_better: bool) -> str:
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


# --- Data shapes ------------------------------------------------------


@dataclass
class CollisionGroup:
    """A set of distinct entity IDs that canonicalize to the same key."""

    canonical_key: str
    ids: list[str]
    names: list[str]
    entity_type: str


@dataclass
class IngestionIntegrityReport:
    # Headline counts
    entities: int
    edges: int

    # 4a Canonical-collision dedup
    unique_canonical_keys: int
    canonical_collisions: int  # number of EXTRA duplicate IDs
    collision_groups: list[CollisionGroup] = field(default_factory=list)

    # 4b Required-field coverage
    required_field_gaps: int = 0
    required_field_coverage: float = 1.0  # fraction with name + entity_type
    gap_examples: list[str] = field(default_factory=list)  # entity IDs

    # 4c Edge-type monoculture
    edge_type_counts: dict[str, int] = field(default_factory=dict)
    edge_type_entropy_bits: float = 0.0
    edge_type_entropy_normalized: float = 0.0  # H / log2(n_types), [0,1]
    dominant_edge_type: Optional[str] = None
    dominant_edge_type_fraction: float = 0.0
    per_edge_type_components: dict[str, int] = field(default_factory=dict)


# --- Scorer -----------------------------------------------------------


def score_ingestion_integrity(
    entities: list[Entity],
    edges: list[Edge],
    *,
    canonicalize: Callable[[str, str], str] = default_canonical_key,
    collision_example_limit: int = 10,
    gap_example_limit: int = 10,
) -> IngestionIntegrityReport:
    """Produce a Cat 4 diagnostic reading for a graph snapshot.

    Args:
        entities, edges: the graph snapshot.
        canonicalize: name+type → canonical key. Default is
            lowercase + whitespace-collapse scoped by type. Pass an
            adapter-specific function if your pipeline strips
            articles, punctuation, or does richer normalization.
        collision_example_limit, gap_example_limit: cap the examples
            retained in the report for readability.
    """
    n = len(entities)

    # --- 4a canonical-collision dedup --------------------------------

    key_to_ids: dict[str, list[str]] = defaultdict(list)
    key_to_names: dict[str, list[str]] = defaultdict(list)
    key_to_type: dict[str, str] = {}
    for ent in entities:
        key = canonicalize(ent.name, ent.entity_type)
        if not key:
            continue  # entity is a required-field gap (handled below)
        key_to_ids[key].append(ent.id)
        key_to_names[key].append(ent.name)
        key_to_type[key] = ent.entity_type

    collision_groups: list[CollisionGroup] = []
    collisions = 0
    for key, ids in key_to_ids.items():
        if len(ids) > 1:
            collisions += len(ids) - 1
            collision_groups.append(
                CollisionGroup(
                    canonical_key=key,
                    ids=ids,
                    names=key_to_names[key],
                    entity_type=key_to_type[key],
                )
            )
    collision_groups.sort(key=lambda g: len(g.ids), reverse=True)
    collision_groups = collision_groups[:collision_example_limit]

    # --- 4b required-field coverage ----------------------------------

    gap_examples: list[str] = []
    gaps = 0
    for ent in entities:
        if not ent.name or not ent.entity_type:
            gaps += 1
            if len(gap_examples) < gap_example_limit:
                gap_examples.append(ent.id)
    coverage = ((n - gaps) / n) if n else 1.0

    # --- 4c edge-type monoculture ------------------------------------

    type_counts: Counter[str] = Counter(e.edge_type for e in edges if e.edge_type)
    total = sum(type_counts.values())

    if total and len(type_counts) > 1:
        raw = -sum(
            (c / total) * math.log2(c / total) for c in type_counts.values()
        )
        raw = max(raw, 0.0)
        normalized = raw / math.log2(len(type_counts))
    else:
        raw = 0.0
        normalized = 0.0

    dominant_type: Optional[str] = None
    dominant_fraction = 0.0
    if total:
        dominant_type, dom_c = type_counts.most_common(1)[0]
        dominant_fraction = dom_c / total

    # Per-type component count via the existing TopologyAnalyzer signal.
    analyzer = TopologyAnalyzer(entities, edges)
    per_type_components = analyzer.edge_type_components()

    return IngestionIntegrityReport(
        entities=n,
        edges=len(edges),
        unique_canonical_keys=len(key_to_ids),
        canonical_collisions=collisions,
        collision_groups=collision_groups,
        required_field_gaps=gaps,
        required_field_coverage=coverage,
        gap_examples=gap_examples,
        edge_type_counts=dict(type_counts.most_common()),
        edge_type_entropy_bits=raw,
        edge_type_entropy_normalized=normalized,
        dominant_edge_type=dominant_type,
        dominant_edge_type_fraction=dominant_fraction,
        per_edge_type_components=per_type_components,
    )


# --- Human-readable rendering -----------------------------------------


def format_report(report: IngestionIntegrityReport) -> str:
    lines = [
        "Cat 4 — The Threshold",
        "═════════════════════",
        "",
        "Measurements",
        "─" * 60,
        f"  Entities:                  {report.entities:,}",
        f"  Edges:                     {report.edges:,}",
        "",
        f"  Unique canonical keys:     {report.unique_canonical_keys:,}",
        f"  Canonical collisions:      {report.canonical_collisions:,}",
    ]
    for group in report.collision_groups[:5]:
        names_preview = ", ".join(f'"{name}"' for name in group.names[:4])
        if len(group.names) > 4:
            names_preview += f", +{len(group.names) - 4} more"
        lines.append(
            f"    [{group.entity_type}] {names_preview} → "
            f"{len(group.ids)} distinct IDs"
        )
    if len(report.collision_groups) > 5:
        lines.append(
            f"    ... +{len(report.collision_groups) - 5} more collision groups"
        )

    lines.append("")
    lines.append(
        f"  Required-field coverage:   {report.required_field_coverage:.2%}"
        f"  ({report.entities - report.required_field_gaps:,} / {report.entities:,})"
    )
    if report.gap_examples:
        sample = ", ".join(report.gap_examples[:5])
        if len(report.gap_examples) > 5:
            sample += f", +{len(report.gap_examples) - 5} more"
        lines.append(f"    gap entity IDs: {sample}")

    lines.append("")
    lines.append(f"  Edge types ({len(report.edge_type_counts)}):")
    total_edges = sum(report.edge_type_counts.values()) or 1
    for etype, count in list(report.edge_type_counts.items())[:10]:
        pct = 100 * count / total_edges
        lines.append(f"    {etype:30s} {count:>8,}  ({pct:5.1f}%)")
    if len(report.edge_type_counts) > 10:
        lines.append(
            f"    ... +{len(report.edge_type_counts) - 10} more edge types"
        )
    lines.append(
        f"  Edge-type entropy:         {report.edge_type_entropy_bits:.2f} bits"
        f"  (normalized {report.edge_type_entropy_normalized:.2f})"
    )
    if report.dominant_edge_type:
        lines.append(
            f"  Dominant edge type:        '{report.dominant_edge_type}' "
            f"at {report.dominant_edge_type_fraction:.1%}"
        )

    if report.per_edge_type_components:
        lines.append("")
        lines.append("  Per-edge-type component count (4c monoculture signal):")
        for etype, ncomp in sorted(
            report.per_edge_type_components.items(), key=lambda kv: -kv[1]
        )[:10]:
            lines.append(f"    {etype:30s} {ncomp:>6,}  components")

    # --- Reading --------------------------------------------------

    lines.append("")
    lines.append("Reading")
    lines.append("─" * 60)

    if report.entities == 0:
        lines.append("  Empty graph — nothing to read.")
        return "\n".join(lines)

    coll_rate = report.canonical_collisions / report.entities
    coll_band = _band(coll_rate, _COLLISION_HEALTHY, _COLLISION_WARN, lower_is_better=True)
    lines.append(
        f"  ● Canonical collisions: {report.canonical_collisions:,} extra "
        f"duplicate IDs ({coll_rate:.1%} of entities) [{coll_band}]."
    )
    if coll_band == "healthy":
        lines.append(
            "      Extraction pipeline is canonicalizing cleanly — the "
            "same name across case/whitespace variants lands on the same "
            "entity."
        )
    elif coll_band == "warning":
        lines.append(
            "      Duplicates are slipping past canonicalization. Each "
            "collision is a split graph — edges that should converge on "
            "one entity are fanning across multiple IDs."
        )
    else:
        lines.append(
            "      High duplicate rate. Likely cause: entity-ID function "
            "hashes raw names without case/whitespace normalization, or "
            "the pipeline creates entities before dedup runs. "
            "Merging these would close a meaningful fraction of the "
            "graph's structural gaps."
        )

    cov_band = _band(
        report.required_field_coverage,
        _COVERAGE_HEALTHY,
        _COVERAGE_WARN,
        lower_is_better=False,
    )
    lines.append(
        f"  ● Required-field coverage: {report.required_field_coverage:.1%} "
        f"have name AND entity_type set [{cov_band}]."
    )
    if cov_band != "healthy":
        lines.append(
            "      Entities with empty name or type usually mean the "
            "extractor fired on something it couldn't resolve. These "
            "nodes pollute traversal and waste the extraction cost."
        )

    if report.edge_type_counts:
        ne_band = _band(
            report.edge_type_entropy_normalized,
            _NORM_ENTROPY_HEALTHY,
            _NORM_ENTROPY_WARN,
            lower_is_better=False,
        )
        lines.append(
            f"  ● Edge-type vocabulary: normalized entropy "
            f"{report.edge_type_entropy_normalized:.2f} "
            f"({len(report.edge_type_counts)} types) [{ne_band}]."
        )
        if ne_band == "healthy":
            lines.append(
                "      Edge vocabulary is balanced across the declared "
                "types. No monoculture."
            )
        elif ne_band == "warning":
            lines.append(
                f"      Concentrated distribution — '{report.dominant_edge_type}' "
                f"holds {report.dominant_edge_type_fraction:.1%} of edges. "
                "Investigate whether this is structural (one relation "
                "genuinely dominates) or an extractor default."
            )
        else:
            lines.append(
                f"      Edge-type monoculture — '{report.dominant_edge_type}' "
                f"holds {report.dominant_edge_type_fraction:.1%} of edges. "
                "The typed vocabulary declared in your ontology isn't "
                "showing up in the graph; a generic relation is absorbing "
                "everything."
            )

    return "\n".join(lines)


# --- 4a B-Cubed scoring against a gold alias registry -----------------


def score_alias_resolution_against_gold(
    report: IngestionIntegrityReport,
    entities: list[Entity],
    gold_aliases_path,
):
    """Score the system's alias resolution against a gold registry.

    Loads a YAML file with the shape::

        aliases:
          german_shepherd:
            canonical: "German Shepherd"
            aliases: ["GSD", "Alsatian", "German Shepherd Dog"]
          pit_bull:
            canonical: "American Pit Bull Terrier"
            aliases: ["Pit Bull", "APBT", "Pitbull"]

    For each entry, the canonical name plus its aliases form one
    true cluster. The predicted clustering is built from the
    `report.collision_groups` (system-detected canonical-collision
    clusters) plus singletons for entity names that aren't in any
    collision group, restricted to entity names that appear in the
    gold universe.

    Returns a `BCubedReport` from `sme.categories._bcubed`, or None
    if the gold registry has no items intersecting the graph (in
    which case there's nothing to score).

    What this measures: how well the system's name-canonicalization-
    only de-dup recovers known alias clusters. The current
    `default_canonical_key` only does case + whitespace
    canonicalization, so semantic aliases ("GSD" → "German Shepherd")
    will NOT collide and will appear as singletons in the predicted
    clustering. B-Cubed quantifies how much that hurts. Systems that
    layer alias_of edges or richer canonicalization on top can pass a
    custom predicted-cluster builder for a fairer score; that hook is
    deferred to a future revision.
    """
    from pathlib import Path

    import yaml

    from sme.categories._bcubed import bcubed_score

    raw = yaml.safe_load(Path(gold_aliases_path).read_text())
    aliases_section = raw.get("aliases") if isinstance(raw, dict) else None
    if not aliases_section:
        raise ValueError(
            f"{gold_aliases_path}: expected top-level `aliases:` mapping; "
            "see ontology.yaml in good-dog-corpus for the reference shape."
        )

    # Build gold clusters and the universe of items they cover.
    gold_clusters: list[frozenset[str]] = []
    gold_universe: set[str] = set()
    for entry in aliases_section.values():
        if not isinstance(entry, dict):
            continue
        canonical = entry.get("canonical")
        names = list(entry.get("aliases") or [])
        if canonical:
            names.append(canonical)
        names = [n for n in names if isinstance(n, str) and n]
        if len(names) < 2:
            # Single-item gold cluster — nothing to test alias resolution against
            continue
        cluster = frozenset(names)
        gold_clusters.append(cluster)
        gold_universe.update(cluster)

    if not gold_clusters:
        return None

    # Build the system's predicted clustering, restricted to the gold
    # universe. For each collision group, take the names that appear in
    # the gold universe and cluster them together. For each gold-universe
    # name not in any collision group, add a singleton — IF that name
    # also appears in the graph (otherwise it's not in scope for scoring).
    graph_names = {ent.name for ent in entities if ent.name}
    if not (gold_universe & graph_names):
        return None  # No overlap between gold registry and graph

    name_to_predicted_cluster: dict[str, frozenset[str]] = {}
    for group in report.collision_groups:
        in_gold = [n for n in group.names if n in gold_universe and n in graph_names]
        if len(in_gold) >= 2:
            cluster = frozenset(in_gold)
            for n in in_gold:
                name_to_predicted_cluster[n] = cluster

    # In-graph + in-gold names not in any collision group → singletons
    for n in gold_universe & graph_names:
        if n not in name_to_predicted_cluster:
            name_to_predicted_cluster[n] = frozenset({n})

    # B-Cubed needs both clusterings to cover the same item set, so
    # restrict gold clusters to items that appear in the graph too.
    filtered_gold: list[frozenset[str]] = []
    for cluster in gold_clusters:
        in_graph = cluster & graph_names
        if in_graph:
            filtered_gold.append(frozenset(in_graph))

    # Deduplicate predicted clusters (each item appears once in any
    # frozenset, so a set-of-frozensets gives unique clusters).
    predicted = list({cluster for cluster in name_to_predicted_cluster.values()})

    # Verify coverage matches before scoring (defensive).
    pred_items = {n for c in predicted for n in c}
    gold_items = {n for c in filtered_gold for n in c}
    if pred_items != gold_items:
        # Should not happen given the construction above, but guard.
        raise RuntimeError(
            f"internal: predicted/gold item sets diverged "
            f"({len(pred_items)} vs {len(gold_items)})"
        )

    return bcubed_score(predicted, filtered_gold)
