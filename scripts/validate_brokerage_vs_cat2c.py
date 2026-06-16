#!/usr/bin/env python3
"""Validation experiment: does Burt brokerage predict cross-domain retrieval?

Per-question design (n = number of cat_2c multi-hop questions, ~10):

  x = Burt constraint along the reasoning PATH a question must traverse
      (mean and max over the entities named in `expected_sources`).
      Higher constraint = the path routes through a structurally fragile,
      low-redundancy region of the graph.
  y = whether the system actually answered the question (per-question
      recall, from a `retrieve` results JSON).

Hypothesis (the thing that would EARN the brokerage metric): questions whose
hop-path runs through high-constraint brokers are answered worse — a positive
correlation between path constraint and failure. If there's no relationship,
the brokerage metric is decoration and we should say so.

The x-side is computed from the good-dog corpus frontmatter alone (the graph
is declared in each note's `entities:` / `edges:` lists). The y-side needs a
retrieval run; pass it with --recall-json (a {question_id: recall_float} map,
or a `retrieve` results JSON with per-question entries). Without it, the
script prints the x-side ranking only.

Usage:
  python scripts/validate_brokerage_vs_cat2c.py
  python scripts/validate_brokerage_vs_cat2c.py --recall-json results/good_dog_B.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import networkx as nx
import yaml

CORPUS = Path(__file__).resolve().parents[1] / "sme/corpora/good-dog-corpus"
VAULT = CORPUS / "vault"
QUESTIONS = CORPUS / "questions.yaml"


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    try:
        return yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return None


def build_graph() -> tuple[nx.Graph, dict[str, str]]:
    """Build the undirected simple graph from note frontmatter.

    Returns (graph, entity_type_by_id). The graph is the substrate for
    nx.constraint — undirected, no parallel edges, no self loops, matching
    TopologyAnalyzer.brokerage's projection.
    """
    def flatten(items):
        """Some notes nest entities/edges one level deep (YAML list-of-lists)."""
        for it in items or []:
            if isinstance(it, list):
                yield from flatten(it)
            elif isinstance(it, dict):
                yield it

    G = nx.Graph()
    etype: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}  # id -> searchable strings
    for note in sorted(VAULT.rglob("*.md")):
        fm = parse_frontmatter(note.read_text())
        if not fm:
            continue
        for ent in flatten(fm.get("entities")):
            eid = ent.get("id")
            if eid:
                G.add_node(eid)
                etype[eid] = ent.get("type", "<none>")
                strings = [eid]
                if ent.get("canonical"):
                    strings.append(str(ent["canonical"]))
                strings.extend(str(a) for a in ent.get("aliases", []) or [])
                aliases[eid] = strings
        for edge in flatten(fm.get("edges")):
            src, dst = edge.get("from"), edge.get("to")
            if src and dst and src != dst:
                G.add_node(src)
                G.add_node(dst)
                G.add_edge(src, dst)
    G.graph["aliases"] = aliases
    return G, etype


def match_source(src: str, aliases: dict[str, list[str]]) -> str | None:
    """Map one expected_source to the single best-matching entity id, searching
    id + canonical + aliases. Prefers the shortest matching string (tightest
    match) to avoid a short token grabbing a long unrelated id."""
    s = src.lower().strip()
    best: tuple[int, str] | None = None
    for eid, strings in aliases.items():
        for cand in strings:
            c = cand.lower().replace("_", " ").replace("-", " ")
            if s in c or s in eid.lower():
                key = (len(cand), eid)
                if best is None or key < best:
                    best = key
    return best[1] if best else None


def waypoints(sources: list[str], aliases: dict[str, list[str]]) -> list[str]:
    """One ordered entity per expected_source (the reasoning chain), deduped."""
    out: list[str] = []
    for src in sources:
        m = match_source(src, aliases)
        if m and m not in out:
            out.append(m)
    return out


def reasoning_path_nodes(
    G: nx.Graph, wps: list[str]
) -> tuple[list[str], int]:
    """Intermediate nodes (the *brokers* a multi-hop answer traverses) on the
    shortest paths between consecutive waypoints. Excludes the waypoints
    themselves (they're the answer leaves). Returns (intermediates, n_segments
    with no connecting path — itself a fragility signal)."""
    inter: set[str] = set()
    disconnected = 0
    for a, b in zip(wps, wps[1:]):
        if a not in G or b not in G:
            continue
        try:
            sp = nx.shortest_path(G, a, b)
        except nx.NetworkXNoPath:
            disconnected += 1
            continue
        inter.update(sp[1:-1])  # drop endpoints
    inter.difference_update(wps)
    return list(inter), disconnected


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation, no scipy dependency. None if degenerate."""
    n = len(xs)
    if n < 3:
        return None

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1  # 1-based average rank for ties
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def load_recall(path: str) -> dict[str, float]:
    """Accept either {qid: recall} or a retrieve results JSON with per-question
    entries carrying an id and a recall/recall@k field."""
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and all(
        isinstance(v, (int, float)) for v in data.values()
    ):
        return {k: float(v) for k, v in data.items()}
    rows = data.get("questions") or data.get("results") or data
    out: dict[str, float] = {}
    for q in rows:
        qid = q.get("id") or q.get("question_id")
        rec = q.get("recall", q.get("recall@k", q.get("mean_recall")))
        if qid is not None and rec is not None:
            out[qid] = float(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--recall-json",
        help="per-question recall (y). {qid: recall} or a retrieve results JSON.",
    )
    ap.add_argument("--json", help="write the full result table to this path")
    args = ap.parse_args()

    G, etype = build_graph()
    qdoc = yaml.safe_load(QUESTIONS.read_text())
    cat2c = [q for q in qdoc["questions"] if q.get("sme_category") == "cat_2c"]

    recall = load_recall(args.recall_json) if args.recall_json else {}

    aliases = G.graph["aliases"]
    rows = []
    for q in cat2c:
        wps = waypoints(q.get("expected_sources", []), aliases)
        inter, disconnected = reasoning_path_nodes(G, wps)
        if inter:
            constraint = nx.constraint(G, nodes=inter)
            cvals = [
                constraint[n]
                for n in inter
                if constraint.get(n) is not None and constraint[n] == constraint[n]
            ]
        else:
            cvals = []
        rows.append(
            {
                "id": q["id"],
                "min_hops": q.get("min_hops"),
                "n_waypoints": len(wps),
                "n_brokers": len(inter),
                "disconnected_segments": disconnected,
                "path_constraint_mean": (sum(cvals) / len(cvals)) if cvals else None,
                "path_constraint_max": max(cvals) if cvals else None,
                "recall": recall.get(q["id"]),
            }
        )

    rows.sort(
        key=lambda r: (r["disconnected_segments"], r["path_constraint_mean"] or -1),
        reverse=True,
    )

    print(f"\nGraph: {G.number_of_nodes()} entities, {G.number_of_edges()} edges")
    print(f"cat_2c questions: {len(cat2c)}")
    print("x = Burt constraint over the broker nodes BETWEEN the answer "
          "waypoints (higher = more fragile reasoning path)\n")
    print(
        f"{'question':40s} {'hop':>3s} {'wp':>3s} {'brk':>3s} "
        f"{'disc':>4s} {'c_mean':>7s} {'c_max':>6s} {'recall':>7s}"
    )
    print("-" * 82)
    for r in rows:
        cm = f"{r['path_constraint_mean']:.3f}" if r["path_constraint_mean"] is not None else "  -  "
        cx = f"{r['path_constraint_max']:.3f}" if r["path_constraint_max"] is not None else "  -  "
        rc = f"{r['recall']:.2f}" if r["recall"] is not None else "   -"
        print(
            f"{r['id'][:40]:40s} {str(r['min_hops']):>3s} "
            f"{r['n_waypoints']:>3d} {r['n_brokers']:>3d} "
            f"{r['disconnected_segments']:>4d} {cm:>7s} {cx:>6s} {rc:>7s}"
        )

    paired = [(r["path_constraint_mean"], r["recall"]) for r in rows
              if r["path_constraint_mean"] is not None and r["recall"] is not None]
    if len(paired) >= 3:
        rho = spearman([p[0] for p in paired], [p[1] for p in paired])
        print(
            f"\nSpearman(path_constraint_mean, recall) = "
            f"{rho:.3f}  (n={len(paired)})"
        )
        print(
            "  Negative rho = fragile (high-constraint) paths retrieve worse "
            "→ brokerage predicts failure → the metric earns its place.\n"
            "  Near-zero rho = brokerage does not predict cross-domain recall."
        )
    else:
        print(
            "\n(no recall supplied — x-side only. Pass --recall-json to complete "
            "the correlation. This ranking is the fragility of each question's "
            "reasoning path in the real good-dog graph.)"
        )

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
