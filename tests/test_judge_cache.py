"""Tests for sme.eval.judge_cache."""
from __future__ import annotations

import json
import time
from pathlib import Path


from sme.eval.judge_cache import (
    DEFAULT_TTL_SECONDS,
    _cache_key,
    clear_cache,
    evict_expired,
    get_cached,
    set_cache,
)


# --- helpers --------------------------------------------------------------


def _write_backdated(cache_dir: Path, key: str, result: dict, age_seconds: int) -> Path:
    """Manually write a cache entry with a backdated timestamp."""
    path = cache_dir / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"result": result, "cached_at": time.time() - age_seconds}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --- cache key ------------------------------------------------------------


def test_cache_key_stability_same_inputs():
    key1 = _cache_key("r1", "b1", "m1", "p1")
    key2 = _cache_key("r1", "b1", "m1", "p1")
    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex


def test_cache_key_different_inputs():
    key1 = _cache_key("r1", "b1", "m1", "p1")
    key2 = _cache_key("r1", "b2", "m1", "p1")
    assert key1 != key2


def test_cache_key_includes_rubric_version():
    key1 = _cache_key("r1", "b1", "m1", "p1", rubric_version="v1")
    key2 = _cache_key("r1", "b1", "m1", "p1", rubric_version="v2")
    assert key1 != key2


# --- round-trip -----------------------------------------------------------


def test_round_trip(tmp_path: Path):
    result = {"score": 42, "rationale": "looks good"}
    set_cache(
        result,
        rubric="info-extraction",
        body="What did I buy?",
        model="gpt-4o",
        provider="openai",
        cache_dir=tmp_path,
    )
    cached = get_cached(
        rubric="info-extraction",
        body="What did I buy?",
        model="gpt-4o",
        provider="openai",
        cache_dir=tmp_path,
    )
    assert cached == result


def test_cache_miss(tmp_path: Path):
    cached = get_cached(
        rubric="info-extraction",
        body="unknown body",
        model="gpt-4o",
        provider="openai",
        cache_dir=tmp_path,
    )
    assert cached is None


# --- TTL expiry -----------------------------------------------------------


def test_ttl_expiry(tmp_path: Path):
    key = _cache_key("r", "b", "m", "p")
    _write_backdated(
        tmp_path,
        key,
        result={"score": 99},
        age_seconds=DEFAULT_TTL_SECONDS + 1,
    )
    cached = get_cached("r", "b", "m", "p", cache_dir=tmp_path)
    assert cached is None


def test_ttl_not_expired(tmp_path: Path):
    key = _cache_key("r", "b", "m", "p")
    _write_backdated(
        tmp_path,
        key,
        result={"score": 77},
        age_seconds=DEFAULT_TTL_SECONDS - 1,
    )
    cached = get_cached("r", "b", "m", "p", cache_dir=tmp_path)
    assert cached == {"score": 77}


# --- eviction --------------------------------------------------------------


def test_evict_expired_removes_old_files_and_returns_count(tmp_path: Path):
    key_old = _cache_key("r1", "b1", "m1", "p1")
    key_fresh = _cache_key("r2", "b2", "m2", "p2")

    _write_backdated(tmp_path, key_old, {"score": 1}, age_seconds=DEFAULT_TTL_SECONDS + 10)
    _write_backdated(tmp_path, key_fresh, {"score": 2}, age_seconds=DEFAULT_TTL_SECONDS - 10)

    removed = evict_expired(cache_dir=tmp_path)
    assert removed == 1

    assert get_cached("r1", "b1", "m1", "p1", cache_dir=tmp_path) is None
    assert get_cached("r2", "b2", "m2", "p2", cache_dir=tmp_path) == {"score": 2}


def test_evict_expired_on_empty_dir_returns_zero(tmp_path: Path):
    assert evict_expired(cache_dir=tmp_path) == 0


def test_evict_expired_on_default_dir_when_missing():
    # Ensure the default path does not exist for this test.
    assert evict_expired() == 0


# --- clear ----------------------------------------------------------------


def test_clear_cache_removes_all_files(tmp_path: Path):
    set_cache({"score": 1}, "r1", "b1", "m1", "p1", cache_dir=tmp_path)
    set_cache({"score": 2}, "r2", "b2", "m2", "p2", cache_dir=tmp_path)

    clear_cache(cache_dir=tmp_path)

    assert get_cached("r1", "b1", "m1", "p1", cache_dir=tmp_path) is None
    assert get_cached("r2", "b2", "m2", "p2", cache_dir=tmp_path) is None
    assert not any(tmp_path.iterdir())


def test_clear_cache_on_empty_dir_is_noop(tmp_path: Path):
    clear_cache(cache_dir=tmp_path)
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


# --- directory creation ----------------------------------------------------


def test_set_cache_creates_nested_directories(tmp_path: Path):
    set_cache({"score": 5}, "r", "b", "m", "p", cache_dir=tmp_path)
    key = _cache_key("r", "b", "m", "p")
    expected_file = tmp_path / key[:2] / f"{key}.json"
    assert expected_file.exists()


# --- malformed entry handling ---------------------------------------------


def test_get_cached_returns_none_for_malformed_file(tmp_path: Path):
    key = _cache_key("r", "b", "m", "p")
    path = tmp_path / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")

    assert get_cached("r", "b", "m", "p", cache_dir=tmp_path) is None


def test_get_cached_returns_none_for_missing_cached_at(tmp_path: Path):
    key = _cache_key("r", "b", "m", "p")
    path = tmp_path / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"result": {}}), encoding="utf-8")

    assert get_cached("r", "b", "m", "p", cache_dir=tmp_path) is None
