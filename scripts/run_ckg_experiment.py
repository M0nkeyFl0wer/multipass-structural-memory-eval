#!/usr/bin/env python3
"""Run the CKG-benchmark A/B/C experiment.

For each shortlisted domain (see docs/ckg_benchmark_experiment.md):

  - Load the CKG via CKGAdapter
  - For every query in queries_{domain}.jsonl, run all three conditions:
      A — flat token-overlap retrieval (CKGAdapter.get_flat_retrieval)
      B — k-hop structured retrieval (CKGAdapter.query)
      C — same node set as B but prose-only, no edges
        (CKGAdapter.condition_c_serialization on B's retrieved entities)
  - Score each by substring-match recall against ground_truth, count
    tokens via tiktoken cl100k_base (or char/4 fallback), record per-
    query results
  - Emit results/ckg_benchmark/{domain}/condition_{A,B,C}.json in the
    shape sme.categories.multi_hop expects (questions list with
    min_hops/recall/hit/tokens), plus a runs.jsonl combined trace
  - Run sme.categories.multi_hop.score_cat2c() to compute per-hop
    B-A and B-C deltas; write summary.md

The CKG `hop_depth` field maps directly onto SME's `min_hops`. Query
`type` (T1_entity, T2_dependency, T3_path, T4_aggregate, T5_cross_concept)
is preserved in the per-query rows so you can re-bucket later.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sme.adapters.ckg import CKGAdapter  # noqa: E402
from sme.categories.multi_hop import score_cat2c  # noqa: E402

DOMAINS = [
    "calculus",
    "us-geography",
    "moss",
    "glp1-obesity",
    "theory-of-knowledge",
]

DATA_ROOT = _REPO_ROOT / "data" / "ckg_benchmark"
RESULTS_ROOT = _REPO_ROOT / "results" / "ckg_benchmark"


# --- token counting (mirror sme/cli.py) ----------------------------

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text)) if text else 0

    _TOKENIZER = "tiktoken-cl100k_base"
except Exception:  # pragma: no cover

    def count_tokens(text: str) -> int:
        return len(text) // 4 if text else 0

    _TOKENIZER = "char-div-4-fallback"


# --- scoring -------------------------------------------------------


def score_recall(context: str, ground_truth: list[str]) -> tuple[float, bool]:
    """SME-style substring recall: fraction of ground_truth strings
    present in the context. `hit` is True if any single ground_truth
    string appears (parallels SME's existing scorer)."""
    if not context or not ground_truth:
        return 0.0, False
    ctx_lower = context.lower()
    n_hit = sum(1 for g in ground_truth if g and g.lower() in ctx_lower)
    return n_hit / len(ground_truth), n_hit > 0


# --- per-domain run -----------------------------------------------


@dataclass
class DomainRun:
    domain: str
    n_queries: int = 0
    rows: list[dict] = field(default_factory=list)  # combined trace
    by_condition: dict[str, list[dict]] = field(
        default_factory=lambda: {"A": [], "B": [], "C": [], "B2": []}
    )
    no_match_count: int = 0


def run_domain(domain: str, *, max_queries: int | None = None, include_b2: bool = False) -> DomainRun:
    csv_path = DATA_ROOT / "domains" / domain / "learning-graph.csv"
    queries_path = DATA_ROOT / "queries" / f"queries_{domain}.jsonl"
    if not csv_path.exists() or not queries_path.exists():
        raise FileNotFoundError(
            f"missing data for {domain}: run scripts/download_ckg_data.py first"
        )

    adapter = CKGAdapter(csv_path)
    ingest = adapter.ingest_corpus([])
    if ingest["errors"]:
        print(
            f"  WARN  {domain}: {len(ingest['errors'])} ingest errors (will not block run)",
            file=sys.stderr,
        )

    out = DomainRun(domain=domain)
    with open(queries_path) as f:
        for i, line in enumerate(f):
            if max_queries is not None and i >= max_queries:
                break
            q = json.loads(line)
            row = run_one(adapter, q, include_b2=include_b2)
            out.rows.append(row)
            for cond in ("A", "B", "C"):
                out.by_condition[cond].append(row[cond])
            if include_b2 and "B2" in row:
                out.by_condition["B2"].append(row["B2"])
            out.n_queries += 1
            if row["B"]["error"] == "NO_MATCH":
                out.no_match_count += 1
    return out


def run_one(adapter: CKGAdapter, q: dict, include_b2: bool = False) -> dict[str, Any]:
    question = q["query"]
    gt = list(q.get("ground_truth", []))
    hop = int(q.get("hop_depth", 0))
    qid = q["id"]
    qtype = q.get("type", "")

    res_a = adapter.get_flat_retrieval(question)
    res_b = adapter.query(question)

    res_b2 = None
    if include_b2:
        res_b2 = adapter.query_hierarchical(question)

    c_context = ""
    if res_b.error is None:
        c_context = adapter.condition_c_serialization(res_b.retrieved_entities)

    a_recall, a_hit = score_recall(res_a.context_string, gt)
    b_recall, b_hit = score_recall(res_b.context_string, gt)
    c_recall, c_hit = score_recall(c_context, gt)

    def cond_row(cond: str, ctx: str, rec: float, hit: bool, err: str | None) -> dict:
        return {
            "id": qid,
            "type": qtype,
            "min_hops": hop,
            "hop_depth": hop,
            "recall": rec,
            "hit": hit,
            "tokens": count_tokens(ctx),
            "condition": cond,
            "error": err,
        }

    result = {
        "id": qid,
        "type": qtype,
        "hop_depth": hop,
        "ground_truth": gt,
        "A": cond_row("A", res_a.context_string, a_recall, a_hit, res_a.error),
        "B": cond_row("B", res_b.context_string, b_recall, b_hit, res_b.error),
        "C": cond_row("C", c_context, c_recall, c_hit, res_b.error),
    }

    if res_b2 is not None:
        b2_recall, b2_hit = score_recall(res_b2.context_string, gt)
        result["B2"] = cond_row("B2", res_b2.context_string, b2_recall, b2_hit, res_b2.error)

    return result


# --- output writers -----------------------------------------------


def write_outputs(run: DomainRun) -> dict[str, Path]:
    out_dir = RESULTS_ROOT / run.domain
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    conds = list(run.by_condition.keys())
    for cond in conds:
        path = out_dir / f"condition_{cond}.json"
        path.write_text(
            json.dumps(
                {
                    "domain": run.domain,
                    "condition": cond,
                    "tokenizer": _TOKENIZER,
                    "questions": run.by_condition[cond],
                },
                indent=2,
            )
        )
        paths[cond] = path

    trace_path = out_dir / "runs.jsonl"
    with open(trace_path, "w") as f:
        for row in run.rows:
            f.write(json.dumps(row) + "\n")
    paths["trace"] = trace_path

    return paths


def write_summary(run: DomainRun, paths: dict[str, Path]) -> Path:
    report = score_cat2c(
        flat_json=paths["A"],
        graph_json=paths["B"],
        no_structure_json=paths["C"],
        flat_label="A: flat token-overlap",
        graph_label="B: 2-hop structured",
        no_structure_label="C: same-nodes prose",
    )
    out_dir = RESULTS_ROOT / run.domain
    summary_path = out_dir / "summary.md"

    A = report.conditions.get("A")
    B = report.conditions["B"]
    C = report.conditions.get("C")

    has_b2 = "B2" in paths and "B2" in run.by_condition

    def _load_questions(json_path: Path) -> list[dict]:
        with open(json_path) as f:
            return json.load(f)["questions"]

    def _cond_stats(questions: list[dict], label: str):
        n = len(questions)
        recalls = [q["recall"] for q in questions]
        tokens_list = [q["tokens"] for q in questions]
        hits = sum(1 for q in questions if q.get("hit"))
        correct_tokens = [q["tokens"] for q in questions if q.get("hit")]
        return type("Cond", (), {
            "label": label,
            "mean_recall": sum(recalls) / n if n else 0,
            "full_recall": hits,
            "total_questions": n,
            "mean_tokens": sum(tokens_list) / n if n else 0,
            "tokens_per_correct": sum(correct_tokens) / len(correct_tokens) if correct_tokens else None,
            "by_hop": _by_hop(questions),
        })()

    def _by_hop(questions: list[dict]) -> dict:
        h: dict[int, dict] = {}
        for q in questions:
            h_val = int(q.get("hop_depth", 0))
            if h_val not in h:
                h[h_val] = {"n": 0, "recalls": [], "tokens": []}
            h[h_val]["n"] += 1
            h[h_val]["recalls"].append(q["recall"])
            h[h_val]["tokens"].append(q["tokens"])
        for k, v in h.items():
            v["mean_recall"] = sum(v["recalls"]) / len(v["recalls"])
            v["mean_tokens"] = sum(v["tokens"]) / len(v["tokens"])
        return h

    B2_stats = _cond_stats(_load_questions(paths["B2"]), "B2: hierarchical") if has_b2 else None

    lines: list[str] = []
    lines.append(f"# CKG-benchmark — {run.domain}")
    lines.append("")
    lines.append(f"- queries run: **{run.n_queries}**")
    lines.append(f"- target-match failures (B): **{run.no_match_count}**")
    lines.append(f"- tokenizer: `{_TOKENIZER}`")
    lines.append("")
    lines.append("## Condition totals")
    lines.append("")
    lines.append("| Cond | label | mean recall | full-recall | mean tokens | tokens/correct |")
    lines.append("|------|-------|-------------|-------------|-------------|----------------|")
    for cond_name, cond in [("A", A), ("B", B), ("C", C), ("B2", B2_stats)]:
        if cond is None:
            continue
        tpc = "—" if cond.tokens_per_correct is None else f"{cond.tokens_per_correct:.0f}"
        lines.append(
            f"| {cond_name} | {cond.label} | {cond.mean_recall:.3f} | "
            f"{cond.full_recall}/{cond.total_questions} | "
            f"{cond.mean_tokens:.0f} | {tpc} |"
        )
    lines.append("")

    if report.delta_B_minus_A:
        lines.append("## B − A by hop_depth (recall pp, tokens)")
        lines.append("")
        lines.append("| hop | n | A recall | B recall | Δrecall (pp) | A tokens | B tokens | Δtokens |")
        lines.append("|-----|---|----------|----------|--------------|----------|----------|---------|")
        for h in sorted(report.delta_B_minus_A.keys()):
            d = report.delta_B_minus_A[h]
            ah = A.by_hop[h] if A else None
            bh = B.by_hop[h]
            lines.append(
                f"| {h} | {bh.n} | "
                f"{ah.mean_recall:.3f} | {bh.mean_recall:.3f} | "
                f"{d['recall_delta_pp']:+.1f} | "
                f"{ah.mean_tokens:.0f} | {bh.mean_tokens:.0f} | "
                f"{d['tokens_delta']:+.0f} |"
            )
        lines.append("")

    if report.delta_B_minus_C:
        lines.append("## B − C by hop_depth (the structure-isolation signal)")
        lines.append("")
        lines.append("| hop | n | C recall | B recall | Δrecall (pp) | C tokens | B tokens | Δtokens |")
        lines.append("|-----|---|----------|----------|--------------|----------|----------|---------|")
        for h in sorted(report.delta_B_minus_C.keys()):
            d = report.delta_B_minus_C[h]
            ch = C.by_hop[h]
            bh = B.by_hop[h]
            lines.append(
                f"| {h} | {bh.n} | "
                f"{ch.mean_recall:.3f} | {bh.mean_recall:.3f} | "
                f"{d['recall_delta_pp']:+.1f} | "
                f"{ch.mean_tokens:.0f} | {bh.mean_tokens:.0f} | "
                f"{d['tokens_delta']:+.0f} |"
            )
        lines.append("")

    if B2_stats is not None and B is not None:
        lines.append("## B − B2 by hop_depth (format: triples vs hierarchical)")
        lines.append("")
        lines.append("| hop | n | B2 recall | B recall | Δrecall (pp) | B2 tokens | B tokens | Δtokens |")
        lines.append("|-----|---|-----------|----------|--------------|-----------|----------|---------|")
        all_hops = sorted(set(list(B2_stats.by_hop.keys()) + list(B.by_hop.keys())))
        for h in all_hops:
            b2h = B2_stats.by_hop.get(h)
            bh = B.by_hop.get(h)
            if b2h is None or bh is None:
                continue
            recall_delta = (b2h["mean_recall"] - bh.mean_recall) * 100
            token_delta = b2h["mean_tokens"] - bh.mean_tokens
            lines.append(
                f"| {h} | {bh.n} | "
                f"{b2h['mean_recall']:.3f} | {bh.mean_recall:.3f} | "
                f"{recall_delta:+.1f} | "
                f"{b2h['mean_tokens']:.0f} | {bh.mean_tokens:.0f} | "
                f"{token_delta:+.0f} |"
            )
        lines.append("")
        recall_delta_total = (B2_stats.mean_recall - B.mean_recall) * 100
        token_delta_total = B2_stats.mean_tokens - B.mean_tokens
        lines.append(
            f"**B vs B2:** recall {B.mean_recall:.3f} vs {B2_stats.mean_recall:.3f} "
            f"({'+' if recall_delta_total >= 0 else ''}{recall_delta_total:.1f}pp), "
            f"tokens {B.mean_tokens:.0f} vs {B2_stats.mean_tokens:.0f} "
            f"({'fewer' if token_delta_total < 0 else 'more'} by {abs(token_delta_total) / max(B.mean_tokens, 1) * 100:.0f}%)"
        )
        lines.append("")

    lines.append(f"**Verdict:** {report.verdict}")
    if report.verdict_details:
        lines.append("")
        for d in report.verdict_details:
            lines.append(f"- {d}")
    lines.append("")

    summary_path.write_text("\n".join(lines))

    (out_dir / "cat2c_report.json").write_text(
        json.dumps(report.to_dict(), indent=2)
    )

    return summary_path


# --- main ----------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--domains",
        nargs="*",
        default=DOMAINS,
        help="Subset of domains to run (default: all 5 shortlisted)",
    )
    ap.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="Cap queries per domain (smoke test)",
    )
    ap.add_argument(
        "--b2",
        action="store_true",
        help="Also run Condition B2 (hierarchical format) alongside A/B/C",
    )
    args = ap.parse_args()

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    overall: list[tuple[str, DomainRun, Path]] = []

    for d in args.domains:
        print(f"\n=== {d} ===" + (" [B2]" if args.b2 else ""))
        run = run_domain(d, max_queries=args.max_queries, include_b2=args.b2)
        paths = write_outputs(run)
        summary = write_summary(run, paths)
        print(f"  ran {run.n_queries} queries (no-match={run.no_match_count})")
        print(f"  conditions: {list(run.by_condition.keys())}")
        print(f"  summary: {summary.relative_to(_REPO_ROOT)}")
        overall.append((d, run, summary))

    # tiny cross-domain index
    idx = RESULTS_ROOT / "_index.md"
    idx_lines = ["# CKG-benchmark experiment results", ""]
    idx_lines.append(f"- tokenizer: `{_TOKENIZER}`")
    idx_lines.append("")
    idx_lines.append("| domain | queries | no-match | summary |")
    idx_lines.append("|--------|---------|----------|---------|")
    for d, run, summary in overall:
        idx_lines.append(
            f"| {d} | {run.n_queries} | {run.no_match_count} | "
            f"[summary]({summary.relative_to(RESULTS_ROOT)}) |"
        )
    idx.write_text("\n".join(idx_lines) + "\n")
    print(f"\nindex: {idx.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
