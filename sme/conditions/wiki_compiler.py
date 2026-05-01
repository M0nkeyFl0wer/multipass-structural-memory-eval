"""Karpathy-baseline Condition D2 — LLM-compiled wiki + index.

Implements the compilation pipeline described in
``docs/cross_validation_2026.md`` § (4) and modelled on Karpathy's
personal LLM-Wiki setup
(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
take a directory of raw notes, run each through an LLM to produce a
condensed wiki article, and emit a single ``index.md`` cataloguing the
articles so a frontier model can navigate the corpus from one prompt.

Where Condition D1 (``FullContextAdapter``) dumps the entire raw corpus
into the prompt verbatim, D2 trades one-time compilation cost for a
denser, lower-noise context. The interesting question D2 answers — and
D1 cannot — is whether the LLM-compilation layer adds value over raw
context at the same context budget.

Compilation flow::

    raw vault/                           compiled/
    ├── notes-a.md          →            ├── wiki/
    ├── sub/notes-b.md                   │   ├── notes-a.md       (LLM summary)
    └── notes-c.md                       │   ├── sub_notes-b.md
                                         │   └── notes-c.md
                                         ├── index.md             (LLM-generated index)
                                         └── _manifest.json       (content hashes for caching)

The cache lives at ``compiled/_manifest.json`` and keys each compiled
article by the SHA256 of its raw source. Re-running ``compile_vault``
on an unchanged source skips the LLM call. Re-running on a corpus
where one note changed re-compiles only that note plus the index.

The LLM client is a small ``LLMClient`` protocol with a single
``complete(prompt, **kwargs) -> str`` method. Tests inject a fake;
production callers pass a real OpenAI / Anthropic / etc. client.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Protocol

log = logging.getLogger(__name__)

_MANIFEST_NAME = "_manifest.json"
_INDEX_NAME = "index.md"
_WIKI_DIR = "wiki"


# --- LLM client protocol ----------------------------------------------


class LLMClient(Protocol):
    """Minimal interface a real LLM call must satisfy.

    The compiler doesn't import any vendor SDK — callers wrap their own
    client (openai, anthropic, ollama, …) and pass it in. Keeps the
    compiler dependency-free and testable without API keys.
    """

    def complete(self, prompt: str, **kwargs) -> str:
        ...


# --- Public API -------------------------------------------------------


@dataclass
class CompileReport:
    """Summary of a compile_vault run."""

    output_dir: Path
    n_notes: int = 0
    n_compiled: int = 0           # actually called the LLM
    n_skipped_cache: int = 0      # found in manifest with matching hash
    n_failed: int = 0             # LLM call raised
    failures: list[tuple[str, str]] = field(default_factory=list)  # (path, error)
    index_chars: int = 0
    wiki_total_chars: int = 0


def compile_vault(
    vault_dir: str | Path,
    output_dir: str | Path,
    llm_client: LLMClient,
    *,
    summary_target_words: int = 300,
    article_prompt: Optional[str] = None,
    index_prompt: Optional[str] = None,
    force: bool = False,
) -> CompileReport:
    """Compile a raw vault into Karpathy-style wiki + index.

    Args:
        vault_dir: the raw corpus directory (read recursively for ``.md``).
        output_dir: where to write ``wiki/`` and ``index.md``. Created
            if missing.
        llm_client: any object with a ``complete(prompt) -> str`` method.
        summary_target_words: rough length target the prompt asks for.
        article_prompt, index_prompt: override the default prompts.
        force: if True, re-compile every note regardless of cache.

    Returns:
        ``CompileReport`` with per-note status. The compiler logs
        warnings on per-note failures but does NOT raise — partial
        compilation is valid and the report makes the gaps visible.
    """
    vault_path = Path(vault_dir)
    out_path = Path(output_dir)
    if not vault_path.is_dir():
        raise ValueError(f"vault_dir does not exist or is not a directory: {vault_path}")

    wiki_path = out_path / _WIKI_DIR
    wiki_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / _MANIFEST_NAME

    manifest: dict[str, dict] = {}
    if manifest_path.exists() and not force:
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as exc:
            log.warning("manifest at %s is corrupt; ignoring (%s)", manifest_path, exc)
            manifest = {}

    article_prompt = article_prompt or _DEFAULT_ARTICLE_PROMPT
    index_prompt = index_prompt or _DEFAULT_INDEX_PROMPT

    report = CompileReport(output_dir=out_path)

    notes = _find_notes(vault_path)
    report.n_notes = len(notes)

    article_summaries: list[tuple[str, str]] = []  # (relpath, summary)

    for note_path in notes:
        rel = note_path.relative_to(vault_path)
        rel_str = str(rel)
        body = note_path.read_text()
        body_hash = _sha256(body)
        wiki_relpath = _safe_wiki_relpath(rel)
        wiki_target = wiki_path / wiki_relpath

        cached = manifest.get(rel_str)
        if (
            not force
            and cached is not None
            and cached.get("hash") == body_hash
            and wiki_target.exists()
        ):
            report.n_skipped_cache += 1
            article_summaries.append((rel_str, wiki_target.read_text()))
            continue

        try:
            prompt = article_prompt.format(
                relpath=rel_str,
                target_words=summary_target_words,
                body=body,
            )
            summary = llm_client.complete(prompt)
            wiki_target.parent.mkdir(parents=True, exist_ok=True)
            wiki_target.write_text(summary)
            manifest[rel_str] = {
                "hash": body_hash,
                "wiki_relpath": str(wiki_relpath),
                "summary_chars": len(summary),
            }
            report.n_compiled += 1
            report.wiki_total_chars += len(summary)
            article_summaries.append((rel_str, summary))
        except Exception as exc:  # noqa: BLE001 — partial compile is a feature
            report.n_failed += 1
            report.failures.append((rel_str, str(exc)))
            log.warning("LLM compile failed for %s: %s", rel_str, exc)

    # Aggregate wiki_total_chars including cache hits
    if report.n_skipped_cache:
        report.wiki_total_chars = sum(
            entry.get("summary_chars", 0)
            for entry in manifest.values()
        )

    # Generate / refresh the index from the surviving article set
    if article_summaries:
        try:
            index_text = _build_index(
                article_summaries,
                index_prompt=index_prompt,
                llm_client=llm_client,
            )
            (out_path / _INDEX_NAME).write_text(index_text)
            report.index_chars = len(index_text)
        except Exception as exc:  # noqa: BLE001
            log.warning("index compile failed: %s", exc)
            # Fall back to a deterministic stub index so downstream
            # readers always have something to load.
            stub = _stub_index(article_summaries)
            (out_path / _INDEX_NAME).write_text(stub)
            report.index_chars = len(stub)

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return report


# --- Helpers ----------------------------------------------------------


_DEFAULT_ARTICLE_PROMPT = """\
You are compiling a personal wiki article from a raw note. Produce a
self-contained summary that another person could read in isolation —
include every load-bearing fact, name, date, and decision. Aim for
roughly {target_words} words. Use markdown headings sparingly.

