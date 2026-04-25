"""Live-daemon smoke tests for MemPalaceDaemonAdapter.

Skipped automatically when PALACE_DAEMON_URL is not set in the
environment, so CI without a daemon stays green. Run locally with:

    PALACE_DAEMON_URL=http://disks.jphe.in:8085 \
    PALACE_API_KEY=$(grep ^PALACE_API_KEY ~/.config/palace-daemon/env | cut -d= -f2) \
    pytest tests/test_mempalace_daemon_integration.py -v

The tests are read-only: query() and get_graph_snapshot() only.
"""

from __future__ import annotations

import os

import pytest

from sme.adapters.base import QueryResult
from sme.adapters.mempalace_daemon import MemPalaceDaemonAdapter


pytestmark = pytest.mark.skipif(
    not os.environ.get("PALACE_DAEMON_URL"),
    reason="needs a running palace-daemon; set PALACE_DAEMON_URL to enable",
)


@pytest.fixture
def adapter():
    a = MemPalaceDaemonAdapter()
    yield a
    a.close()


def test_query_returns_query_result(adapter):
    r = adapter.query("hello", n_results=2)
    assert isinstance(r, QueryResult)
    # Either we got results, or we got a soft-warn / NO_RESULTS — never an
    # uncaught exception.


def test_snapshot_returns_at_least_one_wing(adapter):
    entities, _ = adapter.get_graph_snapshot()
    wing_names = {e.name for e in entities if e.entity_type == "wing"}
    # Live palace has 30+ wings on JP's install; even a fresh palace has >=1.
    assert len(wing_names) >= 1


def test_kind_default_excludes_more_than_kind_all(adapter):
    """Cross-check the README's claim: kind='content' filters strictly
    less than kind='all'. If the live palace has any auto-save
    checkpoints, this assertion holds; on a fresh palace it might be
    equal — assert >= rather than > to avoid flakes."""
    r_all = adapter.query("the", n_results=5, kind="all")
    r_content = adapter.query("the", n_results=5, kind="content")
    # We can't compare result counts directly because limit caps both;
    # use total_before_filter from retrieval_path.
    def total_before(rp):
        for s in rp:
            if s.startswith("total_before_filter="):
                # value may be 'None' on errored queries
                v = s.split("=", 1)[1]
                try:
                    return int(v)
                except ValueError:
                    return -1
        return -1
    assert total_before(r_all.retrieval_path) >= total_before(
        r_content.retrieval_path
    )
