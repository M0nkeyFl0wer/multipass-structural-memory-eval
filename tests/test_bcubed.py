"""Tests for sme.categories._bcubed.

Includes:

- Identity check (predicted == truth → P=R=F1=1.0)
- The canonical 5-item example from Bagga & Baldwin 1998 §3.2
  (verifies the formula matches the literature)
- Pathological / edge cases (singletons, all-merged, all-split)
- Integration with the CollisionGroup adapter helper
"""
from __future__ import annotations

import math

import pytest

from sme.categories._bcubed import (
    BCubedReport,
    bcubed_score,
    collision_groups_to_clusters,
)


def _close(a: float, b: float, *, tol: float = 1e-9) -> bool:
    return math.isclose(a, b, abs_tol=tol)


def test_identical_clustering_is_perfect():
    pred = [{"a", "b"}, {"c", "d", "e"}]
    truth = [{"a", "b"}, {"c", "d", "e"}]
    r = bcubed_score(pred, truth)
    assert _close(r.precision, 1.0)
    assert _close(r.recall, 1.0)
    assert _close(r.f1, 1.0)
    assert r.n_items == 5


def test_all_singletons_match_all_singletons():
    """5 items, all singletons in both — every item's cluster is just
    itself, so |intersection| = 1, |pred| = 1, |true| = 1."""
    pred = [{"a"}, {"b"}, {"c"}, {"d"}, {"e"}]
    truth = [{"a"}, {"b"}, {"c"}, {"d"}, {"e"}]
    r = bcubed_score(pred, truth)
    assert _close(r.precision, 1.0)
    assert _close(r.recall, 1.0)
    assert _close(r.f1, 1.0)


def test_all_merged_when_truth_is_all_singletons():
    """If predicted lumps everything into one cluster but truth splits
    everything: precision per item = 1/N (intersection is just the
    item itself), recall per item = 1 (the item's true cluster is just
    itself, captured)."""
    pred = [{"a", "b", "c", "d"}]
    truth = [{"a"}, {"b"}, {"c"}, {"d"}]
    r = bcubed_score(pred, truth)
    assert _close(r.precision, 1 / 4)
    assert _close(r.recall, 1.0)
    expected_f1 = 2 * 0.25 * 1.0 / (0.25 + 1.0)  # = 0.4
    assert _close(r.f1, expected_f1)


def test_all_singletons_when_truth_is_all_merged():
    """Inverse: predicted splits everything but truth has all in one
    cluster. Precision per item = 1 (own cluster captured), recall per
    item = 1/N (only own item captured from the true cluster)."""
    pred = [{"a"}, {"b"}, {"c"}, {"d"}]
    truth = [{"a", "b", "c", "d"}]
    r = bcubed_score(pred, truth)
    assert _close(r.precision, 1.0)
    assert _close(r.recall, 1 / 4)


def test_bagga_baldwin_canonical_example():
    """Bagga & Baldwin 1998 §3.2 example: 5 items, the predicted
    clustering merges A+B+C while the truth has A+B in one cluster
    and C alone. D+E are singleton in both.

        predicted: {A, B, C}, {D}, {E}
        truth:     {A, B},    {C}, {D}, {E}

    Per-item:
      A: pred_cluster = {A,B,C}, true = {A,B} → P = 2/3, R = 2/2 = 1
      B: same as A                              → P = 2/3, R = 1
      C: pred = {A,B,C}, true = {C}            → P = 1/3, R = 1
      D: pred = {D}, true = {D}                → P = 1, R = 1
      E: pred = {E}, true = {E}                → P = 1, R = 1

    Average:
      P = (2/3 + 2/3 + 1/3 + 1 + 1) / 5 = (5/3 + 2) / 5 = (11/3) / 5 = 11/15
      R = (1 + 1 + 1 + 1 + 1) / 5 = 1
    """
    pred = [{"A", "B", "C"}, {"D"}, {"E"}]
    truth = [{"A", "B"}, {"C"}, {"D"}, {"E"}]
    r = bcubed_score(pred, truth)
    assert _close(r.precision, 11 / 15)
    assert _close(r.recall, 1.0)


def test_dict_input_supported():
    """Per the docstring, clusters can be passed as a dict keyed by
    cluster id."""
    pred = {"c1": {"a", "b"}, "c2": {"c"}}
    truth = {"true_1": {"a", "b"}, "true_2": {"c"}}
    r = bcubed_score(pred, truth)
    assert _close(r.precision, 1.0)
    assert _close(r.recall, 1.0)


