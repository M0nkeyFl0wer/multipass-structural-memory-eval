"""Tests for Cat 7.b latency measurement."""
import pytest

from sme.categories import latency as latency_mod
from sme.categories.latency import LatencyCollector, LatencyReport, format_latency_report

# HdrHistogram quantizes values to its configured precision (3 sig figs)
# and resolves percentiles by bucket rank rather than numpy's linear
# interpolation. So exact percentile values only hold on the numpy
# fallback; on the HDR path we assert quantization-tolerant bounds.
_HDR = latency_mod._HAS_HDR
# Looser than 3-sig-fig precision to also absorb percentile-rank vs
# interpolation divergence on small samples.
_HDR_REL = 0.02


def test_empty_collector():
    c = LatencyCollector()
    r = c.report()
    assert r.n == 0
    assert r.p50_ms == 0.0


def test_single_recording():
    c = LatencyCollector()
    c.record(100.0)
    r = c.report()
    assert r.n == 1
    assert r.p50_ms == (pytest.approx(100.0, rel=_HDR_REL) if _HDR else 100.0)
    assert r.max_ms == (pytest.approx(100.0, rel=_HDR_REL) if _HDR else 100.0)


def test_known_distribution():
    c = LatencyCollector()
    for i in range(1, 101):
        c.record(float(i))
    r = c.report()
    assert r.n == 100
    assert r.p50_ms == (pytest.approx(50.5, rel=_HDR_REL) if _HDR else 50.5)
    assert r.max_ms == (pytest.approx(100.0, rel=_HDR_REL) if _HDR else 100.0)
    assert r.min_ms == (pytest.approx(1.0, rel=_HDR_REL) if _HDR else 1.0)
    assert 49 < r.mean_ms < 51


def test_timed_call(monkeypatch):
    # Deterministic clock: perf_counter returns these in sequence, so the
    # measured elapsed time is exactly 0.0125 s -> 12.5 ms, no real sleep.
    ticks = iter([1.0, 1.0125])
    monkeypatch.setattr(latency_mod.time, "perf_counter", lambda: next(ticks))

    c = LatencyCollector()
    result, latency = c.timed_call(lambda x: x * 2, 5)
    assert result == 10
    assert latency == pytest.approx(12.5)
    assert c.report().n == 1


def test_to_dict():
    c = LatencyCollector()
    c.record(50.0)
    c.record(100.0)
    d = c.to_dict()
    assert d["n"] == 2
    assert "p50_ms" in d
    assert "p95_ms" in d
    assert "raw_ms" in d


def test_to_dict_no_raw():
    c = LatencyCollector(keep_raw=False)
    c.record(50.0)
    d = c.to_dict()
    assert d["raw_ms"] == []


def test_format_report():
    c = LatencyCollector()
    for i in range(1, 51):
        c.record(float(i))
    text = format_latency_report(c.report())
    assert "Cat 7.b" in text
    assert "p50:" in text
    assert "p99:" in text


def test_format_empty():
    text = format_latency_report(LatencyReport())
    assert "No latency data" in text


@pytest.mark.skipif(not _HDR, reason="requires the [latency] extra (hdrhistogram)")
def test_hdr_backend_active():
    # When the extra is installed the collector is histogram-backed.
    c = LatencyCollector()
    assert c._hist is not None


@pytest.mark.skipif(not _HDR, reason="requires the [latency] extra (hdrhistogram)")
def test_hdr_merge_preserves_percentiles():
    # The reason to wire HdrHistogram: two runs' histograms merge
    # losslessly, so combined percentiles match a single combined run.
    combined = LatencyCollector()
    a = LatencyCollector()
    b = LatencyCollector()
    for i in range(1, 51):
        combined.record(float(i))
        a.record(float(i))
    for i in range(51, 101):
        combined.record(float(i))
        b.record(float(i))

    a._hist.add(b._hist)
    merged = a.report()
    expected = combined.report()
    assert merged.n == expected.n == 100
    assert merged.p50_ms == pytest.approx(expected.p50_ms, rel=_HDR_REL)
    assert merged.p99_ms == pytest.approx(expected.p99_ms, rel=_HDR_REL)
