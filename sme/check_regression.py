"""Day-over-day regression detection for `sme-eval check`.

Until 2026-11-13 `check` always exited 0: the nightly run recorded numbers
and nobody was told when they moved. This module compares today's JSON
reading against the previous one and returns human-readable findings for
movements large enough to deserve a look.

Read the findings as "go look", never as "the graph is corrupt". An
aggregate delta cannot tell an engine bug from an intended change (a merge,
dedup, or prune legitimately moves these numbers; see the 2026-06-19
LadybugDB mis-measurement in ~/.claude/rules/verification.md section 4).
The point is that a human finds out the same morning, rather than nine
nights later.

Pure functions over the dicts `check --json` writes, so this is testable
without a graph and reusable by anything that reads `sme.json`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tolerances:
    """How far a metric may move between two readings before it is flagged.

    Defaults are deliberately loose: an alarm that fires every morning
    gets ignored, which is worse than no alarm.
    """

    # Relative drop in entity-to-entity edges (0.05 = 5% fewer edges).
    edge_drop: float = 0.05
    # Relative drop for any single edge type with a meaningful count.
    edge_type_drop: float = 0.20
    edge_type_min_count: int = 50  # ignore tiny types; they are noisy
    # Relative rise in canonical-name collisions (duplicate entities).
    collision_rise: float = 0.10
    # Absolute rise in the dominant edge type's share (monoculture creep).
    dominant_share_rise: float = 0.05
    # Absolute drop in required-field coverage.
    coverage_drop: float = 0.01
    # Absolute rise in the share of entities that are isolated nodes.
    isolated_share_rise: float = 0.02


def _rel_drop(prev: float, cur: float) -> float:
    return (prev - cur) / prev if prev else 0.0


def compare_readings(prev: dict, cur: dict, tol: Tolerances | None = None) -> list[str]:
    """Return one finding per metric that regressed beyond its tolerance.

    `prev` and `cur` are the dicts written by `sme-eval check --json`.
    Missing keys are skipped, not treated as regressions, so an older
    baseline written before a field existed never raises a false alarm.
    """
    tol = tol or Tolerances()
    findings: list[str] = []
    p4, c4 = prev.get("cat4", {}), cur.get("cat4", {})
    p5, c5 = prev.get("cat5", {}), cur.get("cat5", {})

    # Edges disappearing is the loudest signal: extraction stopped, a prune
    # over-reached, or the reader is looking at the wrong tables.
    if "edges" in p4 and "edges" in c4:
        drop = _rel_drop(p4["edges"], c4["edges"])
        if drop > tol.edge_drop:
            findings.append(
                f"edges fell {drop:.1%} ({p4['edges']} -> {c4['edges']})"
            )

    # Per-type drops catch a single relation vanishing or being re-typed,
    # which a stable total can hide.
    p_types = p4.get("edge_type_counts") or {}
    c_types = c4.get("edge_type_counts") or {}
    for etype, before in sorted(p_types.items()):
        if before < tol.edge_type_min_count:
            continue
        after = c_types.get(etype, 0)
        drop = _rel_drop(before, after)
        if after == 0:
            findings.append(f"edge type {etype} disappeared ({before} -> 0)")
        elif drop > tol.edge_type_drop:
            findings.append(
                f"edge type {etype} fell {drop:.1%} ({before} -> {after})"
            )

    if "canonical_collisions" in p4 and "canonical_collisions" in c4:
        before, after = p4["canonical_collisions"], c4["canonical_collisions"]
        if before and (after - before) / before > tol.collision_rise:
            findings.append(
                f"canonical collisions rose {(after - before) / before:.1%} "
                f"({before} -> {after}): entity resolution may have regressed"
            )

    if "dominant_edge_type_fraction" in p4 and "dominant_edge_type_fraction" in c4:
        rise = c4["dominant_edge_type_fraction"] - p4["dominant_edge_type_fraction"]
        if rise > tol.dominant_share_rise:
            findings.append(
                f"dominant edge type ({c4.get('dominant_edge_type')}) share rose "
                f"{rise:+.3f} to {c4['dominant_edge_type_fraction']:.3f}: "
                f"edge-type monoculture creeping in"
            )

    if "required_field_coverage" in p4 and "required_field_coverage" in c4:
        fall = p4["required_field_coverage"] - c4["required_field_coverage"]
        if fall > tol.coverage_drop:
            findings.append(
                f"required-field coverage fell {fall:.3f} "
                f"({p4['required_field_coverage']:.3f} -> "
                f"{c4['required_field_coverage']:.3f})"
            )

    # Isolated share, not raw count: the entity total moves for legitimate
    # reasons (purges, re-ingests), so compare proportions.
    if all(k in d for d, k in ((p5, "isolated_nodes"), (c5, "isolated_nodes"),
                                (p4, "entities"), (c4, "entities"))):
        if p4["entities"] and c4["entities"]:
            before = p5["isolated_nodes"] / p4["entities"]
            after = c5["isolated_nodes"] / c4["entities"]
            if after - before > tol.isolated_share_rise:
                findings.append(
                    f"isolated-node share rose {after - before:+.3f} "
                    f"({before:.3f} -> {after:.3f}): new entities are not "
                    f"being connected"
                )

    return findings
