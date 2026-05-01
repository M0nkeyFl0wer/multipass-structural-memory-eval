"""Tests for sme.conditions.karpathy_compiled.KarpathyCompiledAdapter.

The adapter is a pure read-side component — it consumes the on-disk
output of ``wiki_compiler.compile_vault`` and never calls an LLM. Tests
construct the on-disk shape directly rather than running the compiler.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sme.conditions.karpathy_compiled import KarpathyCompiledAdapter


def _setup_compiled(tmp_path: Path, *, with_index: bool = True, with_wiki: bool = True):
    """Build a compiled-vault directory layout for tests."""
    out = tmp_path / "compiled"
    out.mkdir()
    if with_index:
        (out / "index.md").write_text("# Index\n\n- alpha\n- beta\n")
    if with_wiki:
        wiki = out / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("Article A body.")
        (wiki / "b.md").write_text("Article B body.")
        (wiki / "research__deep.md").write_text("Deep research summary.")
    return out


# --- Construction ----------------------------------------------------


def test_missing_dir_raises(tmp_path):
    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        KarpathyCompiledAdapter(tmp_path / "nope")


def test_empty_dir_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="neither index.md nor wiki/"):
        KarpathyCompiledAdapter(empty)


def test_index_only_construction_succeeds(tmp_path):
    out = _setup_compiled(tmp_path, with_index=True, with_wiki=False)
    adapter = KarpathyCompiledAdapter(out)
    result = adapter.query("anything")
    assert "# Index" in result.context_string
    assert "alpha" in result.context_string


def test_wiki_only_construction_succeeds(tmp_path):
    out = _setup_compiled(tmp_path, with_index=False, with_wiki=True)
    adapter = KarpathyCompiledAdapter(out)
    result = adapter.query("anything")
    assert "Article A body." in result.context_string
    assert "Article B body." in result.context_string


# --- query() --------------------------------------------------------


def test_query_combines_index_and_wiki(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    result = adapter.query("ignored question")
    assert "--- index.md ---" in result.context_string
    assert "--- wiki/a.md ---" in result.context_string
    assert "--- wiki/b.md ---" in result.context_string
    assert "--- wiki/research__deep.md ---" in result.context_string


def test_query_ignores_n_results(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    result_a = adapter.query("q", n_results=1)
    result_b = adapter.query("q", n_results=100)
    assert result_a.context_string == result_b.context_string


def test_retrieval_path_records_diagnostic_fields(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    result = adapter.query("q")
    path = result.retrieval_path
    assert any("karpathy_compiled" in p for p in path)
    assert any(str(out) in p for p in path)
    assert any("n_articles=3" in p for p in path)
    assert any("total_chars=" in p for p in path)


def test_include_wiki_false_returns_index_only(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out, include_wiki=False)
    result = adapter.query("q")
    assert "# Index" in result.context_string
    assert "Article A body." not in result.context_string


def test_query_idempotent(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    a = adapter.query("first")
    b = adapter.query("second")
    assert a.context_string == b.context_string


def test_articles_sorted_deterministic_order(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    result = adapter.query("q")
    body = result.context_string
    # a.md, b.md, research__deep.md should appear in sorted order
    pos_a = body.index("--- wiki/a.md ---")
    pos_b = body.index("--- wiki/b.md ---")
    pos_r = body.index("--- wiki/research__deep.md ---")
    assert pos_a < pos_b < pos_r


# --- get_graph_snapshot ---------------------------------------------


def test_graph_snapshot_is_empty(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    entities, edges = adapter.get_graph_snapshot()
    assert entities == []
    assert edges == []


# --- ingest_corpus -------------------------------------------------


def test_ingest_corpus_raises_with_helpful_message(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    with pytest.raises(NotImplementedError, match="compile-wiki"):
        adapter.ingest_corpus([{"id": "x", "text": "y"}])


# --- close ---------------------------------------------------------


def test_close_clears_cache(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    adapter.query("warm cache")
    assert adapter._cached_context is not None
    adapter.close()
    assert adapter._cached_context is None


def test_close_is_repeatable(tmp_path):
    out = _setup_compiled(tmp_path)
    adapter = KarpathyCompiledAdapter(out)
    adapter.close()
    adapter.close()  # no error


# --- Integration with the compiler ---------------------------------


def test_round_trip_through_compile_vault(tmp_path):
    """Compile a small raw vault, then read it back through the adapter."""
    from sme.conditions.wiki_compiler import compile_vault

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "alpha.md").write_text("Alpha note.")
    (raw / "beta.md").write_text("Beta note.")

    class Fake:
        def complete(self, prompt: str, **kw) -> str:
            for line in prompt.splitlines():
                if line.startswith("Source path: "):
                    rel = line.split(": ", 1)[1].strip()
                    return f"Compiled summary of {rel}"
            return "# Index\n- alpha.md\n- beta.md\n"

    compiled = tmp_path / "compiled"
    compile_vault(raw, compiled, Fake())

    adapter = KarpathyCompiledAdapter(compiled)
    result = adapter.query("any question")
    assert "Compiled summary of alpha.md" in result.context_string
    assert "Compiled summary of beta.md" in result.context_string
    assert "# Index" in result.context_string