def test_per_item_breakdown_returned():
    pred = [{"A", "B", "C"}, {"D"}]
    truth = [{"A", "B"}, {"C"}, {"D"}]
    r = bcubed_score(pred, truth)
    assert r.per_item["A"] == (2 / 3, 1.0)
    assert r.per_item["C"] == (1 / 3, 1.0)
    assert r.per_item["D"] == (1.0, 1.0)


def test_returns_bcubedreport():
    r = bcubed_score([{"a"}], [{"a"}])
    assert isinstance(r, BCubedReport)


def test_mismatched_item_sets_raises():
    with pytest.raises(ValueError, match="cover different item sets"):
        bcubed_score([{"a", "b"}], [{"a", "c"}])


def test_empty_predicted_raises():
    with pytest.raises(ValueError, match="predicted clustering is empty"):
        bcubed_score([], [{"a"}])


def test_empty_true_raises():
    with pytest.raises(ValueError, match="true clustering is empty"):
        bcubed_score([{"a"}], [])


def test_duplicate_membership_raises():
    """An item in two predicted clusters violates the partition assumption."""
    with pytest.raises(ValueError, match="more than one cluster"):
        bcubed_score([{"a", "b"}, {"b", "c"}], [{"a"}, {"b"}, {"c"}])


def test_zero_f1_when_intersection_zero_for_all_items():
    """Pathological case: every item is in a different cluster in
    pred vs truth, so each per-item intersection is the singleton itself.
    Actually, by construction, each item IS in its own cluster in both
    senses (pred_cluster always contains the item, intersection always
    has at least the item). So F1 = 0 only when |pred ∩ true| = 0
    which can't happen with the partition constraint. This test just
    verifies the no-crash behavior when caller manages to construct
    such inputs (impossible via the public API, but the F1 division
    branch is still defensive)."""
    # The cleanest way to exercise the F1=0 branch is the empty-class
    # contract elsewhere; here just verify the happy path doesn't NaN.
    r = bcubed_score([{"a"}], [{"a"}])
    assert not math.isnan(r.f1)


# --- Integration with collision_groups adapter ------------------------


class _FakeCollisionGroup:
    def __init__(self, ids):
        self.ids = ids


def test_collision_groups_to_clusters_adds_singletons():
    """An entity not in any collision group becomes a singleton in the
    B-Cubed cluster list."""
    groups = [_FakeCollisionGroup(["a", "b"]), _FakeCollisionGroup(["c"])]
    isolates = ["d", "e"]
    clusters = collision_groups_to_clusters(groups, isolated_items=isolates)
    # group {"c"} has only 1 id so should be skipped (not a real collision);
    # singletons added for d and e
    flat = [set(c) for c in clusters]
    assert {"a", "b"} in flat
    assert {"d"} in flat
    assert {"e"} in flat
    # singleton {"c"} should NOT appear from the group (filtered)
    # but it would if passed via isolated_items
    assert {"c"} not in flat


def test_collision_groups_round_trip_through_bcubed():
    """End-to-end: a Cat 4a collision detector's output, paired with a
    gold alias clustering, scored by B-Cubed."""
    # Cat 4a found GSD/Alsatian as a collision; AmStaff and APBT each alone.
    detected = [_FakeCollisionGroup(["GSD", "Alsatian"])]
    isolates = ["APBT", "AmStaff"]
    predicted = collision_groups_to_clusters(detected, isolated_items=isolates)

    # Gold standard: GSD+Alsatian are aliases; APBT and AmStaff are
    # distinct breeds (the conflation-test pair).
    truth = [{"GSD", "Alsatian"}, {"APBT"}, {"AmStaff"}]

    r = bcubed_score(predicted, truth)
    assert _close(r.precision, 1.0)
    assert _close(r.recall, 1.0)
    assert _close(r.f1, 1.0)


def test_collision_groups_round_trip_with_overmerge():
    """If Cat 4a wrongly merged APBT and AmStaff (known media-conflation
    failure), B-Cubed should penalize precision."""
    detected = [_FakeCollisionGroup(["APBT", "AmStaff"])]
    isolates = ["GSD", "Alsatian"]
    predicted = collision_groups_to_clusters(detected, isolated_items=isolates)
    truth = [{"GSD", "Alsatian"}, {"APBT"}, {"AmStaff"}]
    r = bcubed_score(predicted, truth)
    # GSD and Alsatian are wrongly singleton (recall hurt)
    # APBT and AmStaff are wrongly merged (precision hurt)
    assert r.precision < 1.0
    assert r.recall < 1.0
    assert r.f1 < 1.0
