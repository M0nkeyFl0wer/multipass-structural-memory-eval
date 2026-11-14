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

    Calibrated 2026-11-13 against the real vault graph, by replaying
    `check` over its archived snapshots (backups on the Pi):

    - Noise floor: 30 consecutive nightly backups (2026-10-14 to 11-13). On a
      normal night NOTHING FELL: no edge count, edge-type count or collision
      count ever decreased; every large move was growth from ingest.
    - Rule: each tolerance is at least 2.5x the worst normal-night move.
      Drops have no normal movement at all, so they get a 1% floor rather
      than a multiple of zero.
    - Signal: the labeled PINNED -> REGRESSED transition (2026-06-20/21)
      fires, and the defect-injection matrix (`sme-eval inject`) measures
      the smallest damage each tolerance catches.

    A graph that is pruned or merged on purpose WILL trip these. That is
    intended: the run stays red until someone looks and accepts the new
    baseline. What must never happen is damage going unseen.
    """

    # Relative drop in entity-to-entity edges. Normal nights: never fell.
    # Was 0.05, which let a 5% loss of all edges (1,300) pass unseen.
    edge_drop: float = 0.01
    # Relative drop for any single edge type with a meaningful count.
    # Normal nights: never fell. Was 0.20, which let 10% of PART_OF go.
    edge_type_drop: float = 0.05
    edge_type_min_count: int = 50  # ignore tiny types; they are noisy
    # Relative rise in canonical-name collisions (duplicate entities).
    # Normal-night worst: +0.04%. Was 0.10.
    collision_rise: float = 0.01
    # ...and the absolute number of new duplicates that is always worth a
    # look. Without it a graph that HAD no duplicates could gain any number
    # (a relative rise from zero is undefined); the defect-injection harness
    # caught exactly that on 2026-11-13: 0 -> 72 duplicates, no finding.
    collision_min_new: int = 25
    # Absolute rise in the dominant edge type's share (monoculture creep).
    # Normal-night worst: +0.016 (a large ingest). Was 0.05.
    dominant_share_rise: float = 0.04
    # Absolute drop in required-field coverage. Normal: always 1.000.
    coverage_drop: float = 0.01
    # Absolute rise in the share of entities that are isolated nodes.
    # Normal-night worst: +0.002. Was 0.02.
    isolated_share_rise: float = 0.005
    # The same, per entity type. The global share is ~88% document-layer
    # nodes (Notes, Chunks) on the vault graph, which dilutes a knowledge-
    # layer type going dark; per type it shows. Normal-night worst: +0.012
    # (3.5k entities landing a night before their edges). Was 0.05.
    # Types smaller than `type_min_count` are skipped as noise.
    type_isolated_share_rise: float = 0.03
    type_min_count: int = 200


def _rel_drop(prev: float, cur: float) -> float:
    return (prev - cur) / prev if prev else 0.0


def compare_readings(prev: dict, cur: dict, tol: Tolerances | None = None) -> list[str]:
    """Return one human-readable finding per metric that regressed.

    Thin wrapper over `compare_readings_keyed` for callers that only print.
    """
    return [what for _key, what in compare_readings_keyed(prev, cur, tol)]


def compare_readings_keyed(
    prev: dict, cur: dict, tol: Tolerances | None = None
) -> list[tuple[str, str]]:
    """Return `(key, finding)` per metric that regressed beyond its tolerance.

    `key` names the METRIC, never its value ("edges", "edge_type:PART_OF"),
    so the same regression on two consecutive nights has the same identity.
    The operator digest dedupes on it: a stable key reads as "STILL OPEN,
    day 3"; a key that embedded the numbers would look NEW every morning.

    `prev` and `cur` are the dicts written by `sme-eval check --json`.
    Missing keys are skipped, not treated as regressions, so an older
    baseline written before a field existed never raises a false alarm.
    """
    tol = tol or Tolerances()
    findings: list[tuple[str, str]] = []
    p4, c4 = prev.get("cat4", {}), cur.get("cat4", {})
    p5, c5 = prev.get("cat5", {}), cur.get("cat5", {})

    # Edges disappearing is the loudest signal: extraction stopped, a prune
    # over-reached, or the reader is looking at the wrong tables.
    if "edges" in p4 and "edges" in c4:
        drop = _rel_drop(p4["edges"], c4["edges"])
        if drop > tol.edge_drop:
            findings.append(
                (
                    "edges",
                    f"edges fell {drop:.1%} ({p4['edges']} -> {c4['edges']})"
                    + _largest_type_drops(p4, c4),
                )
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
            findings.append(
                (f"edge_type:{etype}", f"edge type {etype} disappeared ({before} -> 0)")
            )
        elif drop > tol.edge_type_drop:
            findings.append(
                (f"edge_type:{etype}", f"edge type {etype} fell {drop:.1%} ({before} -> {after})")
            )

    if "canonical_collisions" in p4 and "canonical_collisions" in c4:
        before, after = p4["canonical_collisions"], c4["canonical_collisions"]
        new_dupes = after - before
        rel = new_dupes / before if before else float("inf")
        # Both a relative and an absolute bar: relative alone fires on a
        # handful of new duplicates in a small graph and never from zero.
        if new_dupes >= tol.collision_min_new and rel > tol.collision_rise:
            rise = f"{rel:.1%}" if before else f"from zero, +{new_dupes}"
            findings.append(
                (
                    "canonical_collisions",
                    f"canonical collisions rose {rise} "
                    f"({before} -> {after}): entity resolution may have regressed"
                    + _largest_collision_groups(c4),
                )
            )

    if "dominant_edge_type_fraction" in p4 and "dominant_edge_type_fraction" in c4:
        rise = c4["dominant_edge_type_fraction"] - p4["dominant_edge_type_fraction"]
        if rise > tol.dominant_share_rise:
            findings.append(
                (
                    "dominant_edge_type_share",
                    f"dominant edge type ({c4.get('dominant_edge_type')}) share rose "
                    f"{rise:+.3f} to {c4['dominant_edge_type_fraction']:.3f}: "
                    f"edge-type monoculture creeping in",
                )
            )

    if "required_field_coverage" in p4 and "required_field_coverage" in c4:
        fall = p4["required_field_coverage"] - c4["required_field_coverage"]
        if fall > tol.coverage_drop:
            findings.append(
                (
                    "required_field_coverage",
                    f"required-field coverage fell {fall:.3f} "
                    f"({p4['required_field_coverage']:.3f} -> "
                    f"{c4['required_field_coverage']:.3f})",
                )
            )

    # Isolated share, not raw count: the entity total moves for legitimate
    # reasons (purges, re-ingests), so compare proportions.
    if all(
        k in d
        for d, k in (
            (p5, "isolated_nodes"),
            (c5, "isolated_nodes"),
            (p4, "entities"),
            (c4, "entities"),
        )
    ):
        if p4["entities"] and c4["entities"]:
            before = p5["isolated_nodes"] / p4["entities"]
            after = c5["isolated_nodes"] / c4["entities"]
            if after - before > tol.isolated_share_rise:
                findings.append(
                    (
                        "isolated_share",
                        f"isolated-node share rose {after - before:+.3f} "
                        f"({before:.3f} -> {after:.3f}): new entities are not "
                        f"being connected" + _largest_isolated_rises(p4, c4, p5, c5),
                    )
                )

    # Per-type isolated share: locates the problem to one entity type, and
    # catches a knowledge-layer type going dark that the global share hides.
    for etype, (before, after) in _type_isolated_shares(p4, c4, p5, c5, tol).items():
        if after - before > tol.type_isolated_share_rise:
            findings.append(
                (
                    f"isolated_share:{etype}",
                    f"isolated share of {etype} rose {after - before:+.3f} "
                    f"({before:.3f} -> {after:.3f})",
                )
            )

    findings.extend(_cat8_vocabulary_findings(prev.get("cat8"), cur.get("cat8")))
    return findings


def _cat8_vocabulary_findings(p8: dict | None, c8: dict | None) -> list[tuple[str, str]]:
    """Ontology drift since the baseline, from the `cat8` block of a reading.

    Only CHANGES are findings. The vault graph carries standing drift (e.g.
    note types the schema never declared); reporting that every night would
    be the alarm nobody reads. What is new is what someone just broke.
    Skipped unless both readings were scored against the SAME ontology file.
    """
    if not p8 or not c8 or p8.get("ontology") != c8.get("ontology"):
        return []
    out: list[tuple[str, str]] = []
    for etype in sorted(set(c8.get("edges_undeclared", [])) - set(p8.get("edges_undeclared", []))):
        out.append(
            (
                f"cat8:undeclared_edge:{etype}",
                f"new edge type {etype} is in the graph but not in the declared "
                f"schema: declare it, or find the extractor emitting it",
            )
        )
    newly_missing = sorted(
        (set(c8.get("types_missing", [])) - set(p8.get("types_missing", [])))
        | (set(c8.get("edges_missing", [])) - set(p8.get("edges_missing", [])))
    )
    for name in newly_missing:
        out.append(
            (
                f"cat8:vanished:{name}",
                f"declared type {name} was in use and is now absent from the graph",
            )
        )
    new_types = sorted(set(c8.get("types_undeclared", [])) - set(p8.get("types_undeclared", [])))
    if new_types:
        shown = ", ".join(new_types[:8]) + (" ..." if len(new_types) > 8 else "")
        out.append(
            (
                "cat8:undeclared_entity_types",
                f"{len(new_types)} new entity type(s) not in the declared schema: {shown}",
            )
        )
    return out


# --- locating helpers --------------------------------------------------
# A finding that only says "how much" sends you hunting. These append
# "where" from the per-type fields the reading carries. Each returns "" when
# the fields are missing (older readings), so a finding never breaks on them.


def _largest_type_drops(p4: dict, c4: dict, n: int = 3) -> str:
    p, c = p4.get("edge_type_counts") or {}, c4.get("edge_type_counts") or {}
    drops = sorted(((c.get(t, 0) - v, t) for t, v in p.items()), key=lambda x: x[0])
    parts = [f"{t} {d:+d}" for d, t in drops[:n] if d < 0]
    return f"; largest drops: {', '.join(parts)}" if parts else ""


def short_name(name, limit: int = 60) -> str:
    """One line, at most `limit` chars. Some graphs name nodes by their whole
    text (a chunk's body); a finding must stay a single readable line."""
    flat = " ".join(str(name).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "\u2026"


def _largest_collision_groups(c4: dict, n: int = 3) -> str:
    groups = c4.get("collision_examples") or []
    parts = [
        f"'{short_name((g.get('names') or [g.get('key')])[0])}' x{g.get('n')}"
        for g in groups[:n]
    ]
    return f"; largest groups now: {', '.join(parts)}" if parts else ""


def _type_isolated_shares(
    p4: dict, c4: dict, p5: dict, c5: dict, tol: Tolerances
) -> dict[str, tuple[float, float]]:
    """`{type: (share_before, share_after)}` for types big enough to judge."""
    pn, cn = p4.get("entity_type_counts") or {}, c4.get("entity_type_counts") or {}
    pi, ci = p5.get("isolated_by_type") or {}, c5.get("isolated_by_type") or {}
    if not (pn and cn and pi is not None and ci is not None and "isolated_by_type" in c5):
        return {}
    out = {}
    for t in sorted(set(pn) & set(cn)):
        if pn[t] < tol.type_min_count or cn[t] < tol.type_min_count:
            continue
        out[t] = (pi.get(t, 0) / pn[t], ci.get(t, 0) / cn[t])
    return out


def _largest_isolated_rises(p4: dict, c4: dict, p5: dict, c5: dict, n: int = 3) -> str:
    pi, ci = p5.get("isolated_by_type") or {}, c5.get("isolated_by_type") or {}
    if not ci:
        return ""
    rises = sorted(((ci.get(t, 0) - pi.get(t, 0), t) for t in ci), reverse=True)
    parts = [f"{t} {d:+d}" for d, t in rises[:n] if d > 0]
    return f"; most new isolates: {', '.join(parts)}" if parts else ""
