"""Tests for the operator-digest view of the nightly SME reading.

Each test builds the reading the nightly would leave on disk and asserts the
exact findings the digest would show. The ones that matter most are the
silent cases: a missing, stale or never-compared reading must each produce a
finding, never an "ok".
"""

from __future__ import annotations

import json
import os

from sme.cli import EXIT_REGRESSION, _check_against_baseline, main
from sme.digest_check import CHECK, digest_lines

READING = {
    "cat4": {"entities": 70_000, "edges": 26_000},
    "regression": {"baseline": "/x/sme-baseline.json", "status": "clean", "findings": []},
}


def _write(tmp_path, data, age_hours: float = 1.0):
    p = tmp_path / "sme.json"
    p.write_text(json.dumps(data))
    t = p.stat().st_mtime - age_hours * 3600
    os.utime(p, (t, t))
    return p


def _keys(lines):
    return [(line["severity"], line["key"]) for line in lines]


def test_clean_night_is_one_explicit_ok_line(tmp_path):
    lines = digest_lines(_write(tmp_path, READING))
    assert _keys(lines) == [("ok", "ok")]
    assert lines[0]["check"] == CHECK
    assert lines[0]["project"] == "hybrid-OG-vault-rag"


def test_missing_reading_is_a_finding_not_silence(tmp_path):
    assert _keys(digest_lines(tmp_path / "nope.json")) == [("act", "reading-missing")]


def test_unreadable_reading_is_a_finding(tmp_path):
    p = tmp_path / "sme.json"
    p.write_text("{not json")
    assert _keys(digest_lines(p)) == [("act", "reading-unreadable")]


def test_stale_reading_flags_a_stopped_nightly(tmp_path):
    # The 2026-06 blind spell: the file stayed, the timer stopped producing.
    lines = digest_lines(_write(tmp_path, READING, age_hours=60))
    assert ("act", "stale") in _keys(lines)
    assert ("ok", "ok") not in _keys(lines)


def test_reading_without_regression_block_means_the_alarm_is_unplugged(tmp_path):
    data = {"cat4": READING["cat4"]}  # what run_sme.sh wrote before 2026-11-13
    assert _keys(digest_lines(_write(tmp_path, data))) == [("watch", "no-baseline-compare")]


def test_each_regression_is_its_own_finding_with_a_stable_key(tmp_path):
    data = dict(READING, regression={
        "baseline": "/x/sme-baseline.json", "status": "regressed",
        "findings": [
            {"key": "edges", "what": "edges fell 20.0% (26000 -> 20800)"},
            {"key": "edge_type:PART_OF", "what": "edge type PART_OF disappeared (8600 -> 0)"},
        ],
    })
    lines = digest_lines(_write(tmp_path, data))
    assert _keys(lines) == [("act", "regression:edges"), ("act", "regression:edge_type:PART_OF")]
    # The accept command names both files, so the operator can act from the email.
    assert "cp " in lines[0]["action"] and "/x/sme-baseline.json" in lines[0]["action"]


def test_unreadable_baseline_and_first_night(tmp_path):
    bad = dict(READING, regression={"baseline": "/b", "status": "unreadable", "findings": []})
    first = dict(READING, regression={"baseline": "/b", "status": "no_baseline", "findings": []})
    assert _keys(digest_lines(_write(tmp_path, bad))) == [("act", "baseline-unreadable")]
    assert _keys(digest_lines(_write(tmp_path, first))) == [("watch", "no-baseline-yet")]


def test_cli_prints_json_lines_and_exits_zero(tmp_path, capsys):
    # Exit 0 even with findings: to the digest a non-zero exit means "check
    # could not run", which would turn a real finding into an ERROR line.
    assert main(["digest-check", "--reading", str(tmp_path / "nope.json")]) == 0
    out = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [x["key"] for x in out] == ["reading-missing"]


# --- the verdict travels inside the reading -----------------------------

def test_baseline_verdict_block_regressed(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"cat4": {"edges": 28_000}}))
    rc, block = _check_against_baseline({"cat4": {"edges": 20_000}}, str(base), True)
    assert rc == EXIT_REGRESSION
    assert block["status"] == "regressed"
    assert [f["key"] for f in block["findings"]] == ["edges"]


def test_baseline_verdict_block_missing_and_clean(tmp_path):
    rc, block = _check_against_baseline({}, str(tmp_path / "none.json"), True)
    assert (rc, block["status"]) == (0, "no_baseline")
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"cat4": {"edges": 28_000}}))
    rc, block = _check_against_baseline({"cat4": {"edges": 28_000}}, str(base), True)
    assert (rc, block["status"], block["findings"]) == (0, "clean", [])
