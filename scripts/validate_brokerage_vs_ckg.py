#!/usr/bin/env python3
"""Validation: does Burt brokerage predict multi-hop retrieval on CKG-benchmark?

This is the brokerage-validation experiment on a substrate that actually has
broker-mediated multi-hop structure (good-dog was too small — only 3/10
multi-hop questions traversed any broker). CKG-benchmark gives us, for free:

  - a real prerequisite DAG per domain (learning-graph.csv: ConceptID +
    DEPENDS_ON edges),
  - T3_path queries with EXPLICIT `path_ids` (the exact reasoning chain — no
    fuzzy matching),
  - per-question recall already computed in condition_B.json (the y-side).

Per-question design, pooled across all 5 domains (n ≈ 125 T3_path queries):

  x = Burt constraint over the BROKER nodes on a query's path (the
      intermediate concepts, path_ids[1:-1] — not the endpoints).
  y = condition-B recall for that query.

CONFOUND we report explicitly: condition B retrieves a k-hop neighbourhood
(hop_budget=2), so T3_path queries with hop_depth>2 under-retrieve BY DESIGN.
hop_depth therefore drives recall on its own. We print the full correlation
matrix (constraint↔recall, hop_depth↔recall, constraint↔hop_depth) so a
spurious constraint↔recall signal that's really just hop_depth is visible.

Usage:
  python scripts/validate_brokerage_vs_ckg.py
  python scripts/validate_brokerage_vs_ckg.py --type T3_path --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
DOMAINS_DIR = ROOT / "data/ckg_benchmark/domains"
QUERIES_DIR = ROOT / "data/ckg_benchmark/queries"
RESULTS_DIR = ROOT / "results/ckg_benchmark"


def build_graph(domain: str) -> nx.Graph:
    """Undirected simple graph from learning-graph.csv (DEPENDS_ON edges)."""
    G = nx.Graph()
    csv_path = DOMAINS_DIR / domain / "learning-graph.csv"
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            cid = row["ConceptID"].strip()
            G.add_node(cid)
            deps = (row.get("Dependencies") or "").strip()
            for dep in deps.split(","):
                dep = dep.strip()
                if dep and dep != cid:
                    G.add_node(dep)
                    G.add_edge(cid, dep)
    return G


def load_queries(domain: str) -> list[dict]:
    path = QUERIES_DIR / f"queries_{domain}.jsonl"
    return [json.loads(line) for line in path.open() if line.strip()]


def load_recall(domain: str) -> dict[str, float]:
    path = RESULTS_DIR / domain / "condition_B.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out = {}
    for q in data.get("questions", []):
        if q.get("recall") is not None:
            out[q["id"]] = float(q["recall"])
    return out


def broker_nodes(q: dict) -> list[str]:
    """Intermediate concepts on a query's path (the brokers), as str ids."""
    pids = q.get("path_ids")
    if pids and len(pids) >= 3:
        return [str(p) for p in pids[1:-1]]
    # T5_cross_concept: two endpoints, brokers = shortest-path interior
    if q.get("type") == "T5_cross_concept":
        return []  # resolved against the graph in collect()
    return []


def spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return num / (dx * dy) if dx and dy else None


def collect(qtype: str) -> list[dict]:
    """One row per qualifying query across all domains, with x and y."""
    rows = []
    for qdir in sorted(p.name for p in QUERIES_DIR.glob("queries_*.jsonl")):
        domain = qdir[len("queries_"):-len(".jsonl")]
        G = build_graph(domain)
        recall = load_recall(domain)
        if not recall:
            continue
        constraint_cache: dict[str, float] = {}
        for q in load_queries(domain):
            if qtype != "all" and q.get("type") != qtype:
                continue
            if q["id"] not in recall:
                continue
            brokers = broker_nodes(q)
            brokers = [b for b in brokers if b in G]
            if not brokers:
                continue
            need = [b for b in brokers if b not in constraint_cache]
            if need:
                constraint_cache.update(nx.constraint(G, nodes=need))
            cvals = [
                constraint_cache[b]
                for b in brokers
                if constraint_cache.get(b) is not None
                and constraint_cache[b] == constraint_cache[b]
            ]
            if not cvals:
                continue
            rows.append(
                {
                    "id": q["id"],
                    "domain": domain,
                    "hop_depth": q.get("hop_depth", 0),
                    "n_brokers": len(brokers),
                    "x_constraint_mean": sum(cvals) / len(cvals),
                    "x_constraint_max": max(cvals),
                    "y_recall": recall[q["id"]],
                }
            )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", default="T3_path",
                    help="query type to test (default T3_path; 'all' to pool)")
    ap.add_argument("--json", help="write per-query rows to this path")
    args = ap.parse_args()

    rows = collect(args.type)
    print(f"\nBrokerage validation on CKG-benchmark — query type: {args.type}")
    print(f"pooled across domains, n = {len(rows)} queries with broker nodes\n")
    if not rows:
        print("no qualifying queries (need path_ids + recall + in-graph brokers).")
        return 0

    xs_mean = [r["x_constraint_mean"] for r in rows]
    xs_max = [r["x_constraint_max"] for r in rows]
    ys = [r["y_recall"] for r in rows]
    hops = [float(r["hop_depth"]) for r in rows]

    print("Spearman correlations (n={}):".format(len(rows)))
    print(f"  constraint_mean ↔ recall : {spearman(xs_mean, ys):+.3f}")
    print(f"  constraint_max  ↔ recall : {spearman(xs_max, ys):+.3f}")
    print(f"  hop_depth       ↔ recall : {spearman(hops, ys):+.3f}   "
          "(the known confound)")
    print(f"  constraint_mean ↔ hop    : {spearman(xs_mean, hops):+.3f}   "
          "(is constraint just a proxy for hop_depth?)")

    # Within-hop_depth check: hold hop_depth fixed, does constraint still move
    # recall? Report per-hop where n>=5.
    from collections import defaultdict
    by_hop: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_hop[r["hop_depth"]].append(r)
    print("\nWithin fixed hop_depth (controls the confound):")
    for hop in sorted(by_hop):
        grp = by_hop[hop]
        if len(grp) >= 5:
            rho = spearman([g["x_constraint_mean"] for g in grp],
                           [g["y_recall"] for g in grp])
            mr = sum(g["y_recall"] for g in grp) / len(grp)
            rstr = f"{rho:+.3f}" if rho is not None else "  n/a"
            print(f"  hop={hop}  n={len(grp):3d}  "
                  f"constraint↔recall {rstr}  (mean recall {mr:.2f})")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2))
        print(f"\nwrote {args.json}")

    print("\nReading: a NEGATIVE constraint↔recall that SURVIVES within fixed "
          "hop_depth = fragile-path queries retrieve worse independent of "
          "length → brokerage earns its place. If it vanishes once hop_depth "
          "is held fixed, brokerage was just a hop-length proxy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
