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
        default_factory=lambda: {"A": [], "B": [], "C": []}
    )
    no_match_count: int = 0


def run_domain(domain: str, *, max_queries: int | None = None) -> DomainRun:
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
            row = run_one(adapter, q)
            out.rows.append(row)
            for cond in ("A", "B", "C"):
                out.by_condition[cond].append(row[cond])
            out.n_queries += 1
            if row["B"]["error"] == "NO_MATCH":
                out.no_match_count += 1
    return out


def run_one(adapter: CKGAdapter, q: dict) -> dict[str, Any]:
    question = q["query"]
    gt = list(q.get("ground_truth", []))
    hop = int(q.get("hop_depth", 0))
    qid = q["id"]
    qtype = q.get("type", "")

    res_a = adapter.get_flat_retrieval(question)
    res_b = adapter.query(question)

    # Condition C uses the SAME node set B retrieved, prose-only.
    # Empty context when B failed (NO_MATCH).
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

    return {
        "id": qid,
        "type": qtype,
        "hop_depth": hop,
        "ground_truth": gt,
        "A": cond_row("A", res_a.context_string, a_recall, a_hit, res_a.error),
        "B": cond_row("B", res_b.context_string, b_recall, b_hit, res_b.error),
        "C": cond_row("C", c_context, c_recall, c_hit, res_b.error),
    }


# --- output writers -----------------------------------------------


def write_outputs(run: DomainRun) -> dict[str, Path]:
    out_dir = RESULTS_ROOT / run.domain
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    for cond in ("A", "B", "C"):
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
    for cond_name, cond in [("A", A), ("B", B), ("C", C)]:
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

    lines.append(f"**Verdict:** {report.verdict}")
    if report.verdict_details:
        lines.append("")
        for d in report.verdict_details:
            lines.append(f"- {d}")
    lines.append("")

    summary_path.write_text("\n".join(lines))

    # also dump raw report json for downstream tooling
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
    args = ap.parse_args()

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    overall: list[tuple[str, DomainRun, Path]] = []

    for d in args.domains:
        print(f"\n=== {d} ===")
        run = run_domain(d, max_queries=args.max_queries)
        paths = write_outputs(run)
        summary = write_summary(run, paths)
        print(f"  ran {run.n_queries} queries (no-match={run.no_match_count})")
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
