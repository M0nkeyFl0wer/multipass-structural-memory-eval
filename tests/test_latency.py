"""Tests for Cat 7.b latency measurement."""
import time
from sme.categories.latency import LatencyCollector, LatencyReport, format_latency_report


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
    assert r.p50_ms == 100.0
    assert r.max_ms == 100.0


def test_known_distribution():
    c = LatencyCollector()
    for i in range(1, 101):
        c.record(float(i))
    r = c.report()
    assert r.n == 100
    assert r.p50_ms == 50.5
    assert r.max_ms == 100.0
    assert r.min_ms == 1.0
    assert 49 < r.mean_ms < 51


def test_timed_call():
    c = LatencyCollector()
    def slow_fn(x):
        time.sleep(0.01)
        return x * 2
    result, latency = c.timed_call(slow_fn, 5)
    assert result == 10
    assert latency >= 10.0
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
