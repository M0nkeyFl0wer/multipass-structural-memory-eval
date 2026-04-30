"""Category 9: Harness Integration — The Handshake.

Tests whether the memory system is actually reachable through its
declared invocation surfaces (MCP servers, Claude Code hooks, tool
calls, slash commands, custom actions). Every other SME category
measures offline retrieval — this category measures the layer between
retrieval and a running model.

Current scope (minimum viable):

  9b  Call-through success
      For each ``HarnessDescriptor`` returned by the adapter, invoke
      ``probe_fn`` once and report whether the call completed. A low
      9b means the integration is broken (bad schema, timeout, wrong
      parameters, tool not registered, MCP server unreachable). A high
      9b means the surface is live — it says nothing about whether the
      model will actually invoke it, which is what 9a measures and
      needs a real model runtime.

Planned (not implemented here; see spec v8 § Category 9):

  9a  Invocation rate       — needs real model API
  9c  Result usage          — needs real model API + Cat 1 matcher
  9d  Negative-control rate — needs real model API + held-out set
  9e  Per-model sensitivity — needs multi-model API access
  9f  Per-harness portability — needs per-harness runners
  9g  Hook-driven access    — needs per-harness shims (Claude Code,
                               Cursor, LangGraph, etc.)

9b being implemented first is deliberate: per the spec, it's the one
sub-test that "can be measured against a mock model that always invokes
the tool." No API keys, no cost, no per-harness shim. A clean floor.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from sme.adapters.base import HarnessDescriptor, ProbeResult, SMEAdapter

log = logging.getLogger(__name__)


# --- Bands for the Reading section ------------------------------------

_CALL_THROUGH_HEALTHY = 1.00   # all surfaces callable
_CALL_THROUGH_WARN = 0.80      # 80-99% — partial integration


def _band(value: float, healthy: float, warn: float) -> str:
    if value >= healthy:
        return "healthy"
    if value >= warn:
        return "warn"
    return "concerning"


# --- Result types -----------------------------------------------------


@dataclass
class ProbeReading:
    """One descriptor's probe outcome with SME-side wrapping."""

    descriptor: HarnessDescriptor
    result: ProbeResult


@dataclass
class Cat9bResult:
    """Category 9b — call-through success — scorecard."""

    total_probes: int
    successful_probes: int
    failed_probes: int
    # Probes grouped by HarnessDescriptor.kind for per-surface breakdown.
    by_kind: dict[str, dict[str, int]] = field(default_factory=dict)
    readings: list[ProbeReading] = field(default_factory=list)
    # Present when the adapter declares no manifest — distinct from zero
    # probes succeeding (which is a real failure).
    empty_manifest: bool = False

    @property
    def call_through_rate(self) -> float:
        if self.total_probes == 0:
            return 0.0
        return self.successful_probes / self.total_probes

    @property
    def band(self) -> str:
        if self.empty_manifest:
            return "n/a"
        return _band(self.call_through_rate, _CALL_THROUGH_HEALTHY, _CALL_THROUGH_WARN)


# --- Sub-test: 9b call-through success --------------------------------


