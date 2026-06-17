# Critique Pass 2 — Experienced Dev / Repo Maintainer View

Branch: `ckg-benchmark-experiment` (HEAD `54b7588`)
Full test suite: 497 passed, 8 skipped (green)

---

## Critical — Fix Before Merge

### 1. `_call_openai_compat` concatenates rubric + body without separator
**File:** `sme/eval/judge_base.py:131`
**What:** `combined = rubric + body` — if the rubric doesn't end with whitespace and the body doesn't start with whitespace, the prompt is malformed.
**Evidence:**
- Faithfulness rubric ends with `...UNSUPPORTED"}]}` and body starts with `CONTEXT:` → produces `...UNSUPPORTED"}]}CONTEXT:`
- Answer relevancy rubric ends with `..."<one sentence>"}` and body starts with `QUESTION:` → produces `..."<one sentence>"}QUESTION:`
**Impact:** The LLM still usually parses it, but it's a real correctness bug. The Anthropic path (system + user separation) is correct; OpenAI/OpenRouter path is not.
**Fix:** `combined = rubric.rstrip() + "\n\n" + body.lstrip()`

### 2. `_retry` catches `Exception` — retries on programming bugs
**File:** `sme/eval/judge_base.py:106`
**What:** `except Exception` catches `ValueError`, `TypeError`, `AttributeError` from real bugs (e.g., a typo in `_do()`), not just transient API failures.
**Impact:** A bug in the calling code is retried 3× with backoff, making debugging much harder. You only want to retry on connection errors, rate limits, and timeouts.
**Fix:** Catch only the SDK-specific exception types (`openai.APIError`, `openai.RateLimitError`, `anthropic.APIError`, etc.) and `ConnectionError`/`TimeoutError`.

---

## High — Fix Before Production Load

### 3. Cache unbounded growth — `evict_expired` exists but is never called
**File:** `sme/eval/judge_cache.py:148`
**What:** `evict_expired()` is defined and tested, but no production code calls it. The 30-day TTL is checked on *read* (cache miss for expired entries), but stale files are never deleted.
**Impact:** Running 10K unique questions creates 10K files under `~/.cache/sme-eval/judge/`. Over months this becomes disk pressure.
**Fix:** Call `evict_expired()` from `set_cache()` when the cache exceeds a threshold, or add a `--clear-judge-cache` CLI flag.

### 4. `clear_cache()` at module import time in 4 test modules
**Files:** `tests/test_faithfulness.py`, `tests/test_answer_relevancy.py`, `tests/test_cross_validate_longmemeval.py`
**What:** `clear_cache()` runs when pytest *imports* the module, not when the test *runs*. This is a side effect at import time — an anti-pattern.
**Impact:**
- If pytest-xdist or any parallel runner is used, tests race on the shared `~/.cache/sme-eval/judge` directory.
- If test collection order changes, `clear_cache()` may run between tests in another module, causing surprising failures.
**Fix:** Move `clear_cache()` into a pytest fixture or into each test function. Alternatively, pass `cache_dir=tmp_path` to every `set_cache`/`get_cached` call in tests.

### 5. Cache writes are not atomic — half-written files on crash
**File:** `sme/eval/judge_cache.py:120-123`
**What:** `with path.open("w", ...) as fh: json.dump(payload, fh)` — if the process crashes during the write, the file is truncated/corrupted.
**Impact:** Next read gets a malformed JSON file, logs a warning, and treats it as a cache miss. Not catastrophic, but unnecessary noise.
**Fix:** Write to a temp file in the same directory, then `os.replace(temp_path, path)`.

---

## Medium — Polish & Defensive Programming

