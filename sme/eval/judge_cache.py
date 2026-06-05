"""Disk-based cache for LLM judge API calls.

Iterative development on SME's evaluation pipelines repeatedly calls the
same judge prompts.  This module provides a transparent, zero-dependency
cache layer so those calls hit disk instead of the API after the first run.

Cache layout
------------

Files are stored as ``{cache_dir}/{key[:2]}/{key}.json``.  The two-character
prefix shards the directory so a large cache does not create a single flat
folder with millions of entries.

Each file is a JSON object::

    {"result": <dict>, "cached_at": <float (unix timestamp)>}

Expiry
------

The default TTL is 30 days.  Callers can override per ``get_cached`` / ``evict_expired``
invocation.  A missing, malformed, or expired entry is treated as a cache miss
and returns ``None``.

Thread / process safety
-----------------------

Writes are atomic (temp file in the same directory, then ``os.replace``), but
this module does not use file locking.  In practice SME's judge pipeline is
single-process for a given cache directory; concurrent writers for the same key
are last-write-wins.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "sme-eval" / "judge"
DEFAULT_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def _cache_key(
    rubric: str,
    body: str,
    model: str,
    provider: str,
    rubric_version: str = "v1",
) -> str:
    """Stable SHA-256 hash of the call inputs."""
    payload = f"{rubric}|{body}|{model}|{provider}|{rubric_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(key: str, cache_dir: Path) -> Path:
    return cache_dir / key[:2] / f"{key}.json"


def get_cached(
    rubric: str,
    body: str,
    model: str,
    provider: str,
    *,
    cache_dir: Path | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    rubric_version: str = "v1",
) -> dict | None:
    """Return cached judge result if present and not expired."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    key = _cache_key(rubric, body, model, provider, rubric_version)
    path = _cache_path(key, cache_dir)

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        log.info("judge_cache: unreadable entry %s: %s", path, exc)
        return None

    if not isinstance(data, dict) or "cached_at" not in data or "result" not in data:
        log.info("judge_cache: malformed entry %s", path)
        return None

    if time.time() - data["cached_at"] > ttl_seconds:
        return None

    return data["result"]


def set_cache(
    result: dict,
    rubric: str,
    body: str,
    model: str,
    provider: str,
    *,
    cache_dir: Path | None = None,
    rubric_version: str = "v1",
) -> None:
    """Write judge result to disk cache."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    key = _cache_key(rubric, body, model, provider, rubric_version)
    path = _cache_path(key, cache_dir)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("judge_cache: cannot create directory %s: %s", path.parent, exc)
        return

    payload = {"result": result, "cached_at": time.time()}

    # Atomic write: write to a temp file in the same directory, then rename.
    # This prevents half-written files if the process crashes mid-write.
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp_path, path)
    except OSError as exc:
        log.warning("judge_cache: cannot write %s: %s", path, exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return

    # Threshold-based eviction: when the cache grows beyond a reasonable
    # size, trim the oldest entries.  This is a coarse guard against
    # unbounded growth — a cron job or explicit `--clear-judge-cache`
    # CLI flag is still the right way to do full housekeeping.
    _maybe_evict(cache_dir)


# Coarse threshold: when the cache exceeds this many files, evict the oldest
# 20 %.  Chosen to be large enough for a full LongMemEval run (~500 q)
# without triggering, small enough to prevent multi-gigabyte caches.
_MAX_CACHE_FILES = 5000


def _maybe_evict(cache_dir: Path) -> None:
    """Evict oldest entries if the cache is above the threshold."""
    if not cache_dir.exists():
        return
    entries = list(cache_dir.rglob("*.json"))
    if len(entries) <= _MAX_CACHE_FILES:
        return
    # Sort by mtime (oldest first) and remove the oldest 20 %.
    try:
        entries.sort(key=lambda p: p.stat().st_mtime)
    except OSError as exc:
        log.info("judge_cache: eviction skipped after stat failure: %s", exc)
        return
    to_remove = int(len(entries) * 0.2)
    removed = 0
    for path in entries[:to_remove]:
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    log.info("judge_cache: evicted %d/%d oldest entries (threshold=%d)",
             removed, len(entries), _MAX_CACHE_FILES)


def clear_cache(cache_dir: Path | None = None) -> None:
    """Remove all cached entries."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    if not cache_dir.exists():
        return

    for path in cache_dir.rglob("*.json"):
        try:
            path.unlink()
        except OSError as exc:
            log.warning("judge_cache: cannot remove %s: %s", path, exc)

    # Clean up empty shard directories.
    for shard in cache_dir.iterdir():
        if shard.is_dir():
            try:
                shard.rmdir()
            except OSError:
                pass  # directory not empty — ignore


def evict_expired(
    cache_dir: Path | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> int:
    """Remove expired entries.  Returns count removed."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    if not cache_dir.exists():
        return 0

    now = time.time()
    removed = 0

    for path in cache_dir.rglob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            # Malformed or unreadable — treat as expired.
            try:
                path.unlink()
            except OSError as exc:
                log.warning("judge_cache: cannot remove %s: %s", path, exc)
                continue
            removed += 1
            continue

        cached_at = data.get("cached_at")
        if cached_at is None or now - cached_at > ttl_seconds:
            try:
                path.unlink()
            except OSError as exc:
                log.warning("judge_cache: cannot remove %s: %s", path, exc)
                continue
            removed += 1

    # Clean up empty shard directories.
    for shard in cache_dir.iterdir():
        if shard.is_dir():
            try:
                shard.rmdir()
            except OSError:
                pass

    return removed
