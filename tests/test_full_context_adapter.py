"""Tests for the Karpathy-baseline Condition D1 adapter.

See ``docs/cross_validation_2026.md`` § (4) for the design and
``sme/conditions/full_context.py`` for the implementation contract
these tests pin down.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sme.conditions.full_context import FullContextAdapter


# --- Fixtures ---------------------------------------------------------


def _write_md(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


@pytest.fixture
def three_file_vault(tmp_path: Path) -> Path:
    """A vault with three top-level .md files in non-trivial sort order."""
    vault = tmp_path / "vault"
    _write_md(vault / "alpha.md", "# alpha\nfirst note text\n")
    _write_md(vault / "beta.md", "# beta\nsecond note text\n")
    _write_md(vault / "gamma.md", "# gamma\nthird note text\n")
    return vault


@pytest.fixture
def nested_vault(tmp_path: Path) -> Path:
    """A vault with sub-directories and mixed file types."""
    vault = tmp_path / "vault"
    _write_md(vault / "root.md", "# root\nat the top level\n")
    _write_md(vault / "topic_a" / "child.md", "# child\nnested under topic_a\n")
    _write_md(
        vault / "topic_b" / "deep" / "grandchild.md",
        "# grandchild\nnested two deep\n",
    )
    # Non-md files we expect to be ignored.
    (vault / "ignore.txt").write_text("plain text, not markdown\n")
    (vault / "topic_a" / "data.json").write_text("{\"x\": 1}\n")
    return vault


# --- Construction -----------------------------------------------------


def test_construction_with_existing_dir(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    assert adapter.vault_dir == three_file_vault


def test_construction_with_nonexistent_dir_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="does not exist"):
        FullContextAdapter(bogus)


def test_construction_with_file_not_dir_raises(tmp_path: Path) -> None:
    f = tmp_path / "a_file.md"
    f.write_text("not a dir")
    with pytest.raises(ValueError, match="not a directory"):
        FullContextAdapter(f)


# --- Happy path -------------------------------------------------------


def test_query_returns_all_files_concatenated(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    result = adapter.query("any question")
    assert result.error is None
    assert "first note text" in result.context_string
    assert "second note text" in result.context_string
    assert "third note text" in result.context_string


def test_query_concatenation_is_sorted_by_path(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    ctx = adapter.query("q").context_string
    pos_alpha = ctx.find("first note text")
    pos_beta = ctx.find("second note text")
    pos_gamma = ctx.find("third note text")
    assert 0 <= pos_alpha < pos_beta < pos_gamma


def test_query_n_results_is_ignored(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    a = adapter.query("q", n_results=1)
    b = adapter.query("q", n_results=999)
    assert a.context_string == b.context_string


def test_query_question_text_is_ignored(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    a = adapter.query("what is alpha?")
    b = adapter.query("what is beta?")
    assert a.context_string == b.context_string


def test_query_is_idempotent(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    first = adapter.query("q1").context_string
    second = adapter.query("q2").context_string
    assert first == second
    assert first  # non-empty


def test_retrieval_path_records_diagnostics(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    result = adapter.query("q")
    path = result.retrieval_path
    assert path[0] == "full_context"
    assert any(f"vault_dir={three_file_vault}" in p for p in path)
    assert any(p.startswith("n_files=3") for p in path)
    assert any(p.startswith("total_chars=") for p in path)


# --- Subdirectory recursion ------------------------------------------


def test_query_recurses_into_subdirectories(nested_vault: Path) -> None:
    adapter = FullContextAdapter(nested_vault)
    ctx = adapter.query("q").context_string
    assert "at the top level" in ctx
    assert "nested under topic_a" in ctx
    assert "nested two deep" in ctx


def test_query_ignores_non_md_files(nested_vault: Path) -> None:
    adapter = FullContextAdapter(nested_vault)
    ctx = adapter.query("q").context_string
    assert "plain text, not markdown" not in ctx
    assert '"x": 1' not in ctx


def test_frontmatter_is_included_verbatim(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write_md(
        vault / "note.md",
        "---\ntitle: Frontmattered\ntags: [a, b]\n---\n\nbody text\n",
    )
    adapter = FullContextAdapter(vault)
    ctx = adapter.query("q").context_string
    # Frontmatter must NOT be stripped — D1 includes everything.
    assert "title: Frontmattered" in ctx
    assert "tags: [a, b]" in ctx
    assert "body text" in ctx


# --- Empty / edge cases ----------------------------------------------


def test_empty_vault_returns_error_in_result(tmp_path: Path) -> None:
    vault = tmp_path / "empty_vault"
    vault.mkdir()
    adapter = FullContextAdapter(vault)
    result = adapter.query("q")
    assert result.error is not None
    assert "empty vault" in result.error
    assert result.context_string == ""
    # And we still get diagnostics.
    assert any(p.startswith("n_files=0") for p in result.retrieval_path)


def test_vault_with_only_non_md_files_is_empty(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "a.txt").write_text("nope")
    (vault / "b.json").write_text("{}")
    adapter = FullContextAdapter(vault)
    result = adapter.query("q")
    assert result.error is not None
    assert "empty vault" in result.error


# --- get_graph_snapshot ----------------------------------------------


def test_get_graph_snapshot_returns_empty(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    entities, edges = adapter.get_graph_snapshot()
    assert entities == []
    assert edges == []


# --- ingest_corpus ---------------------------------------------------


def test_ingest_corpus_raises_with_helpful_message(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    with pytest.raises(NotImplementedError) as excinfo:
        adapter.ingest_corpus([{"id": "x", "text": "y"}])
    msg = str(excinfo.value)
    assert "vault_dir" in msg
    assert "ingest_corpus" in msg


# --- Lifecycle -------------------------------------------------------


def test_close_is_a_noop(three_file_vault: Path) -> None:
    adapter = FullContextAdapter(three_file_vault)
    adapter.close()
    # Safe to call twice.
    adapter.close()


# --- Large-corpus warning --------------------------------------------


def test_large_corpus_emits_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    vault = tmp_path / "big"
    # Write a single ~1.1MB file.
    big_body = "x" * 1_100_000
    _write_md(vault / "huge.md", big_body)
    adapter = FullContextAdapter(vault)
    with caplog.at_level(logging.WARNING, logger="sme.conditions.full_context"):
        result = adapter.query("q")
    assert result.error is None
    assert any(
        "may exceed the model's context window" in r.message for r in caplog.records
    )
