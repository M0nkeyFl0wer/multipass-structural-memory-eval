"""Shared pytest fixtures for SME tests."""

from __future__ import annotations

import pytest

from sme.topology.fixtures import synthetic_gap_graph


@pytest.fixture
def gap_graph():
    """Known-topology graph with a seeded structural gap.

    Returns ``(entities, edges, ground_truth)``. See
    ``sme.topology.fixtures.synthetic_gap_graph`` for the layout.
    """
    return synthetic_gap_graph()
