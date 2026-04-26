"""FamiliarAdapter — SME adapter for familiar.realm.watch v0.2.0+.

Familiar wraps palace-daemon with a v0.2 retrieval pipeline (rerank,
temporal decay, extractive compression, grounding directives). This
adapter measures familiar's full pipeline; the sibling
MemPalaceDaemonAdapter measures palace alone. Comparing their SME
scores quantifies what familiar's v0.2 contributes.

POST /api/familiar/eval already returns SME-QueryResult shape natively
(familiar's chunk-C of v0.2 was designed against this contract), so the
adapter is mostly deserialization with error/warning translation rules.
GET /api/familiar/graph proxies palace-daemon's /graph; reuse the
shared mapping module.

Defaults to mock_inference=True so Cat 1 substring scoring stays
deterministic — no LLM in the loop. Inference-mode runs are reserved
for a future Cat 9 pass.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from sme.adapters._graph_mapping import project_graph
from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


DEFAULT_BASE_URL = "http://familiar:8080"
DEFAULT_TIMEOUT_S = 30.0


class FamiliarAdapter(SMEAdapter):
    """Adapter for a running familiar.realm.watch v0.2.0+ instance."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        mock_inference: bool = True,
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.mock_inference = mock_inference
        # `opener` is injected by tests via fake_urlopen_factory; production
        # code uses urllib.request.urlopen directly.
        self._opener = opener

    # --- Required SMEAdapter methods ---

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        """No-op stub. Familiar reads palace data it didn't author;
        ingestion happens upstream via `mempalace mine`."""
        return {
            "entities_created": 0,
            "edges_created": 0,
            "errors": [],
            "warnings": [
                "FamiliarAdapter is diagnostic-only (Mode B). Familiar reads "
                "palace data it didn't author; ingestion happens upstream via "
                "`mempalace mine`. ingest_corpus is a no-op."
            ],
        }

    def query(self, question: str) -> QueryResult:
        raise NotImplementedError("Task 4-7")

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        raise NotImplementedError("Task 8")
