"""Karpathy-baseline Condition D1 — full corpus in context, no retrieval.

The ``FullContextAdapter`` implements SME's Condition D as scoped in
``docs/cross_validation_2026.md`` § (4): concatenate every ``.md`` file
under a vault directory and return that as the query's
``context_string``. There is no retrieval and no graph projection.

This is the deliberate-floor baseline that lets the harness answer the
mempalace#101 scale question — *at what corpus size does structured
retrieval start outperforming flat context-window retrieval?* — by
comparing structural systems' Cat 1/2c/3/6 readings against a no-
retrieval reference per corpus.

Why the structural categories don't apply here:

- Cat 4 (ingestion integrity / canonical collisions), Cat 5 (gap
  detection), and Cat 8 (ontology coherence) all read off the graph
  the system built. D1 deliberately builds no graph. ``get_graph_snapshot``
  returns ``([], [])`` and those categories' scorecards will degenerate
  in the expected way (no entities → nothing to score).
- Cat 1 (single-fact retrieval), Cat 2c (multi-hop recall), Cat 3
  (contradiction surfacing), Cat 6 (provenance) all read off the
  retrieved ``context_string``. Since the entire corpus is in the
  context, SME's substring matcher will trivially find any
  ``expected_sources`` term that exists in the corpus — for these
  categories the adapter gives a maximum-recall, maximum-token-cost
  reading. That tradeoff IS the reading.

The adapter is intentionally tiny — it owns no daemon, no embedding
model, no index. The only state is the vault path and the cached
concatenated context.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


# Threshold above which we warn callers about context-window risk.
# 1 MB ~= 250k cl100k_base tokens, well past most non-frontier models.
_LARGE_CORPUS_BYTES = 1_000_000


class FullContextAdapter(SMEAdapter):
    """Condition D1 adapter — full vault content as ``context_string``.

    Parameters
    ----------
    vault_dir:
        Path to a directory containing ``.md`` source notes. Recursed.
        Non-``.md`` files are ignored. Frontmatter is included verbatim.

    Raises
    ------
    ValueError
        If ``vault_dir`` does not exist or is not a directory. Empty
        directories are NOT an error — ``query()`` reports the empty
        condition through ``QueryResult.error`` instead.
    """

    def __init__(
        self,
        vault_dir: str | Path,
        *,
        read_only: bool = True,  # accepted for CLI parity; nothing to lock
    ):
        self._read_only = read_only
        self.vault_dir = Path(vault_dir)
        if not self.vault_dir.exists():
            raise ValueError(
                f"FullContextAdapter: vault_dir does not exist: {self.vault_dir}"
            )
        if not self.vault_dir.is_dir():
            raise ValueError(
                f"FullContextAdapter: vault_dir is not a directory: {self.vault_dir}"
            )
        self._cached_context: Optional[str] = None
        self._cached_files: Optional[list[Path]] = None

    # --- internal -----------------------------------------------------

    def _load_corpus(self) -> tuple[str, list[Path]]:
        """Read every .md file under vault_dir, sorted by path.

        Result is cached so repeated query() calls are idempotent and
        cheap. Sorted-path order is deterministic across runs and
        platforms (Path comparison is lexicographic on the string repr).
        """
        if self._cached_context is not None and self._cached_files is not None:
            return self._cached_context, self._cached_files

        files = sorted(p for p in self.vault_dir.rglob("*.md") if p.is_file())
        parts: list[str] = []
        for fpath in files:
            try:
                text = fpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Permissive: a non-UTF8 .md file is rare but not fatal.
                # Fall back to latin-1 so we always include something.
                text = fpath.read_text(encoding="latin-1")
            # Tag each file's content with its path so downstream
            # substring matchers can attribute matches and humans can
            # eyeball where text came from.
            try:
                rel = fpath.relative_to(self.vault_dir).as_posix()
            except ValueError:
                rel = fpath.as_posix()
            parts.append(f"--- {rel} ---\n{text}")

        context = "\n\n".join(parts)
        if len(context.encode("utf-8")) > _LARGE_CORPUS_BYTES:
            log.warning(
                "FullContextAdapter: corpus at %s is %d bytes (%d files); "
                "this may exceed the model's context window at query time. "
                "Condition D1 only succeeds when the full corpus fits in "
                "the prompt — see docs/cross_validation_2026.md § (4).",
                self.vault_dir,
                len(context.encode("utf-8")),
                len(files),
            )

        self._cached_context = context
        self._cached_files = files
        return context, files

    # --- SMEAdapter required ------------------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "FullContextAdapter loads its corpus from vault_dir at "
            "construction; pass vault_dir= rather than calling "
            "ingest_corpus()."
        )

    def query(self, question: str, n_results: int = 5) -> QueryResult:
        """Return the entire corpus as ``context_string``.

        ``question`` is accepted but ignored — there is no retrieval.
        ``n_results`` is accepted for API parity with other adapters and
        also ignored: D1 returns the full corpus regardless of K.
        """
        context, files = self._load_corpus()
        retrieval_path = [
            "full_context",
            f"vault_dir={self.vault_dir}",
            f"n_files={len(files)}",
            f"total_chars={len(context)}",
        ]
        if not files:
            return QueryResult(
                answer="",
                context_string="",
                retrieved_entities=[],
                retrieved_edges=[],
                retrieval_path=retrieval_path,
                error=f"empty vault: 0 files under {self.vault_dir}",
            )
        return QueryResult(
            answer=context,
            context_string=context,
            retrieved_entities=[],
            retrieved_edges=[],
            retrieval_path=retrieval_path,
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """No graph in Condition D1 — returns ``([], [])`` by design.

        D1 is "no retrieval, no structure." SME's structural categories
        (Cat 4 ingestion integrity, Cat 5 gap detection, Cat 8 ontology
        coherence) read off the graph the system built; with no graph
        they degenerate to empty readings, which is the honest answer
        for this condition. The retrieval-against-known-source categories
        (Cat 1, 2c, 3, 6) work — substring matchers run against the full
        corpus inside ``context_string``.
        """
        return [], []

    # --- Lifecycle ----------------------------------------------------

    def close(self) -> None:
        """No-op — FullContextAdapter holds no external resources."""
        return None
