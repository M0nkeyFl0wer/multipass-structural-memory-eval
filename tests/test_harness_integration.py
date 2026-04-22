"""Tests for Category 9: Harness Integration — The Handshake.

Covers the 9b sub-test (call-through success) only — the minimum-viable
surface currently implemented. Other sub-tests (9a, 9c–9g) are spec'd
but not implemented and therefore have no tests here.
"""

from __future__ import annotations

from sme.adapters.base import HarnessDescriptor, ProbeResult, SMEAdapter
from sme.categories.harness_integration import (
    format_cat9b_report,
    run_cat9b,
)


class _StubAdapter(SMEAdapter):
    """Minimal adapter that lets a test pre-declare a harness manifest.

    Only overrides the three abstract methods + get_harness_manifest().
    """

    def __init__(self, manifest: list[HarnessDescriptor]) -> None:
        self._manifest = manifest

    def ingest_corpus(self, corpus):
        return {"entities_created": 0, "edges_created": 0, "errors": [], "warnings": []}

    def query(self, question):
        from sme.adapters.base import QueryResult

        return QueryResult(answer="")

    def get_graph_snapshot(self):
        return [], []

    def get_harness_manifest(self):
        return self._manifest


# --- 9b: empty manifest ------------------------------------------------


def test_cat9b_empty_manifest_reports_not_applicable():
    adapter = _StubAdapter(manifest=[])
    result = run_cat9b(adapter)
    assert result.empty_manifest is True
    assert result.total_probes == 0
    assert result.band == "n/a"
    report = format_cat9b_report(result)
    assert "declared no harness manifest" in report


# --- 9b: all probes succeed --------------------------------------------


def test_cat9b_all_probes_succeed_is_healthy():
    descriptors = [
        HarnessDescriptor(
            name=f"probe_{i}",
            kind="mcp_resource",
            probe_fn=lambda: ProbeResult(success=True, latency_ms=1.0),
        )
        for i in range(3)
    ]
    adapter = _StubAdapter(manifest=descriptors)
    result = run_cat9b(adapter)
    assert result.total_probes == 3
    assert result.successful_probes == 3
    assert result.failed_probes == 0
    assert result.call_through_rate == 1.0
    assert result.band == "healthy"


# --- 9b: probe raises an exception -------------------------------------


def test_cat9b_raising_probe_counts_as_failure():
    def boom() -> ProbeResult:
        raise RuntimeError("integration broken")

    adapter = _StubAdapter(
        manifest=[
            HarnessDescriptor(name="boom", kind="tool_call", probe_fn=boom),
        ]
    )
    result = run_cat9b(adapter)
    assert result.failed_probes == 1
    assert result.successful_probes == 0
    assert result.readings[0].result.success is False
    assert "RuntimeError" in (result.readings[0].result.error or "")


# --- 9b: mixed outcomes give correct banding ---------------------------


def test_cat9b_mixed_outcomes_produce_warn_band():
    # 4 probes total, 3 succeed, 1 fails → 75% → concerning (< 80% warn floor)
    descriptors = [
        HarnessDescriptor(
            name=f"ok_{i}",
            kind="mcp_resource",
            probe_fn=lambda: ProbeResult(success=True, latency_ms=1.0),
        )
        for i in range(3)
    ]
    descriptors.append(
        HarnessDescriptor(
            name="bad",
            kind="mcp_resource",
            probe_fn=lambda: ProbeResult(success=False, error="timeout"),
        )
    )
    adapter = _StubAdapter(manifest=descriptors)
    result = run_cat9b(adapter)
    assert result.total_probes == 4
    assert result.successful_probes == 3
    assert result.failed_probes == 1
    assert abs(result.call_through_rate - 0.75) < 1e-9
    assert result.band == "concerning"  # 75% < 80% warn threshold


def test_cat9b_warn_band_at_exactly_80_percent():
    # 5 probes, 4 succeed → 80% → warn band
    descriptors = [
        HarnessDescriptor(
            name=f"ok_{i}",
            kind="mcp_resource",
            probe_fn=lambda: ProbeResult(success=True, latency_ms=1.0),
        )
        for i in range(4)
    ]
    descriptors.append(
        HarnessDescriptor(
            name="bad",
            kind="mcp_resource",
            probe_fn=lambda: ProbeResult(success=False, error="timeout"),
        )
    )
    adapter = _StubAdapter(manifest=descriptors)
    result = run_cat9b(adapter)
    assert result.band == "warn"


# --- 9b: by-kind breakdown ---------------------------------------------


def test_cat9b_by_kind_counts_are_accurate():
    descriptors = [
        HarnessDescriptor(
            name="mcp_ok",
            kind="mcp_resource",
            probe_fn=lambda: ProbeResult(success=True),
        ),
        HarnessDescriptor(
            name="mcp_bad",
            kind="mcp_resource",
            probe_fn=lambda: ProbeResult(success=False, error="x"),
        ),
        HarnessDescriptor(
            name="hook_ok",
            kind="claude_code_hook",
            probe_fn=lambda: ProbeResult(success=True),
        ),
    ]
    adapter = _StubAdapter(manifest=descriptors)
    result = run_cat9b(adapter)
    assert result.by_kind["mcp_resource"] == {"success": 1, "fail": 1}
    assert result.by_kind["claude_code_hook"] == {"success": 1, "fail": 0}


# --- 9b: bool-returning probe is tolerated -----------------------------


def test_cat9b_probe_returning_bool_is_coerced():
    """Defensive: users may reasonably write `return True` instead of
    `return ProbeResult(success=True)`. The runner coerces and continues.
    """
    adapter = _StubAdapter(
        manifest=[
            HarnessDescriptor(
                name="naive_true",
                kind="tool_call",
                probe_fn=lambda: True,  # type: ignore[return-value]
            ),
            HarnessDescriptor(
                name="naive_false",
                kind="tool_call",
                probe_fn=lambda: False,  # type: ignore[return-value]
            ),
        ]
    )
    result = run_cat9b(adapter)
    assert result.successful_probes == 1
    assert result.failed_probes == 1