Source path: {relpath}

Source content:
---
{body}
---

Write the wiki article now. Output ONLY the article text, no preamble.
"""

_DEFAULT_INDEX_PROMPT = """\
You are compiling the top-level index for a personal LLM wiki. Below
is the list of articles and their first paragraphs. Produce a short
index — under 1500 words — that a reader can scan in one sitting and
use to decide which articles to load. Group articles into 3-7
thematic sections. For each article, give one line: the path and a
sentence summary.

Articles:
{article_list}

Output ONLY the index in markdown.
"""


def _find_notes(vault_dir: Path) -> list[Path]:
    """Sorted list of every ``.md`` file under vault_dir."""
    return sorted(vault_dir.rglob("*.md"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_wiki_relpath(rel: Path) -> Path:
    """Map ``a/b/c.md`` → ``a__b__c.md`` so the wiki/ dir stays flat-ish.

    Keeping a flat layout makes the on-disk surface easier to inspect
    and reason about; the original tree structure is preserved in the
    relpath delimiter and the manifest entry.
    """
    parts = list(rel.parts)
    if len(parts) == 1:
        return Path(parts[0])
    stem = "__".join(parts[:-1])
    return Path(f"{stem}__{parts[-1]}")


def _build_index(
    articles: Iterable[tuple[str, str]],
    *,
    index_prompt: str,
    llm_client: LLMClient,
) -> str:
    article_list = "\n".join(
        f"- {rel}: {_first_paragraph(summary)}"
        for rel, summary in articles
    )
    prompt = index_prompt.format(article_list=article_list)
    return llm_client.complete(prompt)


def _stub_index(articles: Iterable[tuple[str, str]]) -> str:
    lines = ["# Index", ""]
    for rel, summary in articles:
        first = _first_paragraph(summary)
        lines.append(f"- **{rel}** — {first}")
    return "\n".join(lines) + "\n"


def _first_paragraph(text: str, *, max_chars: int = 240) -> str:
    """Return the first non-empty paragraph, capped to max_chars."""
    for para in re.split(r"\n\s*\n", text.strip()):
        para = para.strip()
        if para:
            return para[:max_chars]
    return ""
