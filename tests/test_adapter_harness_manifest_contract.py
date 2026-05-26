"""Regression test for the get_harness_manifest() ABC contract.

Closes the silent-AttributeError class entirely: every adapter class must
either inherit the base ABC default (returns []) or override it to return
a list. Tests at the class level (no instantiation) so adapters with
heavy network/disk constructors are still covered.

Upstream issue: M0nkeyFl0wer/multipass-structural-memory-eval#19.
"""

from __future__ import annotations

import inspect

from sme.adapters.base import SMEAdapter
from sme.adapters.familiar import FamiliarAdapter
from sme.adapters.flat_baseline import FlatBaselineAdapter
from sme.adapters.ladybugdb import LadybugDBAdapter
from sme.adapters.mempalace import MemPalaceAdapter
from sme.adapters.mempalace_daemon import MemPalaceDaemonAdapter
from sme.conditions.full_context import FullContextAdapter
from sme.conditions.karpathy_compiled import KarpathyCompiledAdapter

ADAPTER_CLASSES = [
    FamiliarAdapter,
    FlatBaselineAdapter,
    FullContextAdapter,
    KarpathyCompiledAdapter,
    LadybugDBAdapter,
    MemPalaceAdapter,
    MemPalaceDaemonAdapter,
]


def test_base_adapter_default_is_empty_list():
    """The ABC default must return an empty list, not raise."""

    class _MinimalAdapter(SMEAdapter):
        def ingest_corpus(self, corpus):
            return {
                "entities_created": 0,
                "edges_created": 0,
                "errors": [],
                "warnings": [],
            }

        def query(self, question):
            from sme.adapters.base import QueryResult

            return QueryResult(answer="")

        def get_graph_snapshot(self):
            return [], []

    assert _MinimalAdapter().get_harness_manifest() == []


def test_every_adapter_has_get_harness_manifest():
    """Each shipped adapter must resolve `get_harness_manifest` — either
    inherited from `SMEAdapter` (default `[]`) or overridden on the class.
    Catches the silent-AttributeError class at import time without needing
    to instantiate heavyweight adapters."""
    for cls in ADAPTER_CLASSES:
        method = getattr(cls, "get_harness_manifest", None)
        assert callable(method), (
            f"{cls.__name__} is missing get_harness_manifest entirely "
            f"(expected ABC default to be inherited)"
        )
        sig = inspect.signature(method)
        # One positional param: self. No required extras.
        params = list(sig.parameters.values())
        assert len(params) >= 1, f"{cls.__name__}.get_harness_manifest must take self"
        for p in params[1:]:
            assert p.default is not inspect.Parameter.empty or p.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ), (
                f"{cls.__name__}.get_harness_manifest must be callable with no "
                f"args beyond self; found required param {p.name!r}"
            )


def test_base_default_inherited_when_not_overridden():
    """Adapters that don't override should resolve to the ABC default."""
    for cls in ADAPTER_CLASSES:
        if "get_harness_manifest" not in cls.__dict__:
            assert cls.get_harness_manifest is SMEAdapter.get_harness_manifest, (
                f"{cls.__name__} did not override get_harness_manifest but "
                f"does not resolve to SMEAdapter.get_harness_manifest"
            )
