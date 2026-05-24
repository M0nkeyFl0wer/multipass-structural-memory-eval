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

_CLOUD_CHAT_CONFIG_CANDIDATES = [
    os.path.expanduser("~/.config/cloud-chat-assistant/config.json"),
    os.path.expanduser("~/.cloud-chat-assistant.json"),
]


def _resolve_default_backend(bk: dict) -> tuple[str, dict]:
    """Pick a backend + defaults when none was explicitly passed.

    Priority order:
      1. RLM_BASE_URL / RLM_MODEL env vars — point the openai backend
         at any OpenAI-compat endpoint (familiar's own /v1, katana's
         llama.cpp, vLLM, etc.). Most explicit; wins.
      2. Cloud-chat-assistant config file (JP's home env) — Azure
         OpenAI endpoint with key. Reads as `azure_openai`.
      3. Standard env vars (AZURE_OPENAI / OPENAI / ANTHROPIC / PORTKEY).
      4. Fall through to openai default (will fail without a key).
    """
    if os.environ.get("RLM_BASE_URL"):
        bk.setdefault("base_url", os.environ["RLM_BASE_URL"])
        bk.setdefault("model_name", os.environ.get("RLM_MODEL", "qwen2.5-7b"))
        bk.setdefault("api_key", os.environ.get("RLM_API_KEY", "no-auth-needed"))
        return "openai", bk

    for path in _CLOUD_CHAT_CONFIG_CANDIDATES:
        try:
            with open(path) as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            continue
        endpoint = cfg.get("endpoint") or cfg.get("azure_endpoint")
        api_key = cfg.get("api_key")
        deployment = cfg.get("deployment")
        if endpoint and api_key:
            bk.setdefault("azure_endpoint", endpoint)
            bk.setdefault("api_key", api_key)
            if deployment:
                bk.setdefault("azure_deployment", deployment)
                bk.setdefault("model_name", deployment)
            bk.setdefault("api_version", cfg.get("api_version", "2024-08-01-preview"))
            return "azure_openai", bk

    if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
        return "azure_openai", bk
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", bk
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", bk
    if os.environ.get("PORTKEY_API_KEY"):
        return "portkey", bk
    return "openai", bk


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
        backend: Optional[str] = None,
        backend_kwargs: Optional[dict[str, Any]] = None,
        environment: str = "local",
        verbose: bool = False,
        kind: str = "content",
        timeout_s: float = _DEFAULT_DAEMON_TIMEOUT,
        invocation_mode: Optional[str] = None,
        **_unused: Any,
    ) -> None:
        """invocation_mode controls system-prompt augmentation for the
        SME #3 Step 2 discriminating experiment:
          - None (default): vanilla RLM system prompt; LLM decides when
            to invoke mempalace_search based on training. Matches Step 1
            baseline behavior.
          - "forced": prepend a directive requiring at least one
            mempalace_search call before FINAL. Tests whether the
            invocation-rate ceiling (gemma4: 60% zero-call) is the
            dominant Cat 9a lever on substring-shaped corpora.
          - "grounded": prepend a directive requiring the answer to
            quote at least one retrieved source filename. Tests whether
            the substring-scorer-vs-LLM-synthesis gap is the lever on
            file-shaped corpora (n=200 git-derived probes, etc.).
        """
        self.invocation_mode = invocation_mode
        # Lazy-import RLM so multipass doesn't require it for non-rlm runs.
        from rlm import RLM
        from rlm.utils.prompts import RLM_SYSTEM_PROMPT

        self.api_url = (api_url or os.environ.get("PALACE_DAEMON_URL", "http://disks.jphe.in:8085")).rstrip("/")
        self.api_key = api_key or os.environ.get("PALACE_API_KEY", "")
        self.kind = kind
        self.timeout_s = timeout_s
        self.verbose = verbose

        # Per-query capture buffer — populated by _mempalace_search and
        # drained at the end of each query() call. _capture grows by one
        # entry per drawer returned (across all tool invocations);
        # _tool_call_count tracks actual invocations of _mempalace_search
        # so 9a-shaped invocation-rate reads aren't conflated with
        # per-call drawer counts.
        self._capture: list[dict] = []
        self._tool_call_count: int = 0

        # Backend resolution. JP's home environment ships a multi-provider
        # config in ~/.config/cloud-chat-assistant/config.json. If no
        # explicit backend was passed, prefer that file's Azure OpenAI
        # entry (which is what cloud-chat-assistant uses by default).
        bk = dict(backend_kwargs or {})
        if backend is None:
            backend, bk = _resolve_default_backend(bk)
        # Per-backend defaults for model + key.
        if "model_name" not in bk:
            if backend == "portkey":
                bk["model_name"] = "@openai/gpt-5-nano"
            elif backend == "openai":
                bk["model_name"] = "gpt-5-nano"
            elif backend == "azure_openai":
                # Filled in by _resolve_default_backend if the file is present.
                bk.setdefault("model_name", "gpt-4o")
        if "api_key" not in bk:
            if backend == "portkey":
                bk["api_key"] = os.environ.get("PORTKEY_API_KEY", "")
            elif backend == "openai":
                bk["api_key"] = os.environ.get("OPENAI_API_KEY", "")
            elif backend == "anthropic":
                bk["api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
            elif backend == "azure_openai":
                bk["api_key"] = os.environ.get("AZURE_OPENAI_API_KEY", "")

        # Build the system prompt. By default, use RLM's own. In
        # invocation_mode="forced"/"grounded", prepend an extra
        # paragraph of constraints BEFORE the standard RLM prompt
        # (which still owns the {custom_tools_section} format
        # placeholder that RLM fills at completion time).
        custom_system_prompt: Optional[str] = None
        if invocation_mode == "forced":
            custom_system_prompt = (
                "MANDATORY RETRIEVAL CONSTRAINT (test condition, do not ignore):\n"
                "Before you provide FINAL(...) or FINAL_VAR(...), you MUST call\n"
                "`mempalace_search(...)` at least once with a query relevant to the\n"
                "user's question. Even if you believe you can answer from training\n"
                "data, you MUST first invoke the search tool. Never produce FINAL\n"
                "without at least one mempalace_search call in your history.\n"
                "\n"
                + RLM_SYSTEM_PROMPT
            )
        elif invocation_mode == "grounded":
            custom_system_prompt = (
                "MANDATORY GROUNDING CONSTRAINT (test condition, do not ignore):\n"
                "Before you provide FINAL(...) or FINAL_VAR(...), you MUST (1) call\n"
                "`mempalace_search(...)` at least once with a query relevant to the\n"
                "user's question, AND (2) include in your final answer at least one\n"
                "source filename or drawer_id from the retrieved results. Quote the\n"
                "source verbatim from the mempalace_search return value. If no\n"
                "retrieved drawer is relevant, say so explicitly in FINAL and quote\n"
                "the search query you used.\n"
                "\n"
                + RLM_SYSTEM_PROMPT
            )

        rlm_kwargs: dict[str, Any] = dict(
            backend=backend,
            backend_kwargs=bk,
            environment=environment,
            custom_tools={
                "mempalace_search": {
                    "tool": self._mempalace_search,
                    "description": (
                        "Search JP's palace for drawers semantically related to a query. "
                        "Returns a list of dicts with text, wing, room, source_file, similarity. "
                        "Default limit is 5. Use this to ground factual claims about JP, "
                        "his projects, his realm, and any past events."
                    ),
                },
            },
            verbose=verbose,
        )
        if custom_system_prompt is not None:
            rlm_kwargs["custom_system_prompt"] = custom_system_prompt
        self._rlm = RLM(**rlm_kwargs)

    # ------------------------------------------------------------------
    # mempalace_search — exposed to RLM's REPL via custom_tools.
    # ------------------------------------------------------------------

    def _mempalace_search(self, query: str, limit: int = _DEFAULT_LIMIT) -> list[dict]:
        """HTTP call to palace-daemon /search; capture results for SME scoring."""
        self._tool_call_count += 1
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
        # NOTE: source_file is load-bearing — SME's substring scorer matches
        # against expected_sources which are filenames; dropping source_file
        # from the trimmed entry meant the LLM couldn't quote it AND the
        # context_string used by the scorer didn't contain it, so retrieval
        # that landed the right drawer would still score 0. Fixed 2026-05-16.
        trimmed: list[dict] = []
        for r in results[:limit]:
            entry = {
                "drawer_id": r.get("drawer_id") or r.get("id"),
                "text": (r.get("text") or "")[:500],
                "wing": r.get("wing"),
                "room": r.get("room"),
                "source_file": r.get("source_file"),
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
        happens upstream via `mempalace mine` / familiar reflect.

        Returns the full SMEAdapter contract dict (with errors/warnings
        empty lists) so downstream harness code reading those keys
        doesn't KeyError. Prior to 2026-05-16 this returned an
        incomplete dict missing both required keys.
        """
        return {
            "entities_created": 0,
            "edges_created": 0,
            "errors": [],
            "warnings": [],
            "skipped": True,
        }

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """RLM doesn't maintain a graph view. Return empty lists — Cat 8
        ontology coherence isn't applicable here. Cat 1/2/7 still work
        because they only need query() output."""
        return [], []

    def query(self, question: str) -> QueryResult:
        self._capture = []
        self._tool_call_count = 0
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

        # Build context_string from BOTH the captured search results AND
        # the synthesized answer. RLM's "context" is split between what
        # the LM pulled via tool calls (the search captures) and what it
        # produced via training-data synthesis (the answer). Familiar's
        # equivalent — the system prompt — is purely retrieval. To give
        # the substring scorer a fair shake at RLM's full output, we
        # include both sides.
        ctx_lines = [f"── RLM-orchestrated retrieval ({len(self._capture)} drawers) ──"]
        for r in self._capture:
            tags = []
            if r.get("drawer_id"):
                tags.append(f"drawer_id={r['drawer_id']}")
            if r.get("source_file"):
                tags.append(f"source_file={r['source_file']}")
            if r.get("wing"):
                tags.append(f"wing={r['wing']}")
            if r.get("room"):
                tags.append(f"room={r['room']}")
            if isinstance(r.get("similarity"), (int, float)):
                tags.append(f"similarity={r['similarity']:.3f}")
            ctx_lines.append("[" + " · ".join(tags) + "]")
            ctx_lines.append(r.get("text", ""))
            ctx_lines.append("")
        ctx_lines.append("── RLM answer ──")
        ctx_lines.append(answer)
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
            # Strings, not dicts — cli's `'; '.join(path)` expects strings.
            retrieval_path=[
                f"rlm_completion ({elapsed_ms}ms, {self._tool_call_count} tool calls, {len(self._capture)} drawers)",
            ],
            error=None,
        )

    def close(self) -> None:
        # RLM doesn't expose an explicit close; nothing to release here.
        pass
