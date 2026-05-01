"""Tests for sme.conditions.wiki_compiler.

The compiler depends on an injectable ``LLMClient``; tests use a fake
that records prompts and returns canned summaries. No real LLM calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sme.conditions.wiki_compiler import (
    CompileReport,
    compile_vault,
)


class _FakeLLM:
    """Records prompts; returns deterministic canned outputs."""

    def __init__(self, *, summary_template: str = "Summary of {relpath}"):
        self.summary_template = summary_template
        self.prompts: list[str] = []

    def complete(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        # Last article-prompt has "Source path: ..." — pull it back.
        if "Source path:" in prompt:
            for line in prompt.splitlines():
                if line.startswith("Source path: "):
                    rel = line.split(": ", 1)[1].strip()
                    return self.summary_template.format(relpath=rel)
        # Index prompt — return a canned index.
        return "# Index\n\n(canned index)\n"


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# --- Happy path -------------------------------------------------------


def test_compile_simple_vault(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "# A\nFirst note body.")
    _write(vault / "b.md", "# B\nSecond note body.")

    llm = _FakeLLM()
    report = compile_vault(vault, out, llm)

    assert isinstance(report, CompileReport)
    assert report.n_notes == 2
    assert report.n_compiled == 2
    assert report.n_skipped_cache == 0
    assert report.n_failed == 0
    # 2 article calls + 1 index call
    assert len(llm.prompts) == 3

    # Wiki articles written
    assert (out / "wiki" / "a.md").read_text() == "Summary of a.md"
    assert (out / "wiki" / "b.md").read_text() == "Summary of b.md"
    # Index written
    assert (out / "index.md").exists()
    # Manifest cached
    manifest = json.loads((out / "_manifest.json").read_text())
    assert "a.md" in manifest
    assert manifest["a.md"]["wiki_relpath"] == "a.md"


def test_subdirectories_flattened_to_safe_relpath(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "research" / "topic.md", "topic content")
    _write(vault / "research" / "deep" / "subtopic.md", "subtopic content")

    llm = _FakeLLM()
    report = compile_vault(vault, out, llm)

    assert report.n_compiled == 2
    # Flattened with __ delimiter
    assert (out / "wiki" / "research__topic.md").exists()
    assert (out / "wiki" / "research__deep__subtopic.md").exists()


def test_non_md_files_ignored(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "note.md", "the note")
    _write(vault / "image.png", "fake binary")
    _write(vault / "script.py", "print('hi')")

    llm = _FakeLLM()
    report = compile_vault(vault, out, llm)

    assert report.n_notes == 1
    assert report.n_compiled == 1


# --- Caching ---------------------------------------------------------


def test_unchanged_notes_use_cache_on_second_run(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "alpha")
    _write(vault / "b.md", "beta")

    llm1 = _FakeLLM()
    compile_vault(vault, out, llm1)
    # 2 article + 1 index = 3 calls
    assert len(llm1.prompts) == 3

    llm2 = _FakeLLM()
    report2 = compile_vault(vault, out, llm2)
    assert report2.n_skipped_cache == 2
    assert report2.n_compiled == 0
    # Index is still rebuilt every run (cheap, keeps article-list fresh)
    assert len(llm2.prompts) == 1


def test_changed_note_recompiles_only_that_one(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "alpha")
    _write(vault / "b.md", "beta")

    compile_vault(vault, out, _FakeLLM())

    # Mutate b.md
    _write(vault / "b.md", "beta CHANGED")

    llm = _FakeLLM()
    report = compile_vault(vault, out, llm)
    assert report.n_skipped_cache == 1  # a.md unchanged
    assert report.n_compiled == 1  # b.md re-compiled
    # 1 article (b) + 1 index
    assert len(llm.prompts) == 2


def test_force_recompiles_everything(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "alpha")
    _write(vault / "b.md", "beta")

    compile_vault(vault, out, _FakeLLM())

    llm = _FakeLLM()
    report = compile_vault(vault, out, llm, force=True)
    assert report.n_compiled == 2
    assert report.n_skipped_cache == 0


def test_corrupt_manifest_falls_back_to_full_recompile(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "alpha")
    compile_vault(vault, out, _FakeLLM())

    # Corrupt the manifest
    (out / "_manifest.json").write_text("not json {{{")

    llm = _FakeLLM()
    report = compile_vault(vault, out, llm)
    assert report.n_compiled == 1
    assert report.n_skipped_cache == 0


# --- Failure handling ------------------------------------------------


class _FlakyLLM:
    """Fails on the first article prompt, succeeds otherwise."""

    def __init__(self):
        self.calls = 0

    def complete(self, prompt: str, **kwargs) -> str:
        self.calls += 1
        if self.calls == 1 and "Source path:" in prompt:
            raise RuntimeError("transient API error")
        if "Source path:" in prompt:
            for line in prompt.splitlines():
                if line.startswith("Source path: "):
                    rel = line.split(": ", 1)[1].strip()
                    return f"summary({rel})"
        return "(index)"


def test_per_note_failure_does_not_halt_compile(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "alpha")
    _write(vault / "b.md", "beta")

    llm = _FlakyLLM()
    report = compile_vault(vault, out, llm)

    assert report.n_failed == 1
    assert report.n_compiled == 1
    assert len(report.failures) == 1
    # The successful note still landed
    surviving = list((out / "wiki").glob("*.md"))
    assert len(surviving) == 1


class _IndexFailingLLM:
    def complete(self, prompt: str, **kwargs) -> str:
        if "Articles:" in prompt:
            raise RuntimeError("index failed")
        for line in prompt.splitlines():
            if line.startswith("Source path: "):
                return "ok"
        return ""


def test_index_failure_falls_back_to_stub(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "alpha")

    report = compile_vault(vault, out, _IndexFailingLLM())
    # Article succeeded; index fell back to stub
    assert report.n_compiled == 1
    index_text = (out / "index.md").read_text()
    assert "# Index" in index_text
    assert "a.md" in index_text


def test_missing_vault_dir_raises(tmp_path):
    with pytest.raises(ValueError, match="vault_dir does not exist"):
        compile_vault(tmp_path / "nope", tmp_path / "out", _FakeLLM())


def test_empty_vault_produces_empty_compile(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    out = tmp_path / "compiled"

    report = compile_vault(vault, out, _FakeLLM())
    assert report.n_notes == 0
    assert report.n_compiled == 0
    # No index call when there's nothing to index
    assert report.index_chars == 0


# --- Public surface --------------------------------------------------


def test_compile_report_aggregates_total_chars(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "compiled"
    _write(vault / "a.md", "x" * 1000)
    _write(vault / "b.md", "y" * 1000)

    report = compile_vault(vault, out, _FakeLLM())
    assert report.wiki_total_chars > 0
    assert report.index_chars > 0
    assert report.output_dir == out
