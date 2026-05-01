"""Karpathy-baseline Condition D2 — LLM-compiled wiki + index, in context.

Where ``FullContextAdapter`` (D1) dumps every raw ``.md`` into the
prompt, ``KarpathyCompiledAdapter`` (D2) reads the **compiled** wiki
produced by ``wiki_compiler.compile_vault`` and assembles
``index.md`` + every ``wiki/<article>.md`` into the query's
``context_string``.

The compilation is intentionally separate from the adapter (run via
``sme-eval compile-wiki`` or by calling ``compile_vault`` directly).
This keeps the LLM cost out-of-band — the test harness, the SME
``retrieve`` path, and CI all read pre-compiled output. The adapter
itself never calls an LLM.

The condition this measures: at the same context budget as D1, does
LLM-compiled compression improve answer accuracy? Or does the noise
filtering throw away facts a substring matcher (or a downstream
reader model) would have found in the raw text?

Like D1, D2 has no graph: ``get_graph_snapshot`` returns ``([], [])``.
SME's structural categories (Cat 4 / 5 / 8) are not meaningful here;
the retrieval-side categories (Cat 1 / 2c / 3 / 6) read the
``context_string`` and produce comparable numbers to D1, with a
different speed/cost/coverage tradeoff.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


# Threshold above which we warn callers about context-window risk.
# Mirrors the FullContextAdapter constant; KarpathyCompiledAdapter
# should typically be well under this since the compilation step
# condenses each article.
_LARGE_CORPUS_BYTES = 1_000_000


class KarpathyCompiledAdapter(SMEAdapter):
    """Condition D2 — LLM-compiled wiki + index in context.

    Args:
        compiled_dir: directory holding ``index.md`` and a ``wiki/``
            subdirectory with the compiled articles. Produced by
            ``wiki_compiler.compile_vault``.
        include_wiki: if True (default), every wiki article is
            concatenated after the index. If False, only ``index.md``
            is used (tests "is the index alone sufficient?").

    Edge cases handled:

    - ``compiled_dir`` doesn't exist or isn't a directory → ``ValueError``
      at construction time.
    - ``compiled_dir`` exists but ``index.md`` and ``wiki/`` are both
      missing → ``ValueError`` at construction time. (An empty
      compilation suggests the user wired the wrong path.)
    - Only ``index.md`` exists → that's loaded as the full context
      (legitimate "index-only" run).
    - Only ``wiki/`` exists, no ``index.md`` → load wiki articles
      with a generated stub-index header so callers see what's there.
    """

    def __init__(
        self,
        compiled_dir: str | Path,
        *,
        include_wiki: bool = True,
    ) -> None:
        path = Path(compiled_dir)
        if not path.is_dir():
            raise ValueError(
                f"compiled_dir does not exist or is not a directory: {path}"
            )

        index_path = path / "index.md"
        wiki_dir = path / "wiki"

        if not index_path.exists() and not wiki_dir.is_dir():
            raise ValueError(
                f"compiled_dir {path} has neither index.md nor wiki/ — "
                "did you run `sme-eval compile-wiki` first?"
            )

        self.compiled_dir = path
        self.index_path = index_path
        self.wiki_dir = wiki_dir
        self.include_wiki = include_wiki

        self._cached_context: Optional[str] = None
        self._cached_n_articles: int = 0

    # --- Required SMEAdapter contract --------------------------------

    def query(
        self,
        question: str,
        *,
        n_results: int = 5,
        **_: object,
    ) -> QueryResult:
        del question  # unused — D2 returns the same compiled context regardless
        del n_results  # accepted for API parity, ignored

        if self._cached_context is None:
            self._cached_context, self._cached_n_articles = self._build_context()

        total_chars = len(self._cached_context)
        path_summary = [
            "karpathy_compiled",
            f"compiled_dir={self.compiled_dir}",
            f"index_present={self.index_path.exists()}",
            f"include_wiki={self.include_wiki}",
            f"n_articles={self._cached_n_articles}",
            f"total_chars={total_chars}",
        ]

        if not self._cached_context:
            return QueryResult(
                answer="",
                context_string="",
                error=(
                    f"empty compiled corpus: index missing and 0 wiki articles "
                    f"under {self.compiled_dir}"
                ),
                retrieval_path=path_summary,
            )

        return QueryResult(
            answer=self._cached_context,
            context_string=self._cached_context,
            retrieved_entities=[],
            retrieval_path=path_summary,
        )

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """No graph — D2 is a no-retrieval-no-structure baseline."""
        return [], []

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "KarpathyCompiledAdapter reads pre-compiled wiki output. "
            "Run `sme-eval compile-wiki --vault <raw> --output <compiled>` "
            "first, then point the adapter at the compiled directory."
        )

    def close(self) -> None:
        self._cached_context = None

    # --- Internal helpers --------------------------------------------

    def _build_context(self) -> tuple[str, int]:
        parts: list[str] = []
        n_articles = 0

        if self.index_path.exists():
            parts.append("--- index.md ---")
            parts.append(self.index_path.read_text())

        if self.include_wiki and self.wiki_dir.is_dir():
            for article in sorted(self.wiki_dir.rglob("*.md")):
                rel = article.relative_to(self.wiki_dir)
                parts.append(f"--- wiki/{rel} ---")
                parts.append(article.read_text())
                n_articles += 1

        context = "\n\n".join(parts)
        if len(context.encode("utf-8")) > _LARGE_CORPUS_BYTES:
            log.warning(
                "compiled context is %d bytes — likely overruns smaller "
                "context windows",
                len(context.encode("utf-8")),
            )
        return context, n_articles
