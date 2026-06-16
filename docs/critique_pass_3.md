# Critique Pass 3 — Remaining Maintainer Findings

Branch: `ckg-benchmark-experiment`
Status after cleanup batch: 501 passed, 8 skipped

This pass reviewed the updated judge cache, judge wrapper, deterministic
overlays, and test isolation fixes after the high/medium findings from
`docs/critique_pass_2.md` were addressed.

## Result

No remaining medium/high severity findings were found in the touched surfaces.
The remaining items are low-severity portability or polish issues.

## Remaining Low-Severity Items

### 1. Cache directory is Linux-centric

**File:** `sme/eval/judge_cache.py`

`DEFAULT_CACHE_DIR = Path.home() / ".cache" / "sme-eval" / "judge"` is fine
on Linux but not idiomatic on macOS or Windows.

**Why low:** The project is currently developed/tested on Linux and the path is
explicit and harmless. Portability can wait until there are non-Linux users.

**Future fix:** Use `platformdirs.user_cache_dir("sme-eval")` if adding a small
dependency is acceptable.

### 2. Cache eviction scans files on every write

**File:** `sme/eval/judge_cache.py`

`set_cache()` calls `_maybe_evict(cache_dir)` after every successful write. Once
the cache is large, this performs an `rglob("*.json")` scan on every uncached
judge call.

**Why low:** Judge API calls dominate runtime, and the threshold is 5000 files,
so this is unlikely to matter outside very large local batches.

**Future fix:** Only check eviction every N writes, or persist a small cache
metadata file with count/last-eviction state.

### 3. `Optional[Any]` remains in public signatures

**Files:** `sme/eval/judge_base.py`, `sme/eval/faithfulness.py`,
`sme/eval/answer_relevancy.py`, `sme/eval/longmemeval_judge.py`

Several signatures use `Optional[Any]` for injected SDK clients.

**Why low:** This is stylistic; it does not affect runtime behavior.

**Future fix:** Use `Any | None` or provider-specific Protocols if stricter type
checking becomes a goal.

### 4. Score type changed to include `None` on judge failure

**Files:** `sme/eval/faithfulness.py`, `sme/eval/answer_relevancy.py`

`score` now returns `None` for "could not judge" instead of `0.0`. This fixes
the conflation bug, but it is a small API behavior change for direct callers.

**Why low:** CLI and tests handle it, and this behavior is semantically more
correct. No persisted data or external package consumers are known.

**Future fix:** If this becomes a published API, document the return schema in a
formal typed model.

## Why Earlier Tests Missed The Higher-Severity Issues

- The prompt boundary bug was hidden because mocked clients do not grade prompt
  quality, and LLMs are forgiving enough to parse malformed prompt joins.
- Cache growth and atomicity are operational properties, not single-run behavior.
- Import-time `clear_cache()` is only dangerous when module collection order or
  shared cache state changes; single-process pytest often masks it.
- Retry broadness was masked because fake retry clients raised `RuntimeError`,
  which old code retried by accident. The new tests use `ConnectionError` for
  retryable failures.
