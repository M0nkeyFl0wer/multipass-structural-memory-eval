"""Shared pytest fixtures for SME tests."""

from __future__ import annotations

import pytest

from sme.topology.fixtures import synthetic_duplicates_graph, synthetic_gap_graph


@pytest.fixture
def gap_graph():
    """Known-topology graph with a seeded structural gap.

    Returns ``(entities, edges, ground_truth)``. See
    ``sme.topology.fixtures.synthetic_gap_graph`` for the layout.
    """
    return synthetic_gap_graph()


@pytest.fixture
def duplicates_graph():
    """Known-collision graph for Cat 4 (The Threshold) tests.

    Returns ``(entities, edges, ground_truth)``. See
    ``sme.topology.fixtures.synthetic_duplicates_graph`` for the
    exact collisions seeded.
    """
    return synthetic_duplicates_graph()
