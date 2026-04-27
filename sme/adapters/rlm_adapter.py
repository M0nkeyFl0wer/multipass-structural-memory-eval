"""RlmAdapter — Recursive Language Models as an SME adapter.

Treats RLM (jphein/rlm fork of alexzhang13/rlm) as the read-side
orchestrator: instead of familiar's deterministic retrieve→ground→
answer pipeline, the LLM itself decides when to call mempalace_search,
how to compose results, when to recurse.

For SME scoring purposes:
  - `query(text)` calls `rlm.completion(text)` once
  - `mempalace_search` is exposed as an RLM custom_tool — every call's
    result is captured into a per-query buffer
  - `context_string` becomes the concatenation of every drawer text
    RLM pulled during the run (in call order). The substring scorer
    in Cat 1 / retrieve scoring sees exactly what RLM saw.
  - `retrieved_entities` mirror the captured drawers as SME Entity rows
    so Cat 7 token counting and Cat 8 hop-counts have something real.

Backend: configurable via constructor. Defaults to portkey + the
familiar router URL when both are available; falls back to direct
OpenAI/Anthropic/Bedrock per RLM's own backend resolution.

Spec ref:
  ~/Projects/familiar.realm.watch/docs/superpowers/specs/2026-04-23-familiar-realm-watch-design.md
  § "Composition with RLM (Recursive Language Models) — added 2026-04-25"
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional
from urllib import error as _urlerror
from urllib import request as _urlrequest

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter


_DEFAULT_DAEMON_TIMEOUT = 10.0
_DEFAULT_LIMIT = 5


class RlmAdapter(SMEAdapter):
    """RLM-orchestrated palace consumer.

    Args:
        api_url: palace-daemon HTTP base URL (e.g. http://disks.jphe.in:8085)
        api_key: PALACE_API_KEY for the daemon (read from env if unset)
        backend: RLM backend identifier ("portkey", "openai", "anthropic", ...)
        backend_kwargs: passed through to RLM(...) — model_name, api_key, etc.
        environment: RLM REPL environment ("local" by default)
        verbose: forwards to RLM verbose flag
        kind: palace-daemon /search kind filter (default "content")
        timeout_s: per-search HTTP timeout
    """

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        backend: str = "openai",
        backend_kwargs: Optional[dict[str, Any]] = None,
        environment: str = "local",
        verbose: bool = False,
        kind: str = "content",
        timeout_s: float = _DEFAULT_DAEMON_TIMEOUT,
        **_unused: Any,
    ) -> None:
        # Lazy-import RLM so multipass doesn't require it for non-rlm runs.
        from rlm import RLM

        self.api_url = (api_url or os.environ.get("PALACE_DAEMON_URL", "http://disks.jphe.in:8085")).rstrip("/")
        self.api_key = api_key or os.environ.get("PALACE_API_KEY", "")
        self.kind = kind
        self.timeout_s = timeout_s
        self.verbose = verbose

        # Per-query capture buffer — populated by _mempalace_search and
        # drained at the end of each query() call.
        self._capture: list[dict] = []

        bk = dict(backend_kwargs or {})
        # Default to a sensible model when none is given.
        if "model_name" not in bk:
            if backend == "portkey":
                bk["model_name"] = "@openai/gpt-5-nano"
            elif backend == "openai":
                bk["model_name"] = "gpt-5-nano"
        # Resolve env var fallbacks for keys.
        if "api_key" not in bk:
            if backend == "portkey":
                bk["api_key"] = os.environ.get("PORTKEY_API_KEY", "")
            elif backend == "openai":
                bk["api_key"] = os.environ.get("OPENAI_API_KEY", "")
            elif backend == "anthropic":
                bk["api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")

        self._rlm = RLM(
            backend=backend,
            backend_kwargs=bk,
            environment=environment,
            custom_tools={
                "mempalace_search": {
                    "tool": self._mempalace_search,
                    "description": (
                        "Search JP's palace for drawers semantically related to a query. "
                        "Returns a list of dicts with text, wing, room, similarity. "
                        "Default limit is 5. Use this to ground factual claims about JP, "
                        "his projects, his realm, and any past events."
                    ),
                },
            },
            verbose=verbose,
        )

    # ------------------------------------------------------------------
    # mempalace_search — exposed to RLM's REPL via custom_tools.
    # ------------------------------------------------------------------

    def _mempalace_search(self, query: str, limit: int = _DEFAULT_LIMIT) -> list[dict]:
        """HTTP call to palace-daemon /search; capture results for SME scoring."""
        params = {"q": query, "limit": str(limit), "kind": self.kind}
        url = f"{self.api_url}/search?" + "&".join(f"{k}={_urlrequest.quote(v)}" for k, v in params.items())
        req = _urlrequest.Request(url)
        if self.api_key:
            req.add_header("x-api-key", self.api_key)
        try:
            with _urlrequest.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (_urlerror.URLError, _urlerror.HTTPError, OSError) as e:
            return [{"error": str(e), "results": []}]

        results = payload.get("results", []) or []
        # Trim what we return to RLM (it has limited context); keep the same
        # shape stable so the model's prompt isn't re-tokenized by surprise.
        trimmed: list[dict] = []
        for r in results[:limit]:
            entry = {
                "drawer_id": r.get("drawer_id") or r.get("id"),
                "text": (r.get("text") or "")[:500],
                "wing": r.get("wing"),
                "room": r.get("room"),
                "similarity": r.get("similarity"),
            }
            trimmed.append(entry)
            self._capture.append(entry)
        return trimmed

    # ------------------------------------------------------------------
    # SMEAdapter contract.
    # ------------------------------------------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        """No-op stub. RLM consumes a palace it didn't author; ingestion
        happens upstream via `mempalace mine` / familiar reflect."""
        return {"entities_created": 0, "edges_created": 0, "skipped": True}

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """RLM doesn't maintain a graph view. Return empty lists — Cat 8
        ontology coherence isn't applicable here. Cat 1/2/7 still work
        because they only need query() output."""
        return [], []

    def query(self, question: str) -> QueryResult:
        self._capture = []
        t0 = time.time()
        try:
            result = self._rlm.completion(question)
            answer = getattr(result, "response", str(result))
        except Exception as e:  # pragma: no cover — backend / network
            return QueryResult(
                answer="",
                context_string="",
                error=f"{type(e).__name__}: {e}",
            )

        # Build context_string from the captured search results in call order.
        # Mirrors familiar's "── Palace context (N drawers) ──" format so
        # the substring scorer behaves consistently across adapters.
        ctx_lines = [f"── RLM-orchestrated retrieval ({len(self._capture)} drawers) ──"]
        for r in self._capture:
            tags = []
            if r.get("drawer_id"): tags.append(f"drawer_id={r['drawer_id']}")
            if r.get("wing"): tags.append(f"wing={r['wing']}")
            if r.get("room"): tags.append(f"room={r['room']}")
            if isinstance(r.get("similarity"), (int, float)):
                tags.append(f"similarity={r['similarity']:.3f}")
            ctx_lines.append("[" + " · ".join(tags) + "]")
            ctx_lines.append(r.get("text", ""))
            ctx_lines.append("")
        context_string = "\n".join(ctx_lines)

        # SME entities — one per captured drawer.
        entities: list[Entity] = []
        for r in self._capture:
            if not r.get("drawer_id"):
                continue
            entities.append(Entity(
                id=str(r["drawer_id"]),
                name=str(r["drawer_id"]),
                entity_type="drawer",
                properties={
                    "text": r.get("text", ""),
                    "wing": r.get("wing"),
                    "room": r.get("room"),
                    "similarity": r.get("similarity"),
                    "matched_via": "rlm_tool_call",
                },
            ))

        elapsed_ms = round((time.time() - t0) * 1000, 1)
        return QueryResult(
            answer=answer,
            context_string=context_string,
            retrieved_entities=entities,
            retrieved_edges=[],
            retrieval_path=[
                {"step": "rlm_completion", "elapsed_ms": elapsed_ms,
                 "tool_calls": len(self._capture)},
            ],
            error=None,
        )

    def close(self) -> None:
        # RLM doesn't expose an explicit close; nothing to release here.
        pass
