"""Category 7.b: Query latency distribution (YCSB methodology).

Captures wall-clock latency per adapter.query() call and computes
YCSB-standard percentile distribution: p50, p95, p99, p99.9, max.
Uses numpy for percentile calculations; optionally upgrades to
HdrHistogram when the [latency] extra is installed.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class LatencyReport:
    """Latency distribution for a batch of queries."""
    n: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    p99_9_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    min_ms: float = 0.0
    raw_ms: list[float] = field(default_factory=list)


class LatencyCollector:
    """Collects wall-clock latencies and computes distribution."""

    def __init__(self, *, keep_raw: bool = True):
        self._latencies: list[float] = []
        self._keep_raw = keep_raw

    def record(self, latency_ms: float) -> None:
        self._latencies.append(latency_ms)

    def timed_call(self, fn, *args, **kwargs):
        """Call fn(*args, **kwargs) and record the wall-clock latency.
        Returns (result, latency_ms)."""
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.record(elapsed_ms)
        return result, elapsed_ms

    def report(self) -> LatencyReport:
        if not self._latencies:
            return LatencyReport()
        arr = np.array(self._latencies)
        return LatencyReport(
            n=len(arr),
            p50_ms=float(np.percentile(arr, 50)),
            p95_ms=float(np.percentile(arr, 95)),
            p99_ms=float(np.percentile(arr, 99)),
            p99_9_ms=float(np.percentile(arr, 99.9)),
            max_ms=float(np.max(arr)),
            mean_ms=float(np.mean(arr)),
            min_ms=float(np.min(arr)),
            raw_ms=self._latencies.copy() if self._keep_raw else [],
        )

    def to_dict(self) -> dict:
        r = self.report()
        d = {
            "n": r.n,
            "p50_ms": round(r.p50_ms, 2),
            "p95_ms": round(r.p95_ms, 2),
            "p99_ms": round(r.p99_ms, 2),
            "p99_9_ms": round(r.p99_9_ms, 2),
            "max_ms": round(r.max_ms, 2),
            "mean_ms": round(r.mean_ms, 2),
            "min_ms": round(r.min_ms, 2),
        }
        d["raw_ms"] = [round(v, 2) for v in r.raw_ms] if self._keep_raw else []
        return d


def format_latency_report(report: LatencyReport) -> str:
    """Human-readable latency distribution."""
    if report.n == 0:
        return "  No latency data collected."
    lines = [
        "Cat 7.b — Query Latency Distribution",
        "═" * 40,
        "",
        f"  Queries measured:    {report.n}",
        f"  p50:                 {report.p50_ms:,.1f} ms",
        f"  p95:                 {report.p95_ms:,.1f} ms",
        f"  p99:                 {report.p99_ms:,.1f} ms",
        f"  p99.9:               {report.p99_9_ms:,.1f} ms",
        f"  max:                 {report.max_ms:,.1f} ms",
        f"  mean:                {report.mean_ms:,.1f} ms",
        f"  min:                 {report.min_ms:,.1f} ms",
    ]
    return "\n".join(lines)