### 6. Score conflation on parse errors
**Files:** `sme/eval/faithfulness.py:78`, `sme/eval/answer_relevancy.py:60`
**What:** On JSON parse failure, both functions return `score: 0.0`. This conflates "the answer is unfaithful" with "we couldn't judge at all."
**Impact:** Downstream consumers that read the raw dict (not the CLI's `None` handling) will think the score is 0.0.
**Fix:** Return `score: None` on parse errors, not `0.0`. The CLI already handles this correctly.

### 7. `entity_id_overlap` substring matching is case-sensitive
**File:** `sme/eval/deterministic_overlays.py:42-45`
**What:** `source in entity.id` uses Python's case-sensitive `in` operator.
**Impact:** Expected source `"Paris"` won't match entity name `"paris"`.
**Fix:** Case-normalize both sides: `source.lower() in entity.id.lower() or source.lower() in entity.name.lower()`.

### 8. No test for token_utilization pass-through detection
**File:** `tests/test_deterministic_overlays.py`
**What:** The `answer == context_string` → `None` fix from `54b7588` has zero test coverage.
**Fix:** Add a test that creates a `QueryResult(answer="same", context_string="same")` and asserts `token_utilization(result) is None`.

### 9. Logging at wrong level creates noise in CI
**Files:** `sme/eval/judge_base.py:108`, `sme/eval/judge_cache.py:84`
**What:** Transient cache read failures and API retry attempts log at `WARNING` level.
**Impact:** In CI runs without API keys, every skipped judge call emits a WARNING line. This trains users to ignore warnings.
**Fix:** Downgrade transient/retryable events to `INFO` or `DEBUG`. Reserve `WARNING` for actionable problems.

---

## Low — Nice to Have

### 10. Hardcoded `~/.cache` path is not portable
**File:** `sme/eval/judge_cache.py:43`
**What:** `Path.home() / ".cache" / "sme-eval" / "judge"` is Linux-centric. macOS uses `~/Library/Caches/`, Windows uses `%LOCALAPPDATA%`.
**Fix:** Use `platformdirs.user_cache_dir("sme-eval", "sme-eval")` (add `platformdirs` as an optional dep).

### 11. Cache key hashes the entire rubric + body
**File:** `sme/eval/judge_cache.py:55`
**What:** `_cache_key` does `sha256(f"{rubric}|{body}|{model}|{provider}|{rubric_version}")`. For 100K-char contexts (LongMemEval), this is ~100KB of string + hash computation on every cache check.
**Impact:** Small but measurable latency on every judge call.
**Fix:** Acceptable for now; not worth optimizing unless profiling shows it's hot.

### 12. `Optional[Any]` is a type-smell
**Files:** `sme/eval/judge_base.py:83`, `sme/eval/faithfulness.py:20`
**What:** `Optional[Any]` is redundant — `Any` already includes `None`.
**Fix:** Use `Any | None` (Python 3.10+) or just `Any` if the caller always handles None.

---

## Summary

| # | Issue | Severity | Effort | File |
|---|-------|----------|--------|------|
| 1 | rubric+body concatenation missing separator | **Critical** | 1 line | `judge_base.py:131` |
| 2 | `_retry` catches all `Exception` | **Critical** | ~10 lines | `judge_base.py:106` |
| 3 | Cache unbounded growth (evict_expired never called) | High | ~5 lines | `judge_cache.py` + `cli.py` |
| 4 | `clear_cache()` at import time | High | ~10 lines | 4 test files |
| 5 | Non-atomic cache writes | High | ~5 lines | `judge_cache.py:120` |
| 6 | Score conflation on parse errors | Medium | 2 lines | `faithfulness.py`, `answer_relevancy.py` |
| 7 | Case-sensitive entity_id_overlap | Medium | 2 lines | `deterministic_overlays.py` |
| 8 | Missing test for pass-through detection | Medium | ~5 lines | `test_deterministic_overlays.py` |
| 9 | Logging at wrong level | Medium | ~4 lines | `judge_base.py`, `judge_cache.py` |
| 10 | Non-portable cache path | Low | 1 line | `judge_cache.py:43` |

---

**Recommended next two:** #1 (concatenation bug) and #2 (too-broad retry) — both are real correctness bugs that affect every judge call on the OpenAI/OpenRouter path.
