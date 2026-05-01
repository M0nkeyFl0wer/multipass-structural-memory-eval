#!/usr/bin/env python3
"""Cross-validate SME's substring scorer against LongMemEval's GPT-4o judge.

Runs every question in a LongMemEval JSON file (oracle / S / M) through
the chosen SME adapter, scores the same retrieval with both:

  1. SME's substring matcher over `expected_sources` session ids
  2. LongMemEval's GPT-4o judge methodology (per-question-type prompts)

and reports per-SME-category disagreement. Per the KU / Cat 3 semantic-
divergence caveat documented in docs/related_work/longmemeval.md, the
report deliberately does NOT compute a single overall correlation —
each `sme_category` is reported separately so KU's silent-overwrite
reward doesn't drag a contradiction-flagging Cat 3 system's correlation
down.

CLI:

    cross_validate_longmemeval.py
        --dataset PATH                # longmemeval_oracle.json (required)
        --adapter NAME                # flat | mempalace | full-context
        --max-questions N             # smoke-test cap (optional)
        --reader-model MODEL          # default gpt-4o-mini
        --judge-model MODEL           # default gpt-4o-2024-08-06
        --skip-judge                  # SME-only pass when no API key
        --skip-reader                 # judge sees raw context_string
        --out PATH                    # report JSON destination

`OPENAI_API_KEY` controls reader and judge availability; when missing,
the harness still produces SME substring scores so partial readings are
useful.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

# Ensure repo root is importable when run as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sme.adapters.base import QueryResult, SMEAdapter  # noqa: E402
from sme.corpora.longmemeval import (  # noqa: E402
    LMEQuestion,
    load_questions,
    materialize_sme_corpus,
)
from sme.eval.longmemeval_judge import grade_answer  # noqa: E402

log = logging.getLogger("cross_validate_longmemeval")

# Disagreement is "interesting" when SME recall and judge correctness
# imply opposite verdicts. Concretely: SME recall >= 0.5 but judge
# INCORRECT/ABSTAIN-fail, OR SME recall < 0.5 but judge CORRECT.
_DISAGREE_THRESHOLD = 0.5


# --- Adapter construction ---------------------------------------------------

AdapterFactory = Callable[[Path], SMEAdapter]


def _make_full_context_adapter(per_q_vault: Path) -> SMEAdapter:
    from sme.conditions.full_context import FullContextAdapter
    return FullContextAdapter(per_q_vault)


def _make_flat_adapter(per_q_vault: Path) -> SMEAdapter:
    """Build a FlatBaselineAdapter from a per-question vault.

    FlatBaselineAdapter wants a ChromaDB persistence directory, not a
    raw markdown vault. For LongMemEval we ingest the per-question .md
    files into an ephemeral Chroma collection, then point the adapter
    at it. ChromaDB is an optional SME extra — if not installed, the
    harness raises a clear error so the user can pick a different
    adapter or pip-install it.
    """
    try:
        import chromadb  # noqa: F401
    except ImportError as e:  # pragma: no cover — env-dependent
        raise RuntimeError(
            "FlatChromaAdapter requires chromadb. Install with "
            "`pip install chromadb` or pass --adapter full-context."
        ) from e

    from sme.adapters.flat_baseline import FlatBaselineAdapter
    import chromadb as _chromadb  # noqa: WPS433 — late re-import for instance

    db_dir = per_q_vault / "_chroma"
    db_dir.mkdir(parents=True, exist_ok=True)
    client = _chromadb.PersistentClient(path=str(db_dir))
    coll = client.get_or_create_collection(name="lme_per_question")
    docs: list[str] = []
    ids: list[str] = []
    for md_file in sorted(per_q_vault.rglob("*.md")):
        if not md_file.is_file():
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        docs.append(text)
        ids.append(md_file.stem)
    if docs:
        coll.upsert(ids=ids, documents=docs)
    return FlatBaselineAdapter(
        db_path=str(db_dir),
        collection_name="lme_per_question",
        n_results=5,
    )


def _make_mempalace_adapter(per_q_vault: Path) -> SMEAdapter:  # pragma: no cover — heavy
    raise RuntimeError(
        "mempalace adapter not yet wired into cross_validate_longmemeval; "
        "use --adapter full-context for the no-retrieval baseline or "
        "--adapter flat for the chroma baseline."
    )


_ADAPTER_FACTORIES: dict[str, AdapterFactory] = {
    "full-context": _make_full_context_adapter,
    "flat": _make_flat_adapter,
    "mempalace": _make_mempalace_adapter,
}


# --- Scoring helpers --------------------------------------------------------

def sme_substring_recall(retrieved: str, expected: list[str]) -> tuple[float, list[str]]:
    """Substring-match the SME way: count how many expected sources
    appear as substrings of the retrieved context_string.

    Mirrors the scoring in sme.cli (lines ~1000) so the cross-validation
    numbers are comparable to SME's own retrieval-test reports.
    """
    if not expected:
        return 0.0, []
    matched = [s for s in expected if s and s in retrieved]
    return len(matched) / len(expected), matched


def judge_label_to_correct(label: str) -> Optional[bool]:
    """Convert an autoeval_label into a binary correctness signal.

    Returns True for CORRECT/ABSTAIN (ABSTAIN is "correctly refused"),
    False for INCORRECT/PARTIAL, None for ERROR (unknown — exclude
    from rate denominators).
    """
    if label == "CORRECT":
        return True
    if label == "ABSTAIN":
        return True  # for abstention questions this is the success state
    if label in ("INCORRECT", "PARTIAL"):
        return False
    return None


# --- Reader pass ------------------------------------------------------------

def generate_hypothesis(
    question: str,
    context_string: str,
    *,
    reader_model: str,
    client: Optional[Any] = None,
) -> str:
    """One-shot reader call: feed retrieved context + question, get an
    answer string the judge can score.

    Mirrors LongMemEval's standard reader prompt — ask the model to
    answer using only the provided sessions. Returns the empty string
    on any failure so the harness can keep going (judge will then mark
    INCORRECT, which is the right signal: we couldn't produce an answer).
    """
    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            return ""
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            return ""
        client = OpenAI()
    prompt = (
        "Answer the user's question using only the conversation history "
        "below. If the answer is not present, say 'I don't know.'\n\n"
        f"Conversation history:\n{context_string}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    try:
        resp = client.chat.completions.create(
            model=reader_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        log.warning("reader call failed: %s", e)
        return ""


# --- Per-question loop ------------------------------------------------------

def run_one_question(
    q: LMEQuestion,
    *,
    adapter_factory: AdapterFactory,
    work_dir: Path,
    skip_judge: bool,
    skip_reader: bool,
    reader_model: str,
    judge_model: str,
    reader_client: Optional[Any] = None,
    judge_client: Optional[Any] = None,
) -> dict:
    """Materialize the question's per-question vault, build adapter, run
    SME + judge scorers, return one record."""
    # 1. Materialize ONLY this question to a per-question dir
    out_dir = work_dir / q.question_id
    materialize_sme_corpus([q], out_dir, max_questions=1)
    per_q_vault = out_dir / "vault" / q.question_id

    # 2. Build adapter
    adapter = adapter_factory(per_q_vault)

    # 3. Query
    try:
        try:
            result = adapter.query(q.question, n_results=5)
        except TypeError:
            result = adapter.query(q.question)
    except Exception as e:  # noqa: BLE001 — record but continue
        result = QueryResult(answer="", context_string="", error=str(e))
    finally:
        try:
            adapter.close()
        except Exception:  # noqa: BLE001
            pass

    ctx = result.context_string or ""

    # 4. SME substring score
    expected = q.expected_sources_session_level()
    sme_recall, matched = sme_substring_recall(ctx, expected)

    record: dict[str, Any] = {
        "question_id": q.question_id,
        "question_type": q.question_type,
        "sme_category": q.sme_category,
        "is_abstention": q.is_abstention,
        "expected_sources": expected,
        "matched_sources": matched,
        "sme_recall": sme_recall,
        "context_chars": len(ctx),
        "adapter_error": result.error,
    }

    # 5. Optional reader → hypothesis
    if skip_judge:
        record["hypothesis"] = None
        record["judge"] = None
        return record

    qtype_for_judge = "abstention" if q.is_abstention else q.question_type

    if skip_reader:
        # Hand the judge the raw retrieval (option (a) in the planning
        # doc — diagnostic-grade, not apples-to-apples with LongMemEval).
        hypothesis = ctx[:8000]  # cap to keep judge prompt manageable
    else:
        hypothesis = generate_hypothesis(
            q.question, ctx,
            reader_model=reader_model,
            client=reader_client,
        )
    record["hypothesis"] = hypothesis

    judge = grade_answer(
        question_type=qtype_for_judge,
        question=q.question,
        gold_answer=q.answer,
        hypothesis=hypothesis,
        judge_model=judge_model,
        client=judge_client,
    )
    record["judge"] = judge
    return record


# --- Aggregation ------------------------------------------------------------

def _empty_category_slot() -> dict[str, Any]:
    return {
        "n": 0,
        "sme_recall_sum": 0.0,
        "judge_correct": 0,
        "judge_incorrect": 0,
        "judge_partial": 0,
        "judge_abstain": 0,
        "judge_error": 0,
        "judge_skipped": 0,
    }


def _update_judge_label_count(slot: dict, label: str) -> None:
    key = f"judge_{label.lower()}"
    slot[key] = slot.get(key, 0) + 1


def _accumulate_usage(running: dict, fresh: dict) -> None:
    for k in running:
        running[k] += int(fresh.get(k, 0) or 0)


def _is_disagreement(sme_recall: float, judge_correct: Optional[bool]) -> bool:
    if judge_correct is None:
        return False
    sme_says_correct = sme_recall >= _DISAGREE_THRESHOLD
    return sme_says_correct != judge_correct


def _update_slot_for_record(slot: dict, record: dict) -> Optional[str]:
    """Apply one record's counts to its category slot.

    Returns the judge label string when there's a real judge verdict,
    None when the judge was skipped. Disagreement detection happens
    in the caller because it needs visibility into the disagreement
    list.
    """
    slot["n"] += 1
    slot["sme_recall_sum"] += record["sme_recall"]
    judge = record.get("judge")
    if judge is None:
        slot["judge_skipped"] += 1
        return None
    label = judge.get("autoeval_label", "ERROR")
    _update_judge_label_count(slot, label)
    return label


def aggregate(records: list[dict]) -> dict:
    """Compute per-category SME mean recall, judge correct-rate, and
    a disagreement set. Per the KU semantic-divergence caveat, NO
    overall single-number correlation is reported.
    """
    by_cat: dict[str, dict[str, Any]] = {}
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    disagreements: list[dict] = []

    for r in records:
        cat = r["sme_category"]
        if cat not in by_cat:
            by_cat[cat] = _empty_category_slot()
        label = _update_slot_for_record(by_cat[cat], r)
        if label is None:
            continue

        judge = r["judge"]
        _accumulate_usage(total_usage, judge.get("usage") or {})

        if _is_disagreement(r["sme_recall"], judge_label_to_correct(label)):
            disagreements.append({
                "question_id": r["question_id"],
                "sme_category": cat,
                "sme_recall": r["sme_recall"],
                "judge_label": label,
                "judge_rationale": judge.get("rationale", ""),
            })

    per_cat = {}
    for cat, slot in sorted(by_cat.items()):
        n = slot["n"]
        judged = (
            slot["judge_correct"] + slot["judge_incorrect"]
            + slot["judge_partial"] + slot["judge_abstain"]
        )
        sme_recall_mean = slot["sme_recall_sum"] / n if n else 0.0
        judge_correct_rate = (
            (slot["judge_correct"] + slot["judge_abstain"]) / judged
            if judged else None
        )
        per_cat[cat] = {
            "n": n,
            "sme_recall_mean": round(sme_recall_mean, 4),
            "judge_correct_rate": (
                round(judge_correct_rate, 4)
                if judge_correct_rate is not None else None
            ),
            "judge_label_counts": {
                "CORRECT": slot["judge_correct"],
                "PARTIAL": slot["judge_partial"],
                "INCORRECT": slot["judge_incorrect"],
                "ABSTAIN": slot["judge_abstain"],
                "ERROR": slot["judge_error"],
                "skipped": slot["judge_skipped"],
            },
        }

    return {
        "per_category": per_cat,
        "total_questions": len(records),
        "judge_total_usage": total_usage,
        "disagreements": disagreements,
        "ku_caveat": (
            "Per-category numbers are reported separately by design. "
            "KU (knowledge-update) and SME Cat 3 measure different "
            "primitives — KU rewards returning the new value, Cat 3 "
            "rewards flagging the contradiction. A single overall "
            "correlation would mislead. See docs/related_work/longmemeval.md."
        ),
    }


# --- Main -------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run LongMemEval questions through an SME adapter, score with "
            "both SME's substring matcher and LongMemEval's GPT-4o judge, "
            "report per-category disagreement."
        ),
    )
    p.add_argument("--dataset", required=True, type=Path,
                   help="Path to longmemeval_oracle.json (or _s / _m).")
    p.add_argument("--adapter", required=True,
                   choices=sorted(_ADAPTER_FACTORIES),
                   help="SME adapter to run.")
    p.add_argument("--max-questions", type=int, default=None,
                   help="Smoke-test cap on number of questions.")
    p.add_argument("--reader-model", default="gpt-4o-mini",
                   help="Model used to turn retrieved context into an "
                        "answer the judge can score.")
    p.add_argument("--judge-model", default="gpt-4o-2024-08-06",
                   help="LongMemEval judge model.")
    p.add_argument("--skip-judge", action="store_true",
                   help="Run SME-only — no reader, no judge, no API key "
                        "required.")
    p.add_argument("--skip-reader", action="store_true",
                   help="Skip the reader pass; feed raw retrieval to the "
                        "judge (diagnostic mode).")
    p.add_argument("--out", type=Path, default=None,
                   help="Where to write the report JSON.")
    p.add_argument("--work-dir", type=Path, default=None,
                   help="Where per-question vaults are materialized "
                        "(default: tmpdir).")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def run(args: argparse.Namespace,
        *,
        reader_client: Optional[Any] = None,
        judge_client: Optional[Any] = None) -> dict:
    """Programmatic entry point — used by tests."""
    factory = _ADAPTER_FACTORIES[args.adapter]

    work_dir_ctx: Optional[tempfile.TemporaryDirectory[str]] = None
    if args.work_dir is not None:
        work_dir = args.work_dir
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        work_dir_ctx = tempfile.TemporaryDirectory(prefix="sme_xval_")
        work_dir = Path(work_dir_ctx.name)

    records: list[dict] = []
    try:
        for i, q in enumerate(load_questions(args.dataset)):
            if args.max_questions is not None and i >= args.max_questions:
                break
            log.info(
                "[%d] %s (%s / %s)",
                i, q.question_id, q.question_type, q.sme_category,
            )
            rec = run_one_question(
                q,
                adapter_factory=factory,
                work_dir=work_dir,
                skip_judge=args.skip_judge,
                skip_reader=args.skip_reader,
                reader_model=args.reader_model,
                judge_model=args.judge_model,
                reader_client=reader_client,
                judge_client=judge_client,
            )
            records.append(rec)
    finally:
        if work_dir_ctx is not None:
            work_dir_ctx.cleanup()

    summary = aggregate(records)
    report = {
        "run_metadata": {
            "dataset": str(args.dataset),
            "adapter": args.adapter,
            "reader_model": (None if args.skip_reader or args.skip_judge
                             else args.reader_model),
            "judge_model": (None if args.skip_judge else args.judge_model),
            "skip_judge": bool(args.skip_judge),
            "skip_reader": bool(args.skip_reader),
            "max_questions": args.max_questions,
            "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        },
        "summary": summary,
        "per_question": records,
    }
    return report


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    report = run(args)

    out = args.out
    if out is None:
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        out = Path(f"cross_validation_{ts}.json")
    out.write_text(json.dumps(report, indent=2, default=str))

    print(f"Wrote {out}")
    summary = report["summary"]
    for cat, slot in summary["per_category"].items():
        print(
            f"  {cat:20s} n={slot['n']:4d}  "
            f"sme_recall={slot['sme_recall_mean']:.3f}  "
            f"judge_correct_rate={slot['judge_correct_rate']!s}"
        )
    print(f"  disagreements: {len(summary['disagreements'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
