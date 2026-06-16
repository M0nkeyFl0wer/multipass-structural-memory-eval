#!/usr/bin/env python3
"""LLM reader + judge layer for the CKG-benchmark experiment.

Two-stage LongMemEval-style methodology (matches what Yarmoluk's own
benchmark would do, modulo F1-vs-substring):

  Stage 1 (reader, gpt-4o-mini): given context_string and question,
    produce a short answer using only the context.
  Stage 2 (judge, gpt-4o-2024-08-06): given question + reference
    answer (the CKG ground_truth) + reader's answer, return
    CORRECT / PARTIAL / INCORRECT. Same model the LongMemEval
    paper uses; mirrors sme/eval/longmemeval_judge.py.

Reads the per-condition JSONs the runner emitted, augments each
question with `llm_answer` and `llm_label`, writes them back. Idempotent:
re-running skips questions that already have a final label, so partial
runs can be continued without recomputing.

Concurrency via ThreadPoolExecutor (openai SDK is thread-safe). Default
20 workers; cap with --workers if you want to be polite to the API.

Cost estimate: ~$3.50 for the full 5-domain × 877-query × 3-condition
sweep at gpt-4o-mini reader + gpt-4o-2024-08-06 judge prices as of
2026-05.

Usage:
  scripts/judge_ckg.py                          # all 5 domains, all conditions
  scripts/judge_ckg.py --domains calculus       # one domain
  scripts/judge_ckg.py --max-queries 5 --domains calculus  # smoke
  scripts/judge_ckg.py --reader-model gpt-4o-mini  # override reader model
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DOMAINS = [
    "calculus",
    "us-geography",
    "moss",
    "glp1-obesity",
    "theory-of-knowledge",
]

RESULTS_ROOT = _REPO_ROOT / "results" / "ckg_benchmark"

VALID_LABELS = {"CORRECT", "PARTIAL", "INCORRECT", "ERROR"}

READER_PROMPT = """\
You are answering a question using ONLY the provided context. If the
context does not contain enough information, say "I don't know."

Context:
{context}

Question: {question}

Give a brief answer (1-2 sentences). Do not add information not in the
context.\
"""

JUDGE_PROMPT = """\
You are grading a model's answer against a reference answer.

Question: {question}
Reference answer: {reference}
Model answer: {model_answer}

Return exactly one word from {{CORRECT, PARTIAL, INCORRECT}}.

- CORRECT: model answer matches reference (allowing paraphrase)
- PARTIAL: model answer is on-topic but missing key element of reference
- INCORRECT: model answer is wrong, contradicts reference, or refuses\
"""


# --- thread-safe write lock -------------------------------------------

_WRITE_LOCKS: dict[str, threading.Lock] = {}
_WRITE_LOCK_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    with _WRITE_LOCK_GUARD:
        return _WRITE_LOCKS.setdefault(str(path), threading.Lock())


# --- OpenAI client ----------------------------------------------------


def _load_dotenv() -> None:
    """Read repo-root .env into os.environ if not already set.

    Tiny stdlib-only loader; does not handle quoting edge cases the
    same way python-dotenv does, but is enough for the simple KEY=val
    shape used in this repo.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        os.environ.setdefault(k, v)