def run_cat9b(adapter: SMEAdapter, *, timeout_per_probe_s: float = 10.0) -> Cat9bResult:
    """Execute Category 9b against an adapter's declared harness manifest.

    Invokes each ``HarnessDescriptor.probe_fn`` exactly once and tallies
    successes. A probe that raises an exception counts as a failure with
    the exception message captured in ``ProbeResult.error``. A probe
    that exceeds ``timeout_per_probe_s`` is not automatically aborted —
    the probe_fn owns its own timeout semantics — but the elapsed
    wall-clock is recorded in ``ProbeResult.latency_ms``.

    Consumers of this function (the CLI, a CI harness, a test) should
    treat an empty manifest as "the adapter doesn't declare a harness
    surface" — a reporting outcome, not a pass/fail.
    """
    manifest = adapter.get_harness_manifest()

    if not manifest:
        return Cat9bResult(
            total_probes=0,
            successful_probes=0,
            failed_probes=0,
            empty_manifest=True,
        )

    readings: list[ProbeReading] = []
    by_kind: dict[str, dict[str, int]] = {}
    successful = 0
    failed = 0

    for descriptor in manifest:
        start = time.perf_counter()
        try:
            result = descriptor.probe_fn()
            if not isinstance(result, ProbeResult):
                # Tolerate the common mistake of returning a bool.
                result = ProbeResult(
                    success=bool(result),
                    latency_ms=(time.perf_counter() - start) * 1000,
                    error=None if result else "probe_fn returned non-ProbeResult falsy value",
                )
            # Fill latency if the probe forgot to.
            if result.latency_ms == 0.0:
                result.latency_ms = (time.perf_counter() - start) * 1000
        except Exception as exc:  # noqa: BLE001 — intentional; probe_fn is user code
            latency = (time.perf_counter() - start) * 1000
            log.debug("probe %r raised %s", descriptor.name, exc)
            result = ProbeResult(
                success=False,
                latency_ms=latency,
                error=f"{type(exc).__name__}: {exc}",
            )

        readings.append(ProbeReading(descriptor=descriptor, result=result))

        kind_bucket = by_kind.setdefault(descriptor.kind, {"success": 0, "fail": 0})
        if result.success:
            successful += 1
            kind_bucket["success"] += 1
        else:
            failed += 1
            kind_bucket["fail"] += 1

    return Cat9bResult(
        total_probes=len(manifest),
        successful_probes=successful,
        failed_probes=failed,
        by_kind=by_kind,
        readings=readings,
        empty_manifest=False,
    )


# --- Formatting helpers (used by the CLI) -----------------------------


def format_cat9b_report(result: Cat9bResult, *, source_label: str = "") -> str:
    """Return a human-readable scorecard for Category 9b.

    Follows the same banded-reading shape as ``cat4`` / ``cat5`` so the
    CLI output stays consistent. Probe-level detail is included so a
    failing call-through rate is actionable.
    """
    lines: list[str] = []

    header = "Category 9b — Harness Integration (Call-Through Success)"
    if source_label:
        header = f"{header} — {source_label}"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    if result.empty_manifest:
        lines.append(
            "  Adapter declared no harness manifest — pure library usage only. "
            "Cat 9b does not apply."
        )
        lines.append("")
        lines.append(
            "  If this memory system is reachable via MCP, hooks, tool calls, or "
            "slash commands, implement ``get_harness_manifest()`` so SME can probe "
            "each surface."
        )
        return "\n".join(lines) + "\n"

    rate_pct = result.call_through_rate * 100
    lines.append(
        f"  Probes: {result.total_probes} total — "
        f"{result.successful_probes} succeeded, "
        f"{result.failed_probes} failed "
        f"({rate_pct:.1f}% call-through, band: {result.band})"
    )
    lines.append("")

    if result.by_kind:
        lines.append("  By surface kind:")
        for kind, counts in sorted(result.by_kind.items()):
            total = counts["success"] + counts["fail"]
            success = counts["success"]
            pct = (success / total * 100) if total else 0.0
            lines.append(f"    {kind:22} {success}/{total} ({pct:.0f}%)")
        lines.append("")

    if result.failed_probes:
        lines.append("  Failed probes:")
        for reading in result.readings:
            if reading.result.success:
                continue
            error = reading.result.error or "(no error captured)"
            lines.append(
                f"    - {reading.descriptor.kind}/{reading.descriptor.name}: {error}"
            )
        lines.append("")

    lines.append("  Reading:")
    if result.band == "healthy":
        lines.append(
            "    All declared surfaces answered. The memory system is live at every "
            "harness point it claims to support."
        )
    elif result.band == "warn":
        lines.append(
            "    Some surfaces are unreachable. Likely integration regressions rather "
            "than retrieval problems — inspect the failed probes above."
        )
    else:
        lines.append(
            "    Most surfaces failed to respond. The memory system is effectively "
            "unavailable to callers using the declared harness contract. Cat 9a "
            "(invocation rate) readings downstream of this will be artificially low."
        )
    lines.append("")

    lines.append(
        "  Note: 9b measures whether a mock-invoker can reach each surface. It does "
        "NOT measure whether a real model would actually invoke the tool (9a), use "
        "the result (9c), or skip when unnecessary (9d). Those sub-tests require a "
        "real model runtime and are tracked separately."
    )
    return "\n".join(lines) + "\n"
