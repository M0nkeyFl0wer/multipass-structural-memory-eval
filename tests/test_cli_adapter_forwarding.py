"""Tests for the allowlist-based adapter registry in sme.cli.

Inverts the legacy drop-list pattern (PR #7 regression class) — see
M0nkeyFl0wer/multipass-structural-memory-eval#20. Each adapter declares
which kwargs it accepts via `_AdapterSpec.accepts`; unknown kwargs are
silently dropped at the registry boundary, so new CLI flags can't
break old adapters by drifting past stale drop-lists.
"""

from __future__ import annotations

from typing import Any

import pytest

from sme.cli import _ADAPTER_REGISTRY, _load_adapter, _registry_by_alias


class _StubAdapter:
    """Throw-away adapter that captures whatever kwargs reach it."""

    def __init__(self, **kwargs: Any) -> None:
        self.captured_kwargs = kwargs


@pytest.fixture
def stub_loader(monkeypatch):
    """Yield a helper that swaps an adapter's loader for a stub.

    `_AdapterSpec` is a frozen dataclass — `object.__setattr__` bypasses
    that, and this fixture restores the original loader on teardown so
    tests don't bleed mutations into each other.
    """
    restores: list[tuple[Any, Any]] = []

    def _patch(alias: str) -> None:
        spec = _registry_by_alias()[alias]
        restores.append((spec, spec.loader))
        object.__setattr__(spec, "loader", lambda: _StubAdapter)

    yield _patch

    for spec, original in restores:
        object.__setattr__(spec, "loader", original)


# ---------------------------------------------------------------------
# Registry shape checks


def test_unknown_adapter_raises():
    with pytest.raises(SystemExit, match="unknown adapter"):
        _load_adapter("does-not-exist")


def test_every_declared_alias_is_loadable_by_name():
    """All declared aliases route to a real spec."""
    aliases = [a for spec in _ADAPTER_REGISTRY for a in spec.aliases]
    by_alias = _registry_by_alias()
    for alias in aliases:
        assert alias in by_alias, f"alias {alias!r} not in registry index"


# ---------------------------------------------------------------------
# Core contract: rename, allowlist, None-strip, unknown-drop


@pytest.mark.parametrize("alias", ["ladybugdb", "ladybug"])
def test_ladybugdb_aliases_resolve(stub_loader, alias):
    stub_loader(alias)
    out = _load_adapter(alias, db_path="/tmp/x", read_only=True)
    assert isinstance(out, _StubAdapter)
    assert out.captured_kwargs["db_path"] == "/tmp/x"


def test_familiar_renames_api_url_to_base_url(stub_loader):
    stub_loader("familiar")
    out = _load_adapter("familiar", api_url="http://nowhere:1", timeout_s=1.0)
    assert out.captured_kwargs == {
        "base_url": "http://nowhere:1",
        "timeout_s": 1.0,
    }
    assert "api_url" not in out.captured_kwargs


def test_full_context_renames_db_path_to_vault_dir(stub_loader):
    stub_loader("full-context")
    out = _load_adapter("full-context", db_path="/tmp/vault", read_only=True)
    assert out.captured_kwargs == {
        "vault_dir": "/tmp/vault",
        "read_only": True,
    }
    assert "db_path" not in out.captured_kwargs


def test_karpathy_compiled_renames_db_path_to_compiled_dir(stub_loader):
    stub_loader("karpathy-compiled")
    out = _load_adapter("karpathy-compiled", db_path="/tmp/wiki")
    assert out.captured_kwargs == {"compiled_dir": "/tmp/wiki"}


def test_rlm_keeps_kind_and_api_url(stub_loader):
    """`rlm` accepts `kind` — it forwards into mempalace_search /search."""
    stub_loader("rlm")
    out = _load_adapter(
        "rlm",
        api_url="http://disks:8085",
        api_key="abc",
        kind="content",
        include_node_tables=["X"],
        db_path="/tmp/db",
    )
    assert out.captured_kwargs == {
        "api_url": "http://disks:8085",
        "api_key": "abc",
        "kind": "content",
    }


