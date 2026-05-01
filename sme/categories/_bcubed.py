"""B-Cubed precision / recall / F1 for entity-resolution scoring.

Bagga & Baldwin (1998) introduced the B-Cubed metric for cross-document
coreference. Amigó et al. (2009) — "A comparison of extrinsic clustering
evaluation metrics based on formal constraints" — proved it is the only
common cluster-evaluation metric satisfying all four formal constraints
(homogeneity, completeness, rag bag, cluster size vs. quantity).

This module is the scorer SME uses for **Cat 4a alias resolution**
when a gold-standard alias clustering is available (e.g. the
``ontology.yaml#aliases`` registry in good-dog-corpus, or the seeded
alias pairs in standard_v0_1). Without a gold standard, Cat 4a
remains in collision-counting mode (the existing
``ingestion_integrity.py`` path); with a gold standard, the same
canonicalization output gets scored against it via B-Cubed.

Definition (per Bagga & Baldwin 1998 §3):

    For each item i, let:
        P(i) = the cluster i is in under the predicted clustering
        T(i) = the cluster i is in under the gold/true clustering
        precision_i = |P(i) ∩ T(i)| / |P(i)|
        recall_i    = |P(i) ∩ T(i)| / |T(i)|

    Then:
        precision = (1/N) Σ precision_i
        recall    = (1/N) Σ recall_i
        f1        = 2 * P * R / (P + R)

Edge cases handled here:

* Predicted and true must cover the same item set; mismatch raises
  ValueError (the caller should resolve the universe before scoring).
* Empty cluster collections raise ValueError (no items, no metric).
* Singleton-in-both is precision=recall=1 for that item; this is
  the correct B-Cubed behavior for items that have no aliases.
* When P+R = 0 (which only happens with empty intersection across all
  items — a pathological case), F1 returns 0.0 rather than NaN.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BCubedReport:
    """Headline B-Cubed scores plus the per-item breakdown."""

    precision: float
    recall: float
    f1: float
    n_items: int
    per_item: dict[str, tuple[float, float]]  # item -> (precision_i, recall_i)


def _to_item_to_cluster(
    clusters: Iterable[Iterable[str]] | dict[str, Iterable[str]],
) -> dict[str, frozenset[str]]:
    """Turn a clustering (list-of-sets or dict-of-sets) into a
    flat ``{item: cluster_membership}`` lookup, where ``cluster_membership``
    is the frozen set of items in i's cluster.

    Each item must appear in exactly one cluster. Duplicate
    memberships raise ValueError.
    """
    if isinstance(clusters, dict):
        cluster_iter = clusters.values()
    else:
        cluster_iter = clusters

    out: dict[str, frozenset[str]] = {}
    for cluster in cluster_iter:
        members = frozenset(cluster)
        if not members:
            continue
        for item in members:
            if item in out:
                raise ValueError(
                    f"item {item!r} appears in more than one cluster — "
                    f"B-Cubed requires a partition (disjoint clusters)"
                )
            out[item] = members
    return out


def bcubed_score(
    predicted: Iterable[Iterable[str]] | dict[str, Iterable[str]],
    true: Iterable[Iterable[str]] | dict[str, Iterable[str]],
) -> BCubedReport:
    """Compute B-Cubed precision / recall / F1.

    Args:
        predicted: System's clustering. Each cluster is an iterable of
            item ids (typically entity surface forms or canonical keys).
            Can be passed as a list/iterable of clusters or as a dict
            keyed by cluster id.
        true: Gold-standard clustering, same shape.

    Returns:
        ``BCubedReport`` with averaged P/R/F1, item count, and per-item
        breakdown (useful for surfacing the items where the predicted
        clustering disagrees with truth).

    Raises:
        ValueError: if ``predicted`` and ``true`` cover different item
            sets, or if either is empty, or if either contains an item
            in multiple clusters.
    """
    pred_lookup = _to_item_to_cluster(predicted)
    true_lookup = _to_item_to_cluster(true)

    if not pred_lookup:
        raise ValueError("predicted clustering is empty")
    if not true_lookup:
        raise ValueError("true clustering is empty")

    if set(pred_lookup) != set(true_lookup):
        only_pred = set(pred_lookup) - set(true_lookup)
        only_true = set(true_lookup) - set(pred_lookup)
        raise ValueError(
            "predicted and true clusterings cover different item sets; "
            f"only in predicted: {sorted(only_pred)[:5]}{'...' if len(only_pred) > 5 else ''} "
            f"only in true: {sorted(only_true)[:5]}{'...' if len(only_true) > 5 else ''}"
        )

    per_item: dict[str, tuple[float, float]] = {}
    p_sum = 0.0
    r_sum = 0.0
    n = 0

    for item, pred_cluster in pred_lookup.items():
        true_cluster = true_lookup[item]
        intersection = len(pred_cluster & true_cluster)
        precision_i = intersection / len(pred_cluster)
        recall_i = intersection / len(true_cluster)
        per_item[item] = (precision_i, recall_i)
        p_sum += precision_i
        r_sum += recall_i
        n += 1

    precision = p_sum / n
    recall = r_sum / n
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return BCubedReport(
        precision=precision,
        recall=recall,
        f1=f1,
        n_items=n,
        per_item=per_item,
    )


def collision_groups_to_clusters(
    collision_groups: Iterable,  # list[CollisionGroup] from ingestion_integrity
    *,
    isolated_items: Iterable[str] = (),
) -> list[frozenset[str]]:
    """Convert ``CollisionGroup`` records (from Cat 4a) into a B-Cubed-shaped
    cluster list.

    Each CollisionGroup with ≥2 entity IDs becomes one cluster.
    Entity IDs *not* in any collision group must be passed as
    ``isolated_items`` so they appear as singleton clusters in the
    output — B-Cubed needs the full item set, including unmerged
    entities.

    Args:
        collision_groups: Iterable of CollisionGroup-like objects with
            an ``ids: list[str]`` attribute (duck-typed; we don't
            import the dataclass here to keep this module decoupled).
        isolated_items: entity IDs not in any collision group.

    Returns:
        List of frozensets, one per cluster (singletons + collision
        groups), suitable to pass to ``bcubed_score(predicted=...)``.
    """
    out: list[frozenset[str]] = []
    seen: set[str] = set()
    for group in collision_groups:
        ids = list(group.ids)
        if len(ids) < 2:
            continue
        out.append(frozenset(ids))
        seen.update(ids)
    for item in isolated_items:
        if item not in seen:
            out.append(frozenset({item}))
    return out
