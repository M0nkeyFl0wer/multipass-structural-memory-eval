"""End-to-end `sme-eval check` on the good-dog corpus (no graph backend).

Until 2026-11-13 nothing ran `check` as a whole; only its parts were
tested. This drives the real command the nightly runs: reading, Cat 8
against a declared ontology, baseline comparison, exit code, history.
"""

from __future__ import annotations

import json
from pathlib import Path

from sme.cli import EXIT_REGRESSION, main

CORPUS = Path(__file__).resolve().parents[1] / "sme" / "corpora" / "good-dog-corpus"


def _check(tmp_path, *extra):
    out = tmp_path / "sme.json"
    rc = main([
        "check", "--adapter", "corpus", "--db", str(CORPUS / "vault"),
        "--no-homology", "--json", str(out),
        "--implied-ontology", str(CORPUS / "ontology.yaml"),
        "--history", str(tmp_path / "history.jsonl"), *extra,
    ])
    return rc, json.loads(out.read_text())


def test_check_writes_a_full_reading(tmp_path):
    rc, r = _check(tmp_path)
    assert rc == 0
    assert r["cat4"]["entities"] > 0 and r["cat4"]["edges"] > 0
    assert r["cat4"]["entity_type_counts"] and "isolated_by_type" in r["cat5"]
    assert r["cat8"]["ontology"].endswith("ontology.yaml")
    assert "regression" not in r  # no --baseline given
    assert len((tmp_path / "history.jsonl").read_text().splitlines()) == 1


def test_same_graph_against_itself_is_clean(tmp_path):
    _, first = _check(tmp_path)
    base = tmp_path / "base.json"
    base.write_text(json.dumps(first))
    rc, r = _check(tmp_path, "--baseline", str(base), "--fail-on-regression")
    assert (rc, r["regression"]["status"]) == (0, "clean")


def test_lost_edges_fail_the_run_and_are_recorded(tmp_path):
    _, first = _check(tmp_path)
    # Pretend the baseline had twice the edges: today looks like a 50% loss.
    first["cat4"]["edges"] *= 2
    base = tmp_path / "base.json"
    base.write_text(json.dumps(first))
    rc, r = _check(tmp_path, "--baseline", str(base), "--fail-on-regression")
    assert rc == EXIT_REGRESSION
    assert [f["key"] for f in r["regression"]["findings"]] == ["edges"]