def make_client():
    from openai import OpenAI

    _load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # mirror sme.eval.llm_clients keyring fallback
        import subprocess

        try:
            r = subprocess.run(
                ["secret-tool", "lookup", "service", "openai"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if r.returncode == 0 and r.stdout.strip():
                api_key = r.stdout.strip()
        except FileNotFoundError:
            pass
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set (no keyring entry either)")
    return OpenAI(api_key=api_key)


def chat_complete(client, model: str, prompt: str, *, retries: int = 6) -> str:
    """Call chat.completions with exponential backoff on rate-limit (429).

    Backoff schedule (seconds): 2, 4, 8, 16, 32, 60. Total ≈ 2 minutes
    in the worst case, which is enough to ride out a transient 429
    storm against gpt-4o-2024-08-06 at workers=5.
    """
    import random

    last_err = None
    for attempt in range(retries):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            return r.choices[0].message.content or ""
        except Exception as e:  # pragma: no cover — network
            last_err = e
            base = min(60, 2 ** (attempt + 1))
            # full jitter to spread thundering-herd retries
            time.sleep(base * (0.5 + random.random()))
    raise RuntimeError(f"openai call failed after {retries} retries: {last_err}")


def parse_label(judge_text: str) -> str:
    t = (judge_text or "").upper()
    for label in ("CORRECT", "PARTIAL", "INCORRECT"):
        # match whole-word so "INCORRECT" doesn't capture "CORRECT"
        if re.search(rf"\b{label}\b", t):
            return label
    return "ERROR"


# --- per-question pipeline -------------------------------------------


def run_one(
    client,
    *,
    question: str,
    context: str,
    reference: list[str],
    reader_model: str,
    judge_model: str,
) -> dict[str, Any]:
    if not context:
        return {
            "llm_answer": "",
            "llm_label": "INCORRECT",
            "llm_reader_model": reader_model,
            "llm_judge_model": judge_model,
            "llm_skipped_reason": "empty_context",
        }
    try:
        answer = chat_complete(
            client,
            reader_model,
            READER_PROMPT.format(context=context, question=question),
        )
    except Exception as e:
        return {
            "llm_answer": "",
            "llm_label": "ERROR",
            "llm_reader_model": reader_model,
            "llm_judge_model": judge_model,
            "llm_error": f"reader: {e}",
        }
    ref_str = " | ".join(s for s in reference if s)
    try:
        verdict = chat_complete(
            client,
            judge_model,
            JUDGE_PROMPT.format(
                question=question,
                reference=ref_str,
                model_answer=answer,
            ),
        )
    except Exception as e:
        return {
            "llm_answer": answer,
            "llm_label": "ERROR",
            "llm_reader_model": reader_model,
            "llm_judge_model": judge_model,
            "llm_error": f"judge: {e}",
        }
    return {
        "llm_answer": answer,
        "llm_label": parse_label(verdict),
        "llm_judge_raw": verdict,
        "llm_reader_model": reader_model,
        "llm_judge_model": judge_model,
    }


# --- per-domain dispatcher -------------------------------------------


def judge_condition(
    domain: str,
    cond: str,
    *,
    client,
    reader_model: str,
    judge_model: str,
    workers: int,
    max_queries: int | None,
    overwrite: bool,
    runs_by_id: dict[str, dict],
) -> tuple[int, int]:
    """Augment results/{domain}/condition_{cond}.json with llm_label.

    Returns (n_judged, n_skipped). Idempotent: skips entries that already
    have an llm_label unless --overwrite was passed.
    """
    path = RESULTS_ROOT / domain / f"condition_{cond}.json"
    if not path.exists():
        return 0, 0
    doc = json.loads(path.read_text())
    qs = doc["questions"]

    work: list[tuple[int, dict]] = []
    skipped = 0
    for i, q in enumerate(qs):
        if max_queries is not None and i >= max_queries:
            break
        existing = q.get("llm_label")
        if existing and existing != "ERROR" and not overwrite:
            skipped += 1
            continue
        work.append((i, q))

    if not work:
        return 0, skipped

    judged = 0
    lock = _lock_for(path)

    def task(item):
        i, q = item
        full = runs_by_id.get(q["id"])
        if full is None:
            return i, {"llm_label": "ERROR", "llm_error": "no run row"}
        # context_string is rehydrated onto the trace by reattach_context_strings()
        ctx = full.get(cond, {}).get("context_string", "")
        ref = full.get("ground_truth") or q.get("ground_truth", [])
        question_text = full.get("query") or q.get("query", "")
        result = run_one(
            client,
            question=question_text,
            context=ctx,
            reference=ref,
            reader_model=reader_model,
            judge_model=judge_model,
        )
        return i, result

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(task, item) for item in work]
        for fut in as_completed(futures):
            i, res = fut.result()
            with lock:
                qs[i].update(res)
            judged += 1
            if judged % 20 == 0:
                with lock:
                    path.write_text(json.dumps(doc, indent=2))
                print(
                    f"    [{domain}/{cond}] {judged}/{len(work)}",
                    flush=True,
                )

    with lock:
        path.write_text(json.dumps(doc, indent=2))
    return judged, skipped


def load_runs_jsonl(domain: str) -> dict[str, dict]:
    """Load the runner's per-query trace, indexed by query id, and rehydrate
    the context_string from the on-disk graph since runs.jsonl doesn't
    persist context to keep file sizes sane.

    For correctness: we re-create context_string at judge time using the
    saved runner row's metadata (which condition retrieved which entities)
    plus the live adapter. This costs one CKGAdapter load per domain
    (cheap)."""
    path = RESULTS_ROOT / domain / "runs.jsonl"
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            out[r["id"]] = r
    return out


def reattach_context_strings(domain: str, runs_by_id: dict[str, dict]) -> None:
    """Re-derive context_string per condition by re-running the adapter
    on the same query. This avoids needing to inflate runs.jsonl with
    full context text (which would balloon to dozens of MB per domain).
    """
    from sme.adapters.ckg import CKGAdapter

    DATA_ROOT = _REPO_ROOT / "data" / "ckg_benchmark"
    csv_path = DATA_ROOT / "domains" / domain / "learning-graph.csv"
    queries_path = DATA_ROOT / "queries" / f"queries_{domain}.jsonl"
    adapter = CKGAdapter(csv_path)
    adapter.ingest_corpus([])
    with open(queries_path) as f:
        for line in f:
            q = json.loads(line)
            r = runs_by_id.get(q["id"])
            if r is None:
                continue
            r["query"] = q["query"]
            res_a = adapter.get_flat_retrieval(q["query"])
            res_b = adapter.query(q["query"])
            r.setdefault("A", {})["context_string"] = res_a.context_string
            r.setdefault("B", {})["context_string"] = res_b.context_string
            if res_b.error is None:
                c_ctx = adapter.condition_c_serialization(res_b.retrieved_entities)
            else:
                c_ctx = ""
            r.setdefault("C", {})["context_string"] = c_ctx


# --- summary regen ----------------------------------------------------


def write_judge_summary(domain: str) -> None:
    out = RESULTS_ROOT / domain
    rows_by_cond: dict[str, list[dict]] = {}
    for cond in ("A", "B", "C"):
        p = out / f"condition_{cond}.json"
        if not p.exists():
            continue
        rows_by_cond[cond] = json.loads(p.read_text())["questions"]

    lines = [f"# CKG-benchmark — {domain} — LLM judge", ""]
    lines.append("Reader: gpt-4o-mini · Judge: gpt-4o-2024-08-06")
    lines.append("")
    lines.append("## Overall (LLM-judge label distribution)")
    lines.append("")
    lines.append("| Cond | n | CORRECT | PARTIAL | INCORRECT | ERROR | accuracy (C/P) |")
    lines.append("|---|---|---|---|---|---|---|")
    for cond in ("A", "B", "C"):
        if cond not in rows_by_cond:
            continue
        rs = rows_by_cond[cond]
        c = sum(1 for r in rs if r.get("llm_label") == "CORRECT")
        p = sum(1 for r in rs if r.get("llm_label") == "PARTIAL")
        inc = sum(1 for r in rs if r.get("llm_label") == "INCORRECT")
        err = sum(1 for r in rs if r.get("llm_label") in (None, "ERROR"))
        n = len(rs)
        acc = (c + 0.5 * p) / n if n else 0.0
        lines.append(
            f"| {cond} | {n} | {c} | {p} | {inc} | {err} | {acc:.3f} |"
        )
    lines.append("")
    lines.append("## By hop_depth — LLM-judge accuracy")
    lines.append("")
    lines.append("| hop | n | A acc | B acc | C acc | B−A pp | B−C pp |")
    lines.append("|---|---|---|---|---|---|---|")
    hops = sorted({r.get("min_hops", r.get("hop_depth", 0)) for c in rows_by_cond.values() for r in c})

    def acc_for(rows: list[dict], hop: int) -> tuple[int, float]:
        sub = [r for r in rows if r.get("min_hops", r.get("hop_depth", 0)) == hop]
        if not sub:
            return 0, 0.0
        c = sum(1 for r in sub if r.get("llm_label") == "CORRECT")
        p = sum(1 for r in sub if r.get("llm_label") == "PARTIAL")
        return len(sub), (c + 0.5 * p) / len(sub)

    for h in hops:
        n_a, a = acc_for(rows_by_cond.get("A", []), h)
        n_b, b = acc_for(rows_by_cond.get("B", []), h)
        n_c, c = acc_for(rows_by_cond.get("C", []), h)
        n = n_b or n_a or n_c
        lines.append(
            f"| {h} | {n} | {a:.3f} | {b:.3f} | {c:.3f} | "
            f"{(b - a) * 100:+.1f} | {(b - c) * 100:+.1f} |"
        )
    lines.append("")

    (out / "summary_llm_judge.md").write_text("\n".join(lines) + "\n")


# --- main ------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", nargs="*", default=DOMAINS)
    ap.add_argument("--conditions", nargs="*", default=["A", "B", "C"])
    ap.add_argument("--reader-model", default="gpt-4o-mini")
    ap.add_argument("--judge-model", default="gpt-4o-2024-08-06")
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--max-queries", type=int, default=None,
                    help="cap per condition per domain (smoke test)")
    ap.add_argument("--overwrite", action="store_true",
                    help="re-judge entries that already have llm_label")
    args = ap.parse_args()

    client = make_client()
    grand_total = 0
    grand_skipped = 0
    for domain in args.domains:
        print(f"\n=== {domain} ===")
        runs = load_runs_jsonl(domain)
        if not runs:
            print("  no runs.jsonl — run scripts/run_ckg_experiment.py first")
            continue
        # rehydrate context_strings (cheap)
        reattach_context_strings(domain, runs)
        for cond in args.conditions:
            print(f"  condition {cond} ...", flush=True)
            judged, skipped = judge_condition(
                domain,
                cond,
                client=client,
                reader_model=args.reader_model,
                judge_model=args.judge_model,
                workers=args.workers,
                max_queries=args.max_queries,
                overwrite=args.overwrite,
                runs_by_id=runs,
            )
            print(f"    judged={judged} skipped={skipped}")
            grand_total += judged
            grand_skipped += skipped
        write_judge_summary(domain)

    print(f"\ngrand total judged={grand_total} skipped={grand_skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
