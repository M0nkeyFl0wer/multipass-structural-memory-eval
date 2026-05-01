"""good-dog-corpus factual-integrity verification.

Companion to validate.py. Where validate.py checks structural integrity
(every entity has an edge, every edge has evidence, every required
frontmatter field is present), verify.py checks factual-integrity
as-far-as-automation-can:

  - URL liveness via curl with a browser user-agent (catches dead links
    that a normal reader would also fail to fetch)
  - Cross-note canonical-name consistency on shared entity ids
  - Cross-note timestamp consistency on shared event ids
  - Numeric-claim extraction — surfaces every number with context, for
    human spot-check (automation cannot verify a number is correct,
    only surface it)
  - Quoted-text extraction — surfaces everything in "double quotes" in
    note bodies, for human spot-check against the live source URL

What this script CANNOT do, by design:

  - Verify that a quoted statement actually appears at the source URL.
    That requires fetching the source and string-matching against it,
    which the agent sandbox couldn't do reliably for many of the URLs
    we're using (FDA / NPR / CPR / others returned 403/404 to WebFetch
    while being live in browsers).
  - Detect plausibly-fabricated facts that don't trip a cross-reference.
    A made-up middle name, a wrong byline, a slightly-off date that
    doesn't appear in any other note — none of these surface here.
  - Validate causal claims or relationship claims that aren't anchored
    to a specific quotable phrase.

Read this script's output as a SURFACE for human review, not a clean
bill of health. The output is the list of facts the corpus claims; the
spot-checking those claims against live sources is the actual
verification step.

Usage:
    python sme/corpora/good-dog-corpus/verify.py
    python sme/corpora/good-dog-corpus/verify.py --skip-url-check
    python sme/corpora/good-dog-corpus/verify.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

CORPUS_ROOT = Path(__file__).resolve().parent
VAULT_PATH = CORPUS_ROOT / "vault"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0"
)

NUMERIC_RE = re.compile(
    r"(?<![\w.])"                       # not part of an identifier
    r"(\d{1,3}(?:,\d{3})+|\d+\.?\d*)"   # 1,234 or 1234 or 12.5
    r"(\s?(?:%|percent|reports?|cases?|stages?|notes?|days?|"
    r"weeks?|months?|years?|drawers?|edges?|entities?))?"
)

QUOTED_RE = re.compile(r'"([^"\n]{8,300})"')


def parse_note(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)), match.group(2)


def find_notes() -> list[Path]:
    return sorted(VAULT_PATH.rglob("*.md"))


def _curl(url: str, head: bool, timeout: int) -> tuple[int | None, str]:
    flags = ["-sIL"] if head else ["-sL", "-o", "/dev/null"]
    try:
        result = subprocess.run(
            [
                "curl",
                *flags,
                "-A",
                UA,
                "-m",
                str(timeout),
                "-w",
                "%{http_code}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        # When -sIL is used the body is the headers; -w writes the status
        # at the end. Take the trailing 3 digits as status.
        out = result.stdout.strip()
        # Status is the last 3-digit run-on digits in -w output.
        m = re.search(r"(\d{3})$", out)
        if m:
            return int(m.group(1)), out
        return None, f"unparseable curl output: {out!r}"
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    except Exception as e:  # noqa: BLE001
        return None, f"ERROR: {e}"


def curl_head(url: str, timeout: int = 15) -> tuple[str, int | None, str]:
    """Return (url, status_code, classification).

    Classifications:
      - "live": HEAD or GET returned 2xx/3xx
      - "live_get_fallback": HEAD failed (often 405 Method Not Allowed),
        GET returned 2xx/3xx
      - "blocked": 403 — likely anti-bot, assume live, flag for human
      - "dead": real failure (404 / timeout / etc)
    """
    head_status, _ = _curl(url, head=True, timeout=timeout)
    if head_status is not None and 200 <= head_status < 400:
        return url, head_status, "live"
    if head_status == 405 or (head_status is not None and 400 <= head_status < 500):
        get_status, _ = _curl(url, head=False, timeout=timeout)
        if get_status is not None and 200 <= get_status < 400:
            return url, get_status, "live_get_fallback"
        if get_status == 403:
            return url, 403, "blocked"
        return url, get_status, "dead"
    if head_status is None:
        return url, None, "dead"
    return url, head_status, "dead"


def url_liveness_check(notes: list[Path]) -> list[dict]:
    urls: dict[str, list[str]] = defaultdict(list)
    for path in notes:
        fm, _ = parse_note(path)
        url = fm.get("source_url")
        if url:
            urls[url].append(str(path.relative_to(CORPUS_ROOT)))

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(curl_head, u): u for u in urls}
        for fut in as_completed(futures):
            url, status, classification = fut.result()
            results.append(
                {
                    "url": url,
                    "status": status,
                    "classification": classification,
                    "notes": urls[url],
                    "live": classification in ("live", "live_get_fallback"),
                }
            )
    return sorted(
        results,
        key=lambda r: (r["classification"] == "dead", r["classification"], r["url"]),
    )


def cross_note_consistency(notes: list[Path]) -> list[dict]:
    """For each entity id used in multiple notes, surface any divergence
    on canonical name or first-seen timestamp."""
    by_id: dict[str, list[dict]] = defaultdict(list)
    for path in notes:
        fm, _ = parse_note(path)
        for ent in fm.get("entities", []):
            eid = ent.get("id")
            if not eid:
                continue
            by_id[eid].append(
                {
                    "note": str(path.relative_to(CORPUS_ROOT)),
                    "canonical": ent.get("canonical"),
                    "type": ent.get("type"),
                    "timestamp": ent.get("timestamp"),
                    "aliases": ent.get("aliases", []) or [],
                }
            )

    issues: list[dict] = []
    for eid, decls in by_id.items():
        if len(decls) < 2:
            continue
        canonicals = {d["canonical"] for d in decls if d["canonical"]}
        types = {d["type"] for d in decls if d["type"]}
        timestamps = {d["timestamp"] for d in decls if d["timestamp"]}
        if len(canonicals) > 1:
            issues.append(
                {
                    "entity_id": eid,
                    "kind": "canonical_disagreement",
                    "values": sorted(canonicals),
                    "decls": decls,
                }
            )
        if len(types) > 1:
            issues.append(
                {
                    "entity_id": eid,
                    "kind": "type_disagreement",
                    "values": sorted(types),
                    "decls": decls,
                }
            )
        if len(timestamps) > 1:
            issues.append(
                {
                    "entity_id": eid,
                    "kind": "timestamp_disagreement",
                    "values": sorted(timestamps),
                    "decls": decls,
                }
            )
    return issues


def extract_human_review_surface(notes: list[Path]) -> list[dict]:
    """Surface every numeric claim and every quoted phrase per note."""
    out = []
    for path in notes:
        fm, body = parse_note(path)
        rel = str(path.relative_to(CORPUS_ROOT))
        numbers = []
        for m in NUMERIC_RE.finditer(body):
            start, end = m.span()
            ctx_start = max(0, start - 60)
            ctx_end = min(len(body), end + 60)
            ctx = body[ctx_start:ctx_end].replace("\n", " ").strip()
            numbers.append({"number": m.group(0).strip(), "context": ctx})
        quotes = [q.strip() for q in QUOTED_RE.findall(body) if len(q) > 8]
        out.append(
            {
                "note": rel,
                "source_url": fm.get("source_url"),
                "source_date": fm.get("source_date"),
                "numbers": numbers[:30],  # cap per note
                "quotes": quotes[:20],
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-url-check", action="store_true")
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args()

    notes = find_notes()
    print(f"--- good-dog-corpus verify ---")
    print(f"notes scanned: {len(notes)}")

    report: dict = {"notes_scanned": len(notes)}

    print()
    print("=== Cross-note consistency ===")
    consistency_issues = cross_note_consistency(notes)
    report["consistency_issues"] = consistency_issues
    if not consistency_issues:
        print("OK — every shared entity id has consistent canonical, type, and timestamp.")
    else:
        for issue in consistency_issues:
            print(
                f"  {issue['kind']:25s} {issue['entity_id']:40s} {issue['values']}"
            )

    print()
    print("=== URL liveness ===")
    if args.skip_url_check:
        print("(skipped via --skip-url-check)")
        report["url_liveness"] = "skipped"
    else:
        url_results = url_liveness_check(notes)
        report["url_liveness"] = url_results
        cls_counts: dict[str, int] = defaultdict(int)
        for r in url_results:
            cls_counts[r["classification"]] += 1
        for cls in ("live", "live_get_fallback", "blocked", "dead"):
            if cls in cls_counts:
                print(f"  {cls:20s} {cls_counts[cls]} / {len(url_results)}")
        if cls_counts.get("blocked"):
            print()
            for r in url_results:
                if r["classification"] == "blocked":
                    print(f"  BLOCKED (HTTP 403, likely anti-bot — assume live) {r['url']}")
                    for n in r["notes"]:
                        print(f"      used by: {n}")
        if cls_counts.get("dead"):
            print()
            for r in url_results:
                if r["classification"] == "dead":
                    print(f"  DEAD ({r['status']}) {r['url']}")
                    for n in r["notes"]:
                        print(f"      used by: {n}")

    print()
    print("=== Human-review surface ===")
    review = extract_human_review_surface(notes)
    report["human_review_surface"] = review
    total_numbers = sum(len(n["numbers"]) for n in review)
    total_quotes = sum(len(n["quotes"]) for n in review)
    print(f"  notes: {len(review)}")
    print(f"  numeric claims surfaced: {total_numbers}")
    print(f"  quoted phrases surfaced: {total_quotes}")
    print(
        "  → use --json to dump the full surface; spot-check each "
        "claim against the cited source_url before any reading is "
        "treated as ground truth."
    )

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
        print(f"\nFull report: {args.json}")

    print()
    print(
        "REMINDER: this script surfaces facts for human review. It does "
        "NOT verify them against live sources. A clean run means no "
        "URL is dead and no entity disagrees with itself across notes — "
        "neither of which proves a fact in any note is correct."
    )

    # Exit code: 1 if URLs are dead OR consistency issues, else 0.
    bad_urls = (
        not args.skip_url_check
        and any(not r["live"] for r in report.get("url_liveness", []))
    )
    if consistency_issues or bad_urls:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
