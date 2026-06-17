"""Category 7.b: Query latency distribution (YCSB methodology).

Captures wall-clock latency per adapter.query() call and computes
YCSB-standard percentile distribution: p50, p95, p99, p99.9, max.

By default percentiles are computed with numpy. When the [latency]
extra is installed (``pip install sme-eval[latency]``), an HdrHistogram
backs the collector instead. HdrHistogram is preferred at scale: it has
fixed per-sample memory regardless of N (numpy holds every sample), and
two histograms can be merged losslessly — letting percentiles from
separate runs combine without re-reading the raw samples.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

try:
    from hdrh.histogram import HdrHistogram

    _HAS_HDR = True
except ImportError:  # base install — np.percentile fallback
    HdrHistogram = None
    _HAS_HDR = False

# HdrHistogram records integers; latencies are sub-millisecond-sensitive,
# so we record microseconds (ms * 1000) over a 1 µs .. 1 hour range at
# 3 significant figures, then convert back to ms on readout.
_HDR_MIN_US = 1
_HDR_MAX_US = 3_600_000_000
_HDR_SIGFIGS = 3
_US_PER_MS = 1000.0


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
    """Collects wall-clock latencies and computes distribution.

    Uses an HdrHistogram when the [latency] extra is installed, else
    falls back to numpy percentiles over the recorded sample list.
    """

    def __init__(self, *, keep_raw: bool = True):
        self._latencies: list[float] = []
        self._keep_raw = keep_raw
        # The histogram is the percentile source when available. Raw
        # samples are still tracked when keep_raw is set (and always in
        # the numpy fallback, which has no other store).
        self._hist = (
            HdrHistogram(_HDR_MIN_US, _HDR_MAX_US, _HDR_SIGFIGS) if _HAS_HDR else None
        )

    def record(self, latency_ms: float) -> None:
        if self._hist is not None:
            # Clamp to the trackable range so out-of-band samples don't raise.
            us = int(round(latency_ms * _US_PER_MS))
            self._hist.record_value(min(max(us, _HDR_MIN_US), _HDR_MAX_US))
            if self._keep_raw:
                self._latencies.append(latency_ms)
        else:
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
        if self._hist is not None:
            return self._report_hdr()
        return self._report_numpy()

    def _report_numpy(self) -> LatencyReport:
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

    def _report_hdr(self) -> LatencyReport:
        h = self._hist
        if h.get_total_count() == 0:
            return LatencyReport()

        def pct(p: float) -> float:
            return h.get_value_at_percentile(p) / _US_PER_MS

        return LatencyReport(
            n=h.get_total_count(),
            p50_ms=pct(50),
            p95_ms=pct(95),
            p99_ms=pct(99),
            p99_9_ms=pct(99.9),
            max_ms=h.get_max_value() / _US_PER_MS,
            mean_ms=h.get_mean_value() / _US_PER_MS,
            min_ms=h.get_min_value() / _US_PER_MS,
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