def test_unknown_kwargs_silently_dropped(stub_loader):
    """The PR #7 class of regression: a new CLI flag must not blow up
    an old adapter just by being present in the kwargs bag."""
    stub_loader("familiar")
    out = _load_adapter(
        "familiar",
        api_url="http://nowhere:1",
        # Every one of these belongs to *some* other adapter and must
        # not reach FamiliarAdapter's constructor.
        include_node_tables=["X"],
        include_edge_tables=["Y"],
        auto_discover=True,
        kg_path="/tmp/kg.sqlite3",
        collection_name="drawers",
        default_query_mode="hybrid",
        db_path="/tmp/db",
        buffer_pool_size=128,
        api_key="secret",
        kind="content",
        read_only=True,
        # Invented future flag that doesn't exist anywhere yet.
        some_future_flag_that_doesnt_exist=42,
    )
    assert out.captured_kwargs == {"base_url": "http://nowhere:1"}


def test_none_valued_kwargs_are_stripped(stub_loader):
    """`None` means 'use the adapter default' — never forward as-is."""
    stub_loader("flat")
    out = _load_adapter(
        "flat",
        db_path="/tmp/db",
        read_only=True,
        collection_name=None,
        n_results=None,
    )
    assert out.captured_kwargs == {"db_path": "/tmp/db", "read_only": True}
    assert "collection_name" not in out.captured_kwargs
    assert "n_results" not in out.captured_kwargs


def test_mempalace_daemon_drops_db_path(stub_loader):
    """Daemon adapter has a legacy `db_path` constructor arg that's a
    no-op — old drop-list dropped it; preserve that behavior."""
    stub_loader("mempalace-daemon")
    out = _load_adapter(
        "mempalace-daemon",
        api_url="http://localhost:8085",
        api_key="key",
        kind="content",
        db_path="/tmp/should-be-dropped",
        buffer_pool_size=128,
    )
    assert "db_path" not in out.captured_kwargs
    assert "buffer_pool_size" not in out.captured_kwargs
    assert out.captured_kwargs == {
        "api_url": "http://localhost:8085",
        "api_key": "key",
        "kind": "content",
    }


def test_mempalace_keeps_kg_path_and_collection_name(stub_loader):
    stub_loader("mempalace")
    out = _load_adapter(
        "mempalace",
        db_path="/tmp/chroma",
        kg_path="/tmp/kg.sqlite3",
        collection_name="drawers",
        read_only=True,
        # Should be dropped — not in mempalace's accepts
        api_url="http://x",
        kind="content",
    )
    assert out.captured_kwargs == {
        "db_path": "/tmp/chroma",
        "kg_path": "/tmp/kg.sqlite3",
        "collection_name": "drawers",
        "read_only": True,
    }


# ---------------------------------------------------------------------
# Integration: real construction for lightweight adapters


def test_familiar_real_construction():
    """FamiliarAdapter has no heavy deps — verify the registry routes
    correctly all the way through to the real constructor."""
    adapter = _load_adapter("familiar", api_url="http://nowhere:1", timeout_s=1.0)
    assert type(adapter).__name__ == "FamiliarAdapter"
    assert adapter.base_url == "http://nowhere:1"
    assert adapter.timeout_s == 1.0


def test_full_context_real_construction(tmp_path):
    """FullContextAdapter only validates the vault path exists."""
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = _load_adapter("full-context", db_path=str(vault))
    assert type(adapter).__name__ == "FullContextAdapter"
    assert adapter.vault_dir == vault


# ---------------------------------------------------------------------
# Sanity: rename/accepts internal consistency


def test_rename_targets_are_in_accepts():
    """A spec that renames `foo` → `bar` must accept `bar`. Otherwise
    the registry would rename a kwarg only to immediately drop it."""
    for spec in _ADAPTER_REGISTRY:
        for src, dst in spec.rename.items():
            assert dst in spec.accepts, (
                f"adapter {spec.aliases[0]!r} renames {src!r} → {dst!r} "
                f"but {dst!r} is not in accepts={sorted(spec.accepts)}"
            )


def test_rename_sources_are_not_in_accepts():
    """If `foo` renames to `bar`, `foo` itself shouldn't also appear
    in accepts — that creates ambiguity about which the adapter wants."""
    for spec in _ADAPTER_REGISTRY:
        for src in spec.rename:
            assert src not in spec.accepts, (
                f"adapter {spec.aliases[0]!r} both renames {src!r} away "
                f"and lists it in accepts — pick one"
            )
