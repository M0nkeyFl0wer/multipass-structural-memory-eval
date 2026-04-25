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


def test_kind_content_excludes_stop_hook_checkpoints(adapter):
    """Cross-check the README's behavioural claim: kind='content'
    excludes Stop-hook auto-save checkpoints (which start with
    'CHECKPOINT:' in the live palace) while kind='all' includes them.

    The earlier-shape assertion on total_before_filter conflated
    metadata math with filter behaviour — `total_before_filter` is
    not "scope size before kind filter". The reliable signal is in
    the returned context_string itself: do CHECKPOINT: strings
    appear or not?
    """
    r_all = adapter.query("CHECKPOINT", n_results=5, kind="all")
    r_content = adapter.query("CHECKPOINT", n_results=5, kind="content")

    # If the live palace has zero checkpoints, both will be empty —
    # skip rather than fail.
    if "CHECKPOINT:" not in (r_all.context_string or ""):
        pytest.skip(
            "live palace has no Stop-hook checkpoints to test against"
        )

    # The behavioural invariant: kind='content' must have strictly
    # fewer (or zero) CHECKPOINT: strings than kind='all'.
    n_all = (r_all.context_string or "").count("CHECKPOINT:")
    n_content = (r_content.context_string or "").count("CHECKPOINT:")
    assert n_content < n_all, (
        f"kind='content' should filter checkpoints, got "
        f"{n_content} vs {n_all} for kind='all'"
    )
