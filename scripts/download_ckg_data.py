#!/usr/bin/env python3
"""Download selected domains from danyarm/ckg-benchmark.

Pulls the 5 shortlisted domains' learning-graph.csv plus their
queries_{domain}.jsonl into data/ckg_benchmark/. Idempotent — skips
files that already exist with non-zero size. The dataset directory
is gitignored.

The shortlist and shape rationale live in
docs/ckg_benchmark_experiment.md. To experiment with another domain
add it to DOMAINS below.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

REPO = "danyarm/ckg-benchmark"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main"

DOMAINS = [
    "calculus",
    "us-geography",
    "moss",
    "glp1-obesity",
    "theory-of-knowledge",
]

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "ckg_benchmark"


def fetch(url: str, dest: Path) -> tuple[bool, int]:
    if dest.exists() and dest.stat().st_size > 0:
        return False, dest.stat().st_size
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "sme-ckg-experiment/1"})
    with urllib.request.urlopen(req) as r:
        body = r.read()
    if not body:
        raise RuntimeError(f"empty body from {url}")
    dest.write_bytes(body)
    return True, len(body)


def main() -> int:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    fetched, skipped = 0, 0
    for d in DOMAINS:
        csv_url = f"{BASE}/domains/{d}/learning-graph.csv"
        csv_dest = DATA_ROOT / "domains" / d / "learning-graph.csv"
        q_url = f"{BASE}/queries/queries_{d}.jsonl"
        q_dest = DATA_ROOT / "queries" / f"queries_{d}.jsonl"
        for url, dest in ((csv_url, csv_dest), (q_url, q_dest)):
            new, size = fetch(url, dest)
            tag = "FETCH" if new else "skip "
            print(f"  {tag}  {dest.relative_to(DATA_ROOT)}  ({size} bytes)")
            if new:
                fetched += 1
            else:
                skipped += 1
    print(f"\ndone — {fetched} fetched, {skipped} already present, root={DATA_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
