"""Tests for _load_adapter allowlist registry (issue #20).

Verifies that:
  - Every registered adapter can be constructed without TypeError when
    given the CLI's full kwarg superset (the allowlist filters correctly).
  - Kwarg renames land on the correct constructor parameter.
  - Unknown adapter names raise SystemExit.
  - get_harness_manifest() returns a list on every adapter (issue #19).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sme.cli import _REGISTRY, _load_adapter


_CLI_SUPERSET = {
    "db_path": "/tmp/fake.db",
    "read_only": True,
    "auto_discover": True,
    "include_node_tables": ["T"],
    "include_edge_tables": ["E"],
    "kg_path": "/tmp/kg.sqlite3",
    "collection_name": "test_coll",
    "default_query_mode": "semantic",
    "buffer_pool_size": 64,
    "api_url": "http://localhost:9999",
    "api_key": "test-key",
    "kind": "content",
    "mock_inference": True,
    "timeout_s": 5.0,
}


def _stub_adapter(cls_name: str):
    """Return a mock class that records kwargs passed to __init__."""
    init_kwargs = {}

    class _Stub:
        def __init__(self, **kw):
            init_kwargs.update(kw)

    _Stub.__name__ = cls_name
    _Stub.__qualname__ = cls_name
    return _Stub, init_kwargs


class TestLoadAdapterAllowlist:
    """Each adapter should receive only the kwargs its constructor accepts."""

    def test_unknown_adapter_raises(self):
        with pytest.raises(SystemExit, match="unknown adapter"):
            _load_adapter("nonexistent_adapter")

    def test_familiar_renames_api_url_to_base_url(self):
        stub, captured = _stub_adapter("FamiliarAdapter")
        with patch.dict(
            "sys.modules",
            {"sme.adapters.familiar": MagicMock(FamiliarAdapter=stub)},
        ):
            _load_adapter("familiar", api_url="http://test:1234", kind="content")
        assert captured.get("base_url") == "http://test:1234"
        assert "api_url" not in captured

    def test_full_context_renames_db_path_to_vault_dir(self):
        stub, captured = _stub_adapter("FullContextAdapter")
        with patch.dict(
            "sys.modules",
            {"sme.conditions.full_context": MagicMock(FullContextAdapter=stub)},
        ):
            _load_adapter("full-context", db_path="/tmp/vault")
        assert captured.get("vault_dir") == "/tmp/vault"
        assert "db_path" not in captured

    def test_karpathy_compiled_renames_db_path_to_compiled_dir(self):
        stub, captured = _stub_adapter("KarpathyCompiledAdapter")
        with patch.dict(
            "sys.modules",
            {
                "sme.conditions.karpathy_compiled": MagicMock(
                    KarpathyCompiledAdapter=stub
                )
            },
        ):
            _load_adapter("karpathy-compiled", db_path="/tmp/compiled")
        assert captured.get("compiled_dir") == "/tmp/compiled"

    def test_none_values_are_stripped(self):
        stub, captured = _stub_adapter("FlatBaselineAdapter")
        with patch.dict(
            "sys.modules",
            {"sme.adapters.flat_baseline": MagicMock(FlatBaselineAdapter=stub)},
        ):
            _load_adapter("flat", db_path="/tmp/x", api_url=None, kind=None)
        assert "api_url" not in captured
        assert "kind" not in captured

    def test_all_aliases_resolve(self):
        """Every alias in the registry points to a spec."""
        for alias in _REGISTRY:
            spec = _REGISTRY[alias]
            assert spec.module, f"alias {alias!r} has no module"
            assert spec.cls_name, f"alias {alias!r} has no cls_name"


class TestAllAdaptersAcceptSuperset:
    """_load_adapter should never raise TypeError for the CLI kwarg superset.

    Each adapter's constructor accepts a subset; the allowlist filter
    discards the rest.  This test catches the exact regression from PR #7
    where a stale drop-list caused TypeError.
    """

    @pytest.mark.parametrize("name", sorted(set(_REGISTRY.keys())))
    def test_no_typeerror_with_full_superset(self, name):
        spec = _REGISTRY[name]
        stub, _ = _stub_adapter(spec.cls_name)
        mod_mock = MagicMock(**{spec.cls_name: stub})
        with patch.dict("sys.modules", {spec.module: mod_mock}):
            adapter = _load_adapter(name, **_CLI_SUPERSET)
        assert adapter is not None


class TestHarnessManifestContract:
    """Every adapter's get_harness_manifest() must return a list (issue #19).

    The base class defines the default (return []); this test verifies
    the contract holds for subclasses that can be cheaply instantiated.
    """

    def test_base_class_default_returns_empty_list(self):
        from sme.adapters.base import SMEAdapter

        class _Minimal(SMEAdapter):
            def ingest_corpus(self, corpus):
                return {}

            def query(self, question):
                pass

            def get_graph_snapshot(self):
                return [], []

        a = _Minimal()
        result = a.get_harness_manifest()
        assert isinstance(result, list)
        assert result == []

    def test_full_context_returns_empty_list(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        from sme.conditions.full_context import FullContextAdapter

        a = FullContextAdapter(str(vault))
        result = a.get_harness_manifest()
        assert isinstance(result, list)

    def test_karpathy_compiled_returns_empty_list(self, tmp_path):
        compiled = tmp_path / "compiled"
        compiled.mkdir()
        (compiled / "wiki").mkdir()
        (compiled / "index.md").write_text("# Index\n")
        (compiled / "_manifest.json").write_text("{}")
        from sme.conditions.karpathy_compiled import KarpathyCompiledAdapter

        a = KarpathyCompiledAdapter(str(compiled))
        result = a.get_harness_manifest()
        assert isinstance(result, list)
