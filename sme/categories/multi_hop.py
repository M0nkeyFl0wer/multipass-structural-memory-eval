"""Category 2c: Multi-Hop Retrieval Recall by Depth.

Takes retrieval result JSONs (as emitted by ``sme-eval retrieve --json``)
for one or more conditions and computes the hop-depth breakdown. This
is a pure post-processing step over Cat 1/Cat 7 style results — it
reuses the same questions and simply groups them by their annotated
``min_hops`` value.

Spec expectation (from sme_spec_v5 Cat 2c):

    At 1-hop, graph advantage may be modest (1.5x). At 3-hop, it
    should be dramatic (5-10x). If it doesn't scale with depth,
    the traversal isn't working.

The scorer reports:
    - Per-hop recall for each condition
    - B-A and B-C deltas by hop depth (if A and C are provided)
    - Verdict: does structure earn complexity at multi-hop?

Three conditions follow Cat 7 Condition A/B/C convention:
    A = flat baseline (no structure)
    B = full pipeline (structural layer enabled)
    C = full pipeline with structural layer disabled (same index)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class HopBreakdown:
    hops: int
    n: int
    mean_recall: float
    hit_rate: float
    mean_tokens: float
    correct_count: int


@dataclass
class ConditionReport:
    name: str  # A | B | C
    label: str  # human-readable
    total_questions: int
    full_recall: int
    partial_hits: int
    mean_recall: float
    mean_tokens: float
    tokens_per_correct: Optional[float]
    by_hop: dict[int, HopBreakdown]


@dataclass
class Cat2cReport:
    conditions: dict[str, ConditionReport] = field(default_factory=dict)
    # Per-hop deltas
    delta_B_minus_A: dict[int, dict[str, float]] = field(default_factory=dict)
    delta_B_minus_C: dict[int, dict[str, float]] = field(default_factory=dict)
    # Per-hop ratios (B recall / A recall)
    ratio_B_over_A: dict[int, float] = field(default_factory=dict)
    # Verdict
    verdict: str = ""
    verdict_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "conditions": {
                name: {
                    "label": cr.label,
                    "total": cr.total_questions,
                    "full_recall": cr.full_recall,
                    "partial_hits": cr.partial_hits,
                    "mean_recall": cr.mean_recall,
                    "mean_tokens": cr.mean_tokens,
                    "tokens_per_correct": cr.tokens_per_correct,
                    "by_hop": {
                        str(h): {
                            "hops": bk.hops,
                            "n": bk.n,
                            "mean_recall": bk.mean_recall,
                            "hit_rate": bk.hit_rate,
                            "mean_tokens": bk.mean_tokens,
                            "correct_count": bk.correct_count,
                        }
                        for h, bk in cr.by_hop.items()
                    },
                }
                for name, cr in self.conditions.items()
            },
            "delta_B_minus_A": {
                str(h): d for h, d in self.delta_B_minus_A.items()
            },
            "delta_B_minus_C": {
                str(h): d for h, d in self.delta_B_minus_C.items()
            },
            "ratio_B_over_A": {
                str(h): r for h, r in self.ratio_B_over_A.items()
            },
            "verdict": self.verdict,
            "verdict_details": self.verdict_details,
        }


def _load_retrieve_json(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _build_condition_report(
    name: str, label: str, data: dict
) -> ConditionReport:
    """Convert a retrieve-results JSON dict into a ConditionReport."""
    questions = data.get("questions", [])
    summary = data.get("summary", {}) or {}

    by_hop: dict[int, HopBreakdown] = {}
    for q in questions:
        h = int(q.get("min_hops", 0))
        by_hop.setdefault(
            h,
            HopBreakdown(
                hops=h,
                n=0,
                mean_recall=0.0,
                hit_rate=0.0,
                mean_tokens=0.0,
                correct_count=0,
            ),
        )

    # Accumulate per-hop
    sums: dict[int, dict] = {
        h: {"recall": 0.0, "hit": 0, "tokens": 0.0, "correct": 0, "n": 0}
        for h in by_hop
    }
    for q in questions:
        h = int(q.get("min_hops", 0))
        s = sums[h]
        s["recall"] += float(q.get("recall", 0.0))
        s["hit"] += 1 if q.get("hit") else 0
        s["tokens"] += float(q.get("tokens", 0))
        if float(q.get("recall", 0.0)) >= 1.0:
            s["correct"] += 1
        s["n"] += 1

    for h, s in sums.items():
        n = s["n"]
        by_hop[h] = HopBreakdown(
            hops=h,
            n=n,
            mean_recall=(s["recall"] / n) if n else 0.0,
            hit_rate=(s["hit"] / n) if n else 0.0,
            mean_tokens=(s["tokens"] / n) if n else 0.0,
            correct_count=s["correct"],
        )

    total = len(questions)
    full_recall = sum(1 for q in questions if q.get("recall", 0.0) >= 1.0)
    partial = sum(1 for q in questions if q.get("hit"))
    mean_recall = (
        sum(float(q.get("recall", 0.0)) for q in questions) / total
        if total
        else 0.0
    )
    total_tokens = sum(float(q.get("tokens", 0)) for q in questions)
    mean_tokens = total_tokens / total if total else 0.0
    tokens_per_correct = (
        total_tokens / full_recall if full_recall else None
    )

    return ConditionReport(
        name=name,
        label=label,
        total_questions=total,
        full_recall=full_recall,
        partial_hits=partial,
        mean_recall=mean_recall,
        mean_tokens=mean_tokens,
        tokens_per_correct=tokens_per_correct,
        by_hop=by_hop,
    )


def score_cat2c(
    flat_json: Optional[str | Path] = None,
    graph_json: Optional[str | Path] = None,
    no_structure_json: Optional[str | Path] = None,
    *,
    flat_label: str = "flat baseline",
    graph_label: str = "full pipeline",
    no_structure_label: str = "structure disabled",
) -> Cat2cReport:
    """Produce a Cat 2c multi-hop scorecard from retrieval result JSONs.

    Exactly one of ``graph_json`` is required (the system under test).
    ``flat_json`` (Condition A) and ``no_structure_json`` (Condition C)
    are optional but strongly recommended — without them, the report
    can only show Condition B in isolation.
    """
    if graph_json is None:
        raise ValueError("graph_json (Condition B) is required")

    report = Cat2cReport()

    if flat_json:
        report.conditions["A"] = _build_condition_report(
            "A", flat_label, _load_retrieve_json(flat_json)
        )
    report.conditions["B"] = _build_condition_report(
        "B", graph_label, _load_retrieve_json(graph_json)
    )
    if no_structure_json:
        report.conditions["C"] = _build_condition_report(
            "C", no_structure_label, _load_retrieve_json(no_structure_json)
        )

    # Align hop sets across conditions
    all_hops = set()
    for cond in report.conditions.values():
        all_hops.update(cond.by_hop.keys())

    A = report.conditions.get("A")
    B = report.conditions["B"]
    C = report.conditions.get("C")

    for h in sorted(all_hops):
        if A and h in A.by_hop and h in B.by_hop:
            ar, br = A.by_hop[h].mean_recall, B.by_hop[h].mean_recall
            at, bt = A.by_hop[h].mean_tokens, B.by_hop[h].mean_tokens
            report.delta_B_minus_A[h] = {
                "recall_delta_pp": (br - ar) * 100,
                "tokens_delta": bt - at,
            }
            report.ratio_B_over_A[h] = (br / ar) if ar else float("inf")
        if C and h in C.by_hop and h in B.by_hop:
            cr, br = C.by_hop[h].mean_recall, B.by_hop[h].mean_recall
            ct, bt = C.by_hop[h].mean_tokens, B.by_hop[h].mean_tokens
            report.delta_B_minus_C[h] = {
                "recall_delta_pp": (br - cr) * 100,
                "tokens_delta": bt - ct,
            }

    # Verdict
    report.verdict, report.verdict_details = _verdict(report)

    return report


def _verdict(report: Cat2cReport) -> tuple[str, list[str]]:
    """Derive a structural-contribution verdict from the deltas.

    Rules:
      - If B - C is consistently positive on recall across hop depths,
        structure is earning complexity (the routing layer helps).
      - If B - C is near zero across all depths, structure is a neutral
        tax (routing adds nothing beyond metadata).
      - If B - C is negative at any depth (esp. 2+), structure is
        harmful at multi-hop — the routing is throwing away answers.
      - If the B/A ratio doesn't grow with depth, structure doesn't
        earn its complexity even if it matches flat — the spec
        expects the advantage to scale with hops.
    """
    details: list[str] = []

    if not report.delta_B_minus_C:
        details.append(
            "no Condition C provided — cannot isolate structural contribution"
        )

    if not report.delta_B_minus_A:
        details.append(
            "no Condition A (flat) provided — cannot compare to baseline"
        )
        return ("incomplete", details)

    # Check if B ever beats A meaningfully (>5pp at any depth)
    beats_a_at: list[int] = []
    loses_a_at: list[int] = []
    for h, d in sorted(report.delta_B_minus_A.items()):
        if d["recall_delta_pp"] > 5:
            beats_a_at.append(h)
        elif d["recall_delta_pp"] < -5:
            loses_a_at.append(h)

    # Check if B/A ratio grows with hops (the spec expectation)
    ratios_sorted = [
        (h, r)
        for h, r in sorted(report.ratio_B_over_A.items())
        if r != float("inf")
    ]
    ratio_grows = False
    if len(ratios_sorted) >= 2:
        first = ratios_sorted[0][1]
        last = ratios_sorted[-1][1]
        ratio_grows = last > first * 1.2

    # B - C pattern
    if report.delta_B_minus_C:
        structural_positive_at: list[int] = []
        structural_negative_at: list[int] = []
        for h, d in sorted(report.delta_B_minus_C.items()):
            if d["recall_delta_pp"] > 5:
                structural_positive_at.append(h)
            elif d["recall_delta_pp"] < -5:
                structural_negative_at.append(h)
        if structural_negative_at:
            details.append(
                "B - C is negative at hops "
                + ",".join(str(h) for h in structural_negative_at)
                + " — structural routing is actively harmful"
            )
        elif structural_positive_at:
            details.append(
                "B - C is positive at hops "
                + ",".join(str(h) for h in structural_positive_at)
                + " — structure contributes real value"
            )
        else:
            details.append(
                "B - C is near zero across all hop depths — "
                "structure is a neutral tax, adds nothing beyond metadata"
            )

    if loses_a_at and not beats_a_at:
        verdict = "structure harmful at multi-hop"
        details.append(
            f"B loses to flat at {len(loses_a_at)} hop depth(s) "
            f"and never wins — structure fails to earn its complexity"
        )
    elif beats_a_at and not loses_a_at:
        if ratio_grows:
            verdict = "structure earns complexity (scales with depth)"
            details.append(
                "B/A ratio grows with hop depth as the spec predicts "
                "— multi-hop traversal is working"
            )
        else:
            verdict = "structure adds value at uniform scale"
            details.append(
                "B beats flat but the advantage does not grow with depth "
                "— traversal may not be active, benefits may come from re-ranking"
            )
    elif not beats_a_at and not loses_a_at:
        verdict = "structure is a neutral tax"
    else:
        verdict = "mixed: structure helps at some depths and hurts at others"

    return verdict, details


def format_report(report: Cat2cReport) -> str:
    """Render a readable text scorecard."""
    lines: list[str] = []
    lines.append("=" * 76)
    lines.append(" Category 2c: Multi-Hop Recall by Depth")
    lines.append("=" * 76)

    # Header row
    conds = list(report.conditions.values())
    hops_present = sorted(
        {h for cond in conds for h in cond.by_hop.keys()}
    )

    lines.append("")
    hop_hdr = "  ".join(f"{h}-hop" for h in hops_present)
    lines.append(f"  {'condition':<26} {hop_hdr}  overall")
    lines.append(f"  {'-' * 26} " + "  ".join(["-----"] * len(hops_present)) + "  -------")

    for cond in conds:
        cells = []
        for h in hops_present:
            bk = cond.by_hop.get(h)
            if bk:
                cells.append(f"{bk.mean_recall:5.0%}")
            else:
                cells.append("  n/a")
        overall = f"{cond.mean_recall:5.0%}"
        label = f"{cond.label[:24]:24}"
        lines.append(f"  {label}  " + "  ".join(cells) + f"  {overall}")

    lines.append("")
    lines.append("  Tokens per query:")
    for cond in conds:
        cells = []
        for h in hops_present:
            bk = cond.by_hop.get(h)
            cells.append(f"{bk.mean_tokens:5.0f}" if bk else "  n/a")
        lines.append(
            f"  {cond.label[:24]:24}  " + "  ".join(cells) + f"  {cond.mean_tokens:5.0f}"
        )

    # Tokens per correct answer
    lines.append("")
    lines.append("  Tokens per correct answer (overall):")
    for cond in conds:
        tpc = cond.tokens_per_correct
        lines.append(
            f"  {cond.label[:24]:24}  "
            + (f"{tpc:6.0f}" if tpc is not None else "   inf (no full-recall queries)")
        )

    # Deltas
    if report.delta_B_minus_A:
        lines.append("")
        lines.append("  B − A (structural + metadata contribution) by hop:")
        for h, d in sorted(report.delta_B_minus_A.items()):
            sign = "+" if d["recall_delta_pp"] >= 0 else ""
            lines.append(
                f"    {h}-hop:  recall {sign}{d['recall_delta_pp']:.1f}pp   "
                f"tokens {d['tokens_delta']:+.0f}"
            )

    if report.delta_B_minus_C:
        lines.append("")
        lines.append("  B − C (structural layer alone) by hop:")
        for h, d in sorted(report.delta_B_minus_C.items()):
            sign = "+" if d["recall_delta_pp"] >= 0 else ""
            lines.append(
                f"    {h}-hop:  recall {sign}{d['recall_delta_pp']:.1f}pp   "
                f"tokens {d['tokens_delta']:+.0f}"
            )

    # Ratio
    if report.ratio_B_over_A:
        lines.append("")
        lines.append("  B / A ratio by hop (spec expects to grow with depth):")
        for h, r in sorted(report.ratio_B_over_A.items()):
            if r == float("inf"):
                cell = "  inf"
            else:
                cell = f"{r:.2f}x"
            lines.append(f"    {h}-hop:  {cell}")

    # Verdict
    lines.append("")
    lines.append("  " + "─" * 72)
    lines.append(f"  VERDICT: {report.verdict}")
    for note in report.verdict_details:
        lines.append(f"    — {note}")
    lines.append("")
    return "\n".join(lines)
