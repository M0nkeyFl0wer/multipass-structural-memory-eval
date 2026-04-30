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

# Soft warnings (low_confidence, filtered_null_text_*, stuck_loop) and hard
# warnings (palace_unreachable) both surface in QueryResult.error with a
# WARN: prefix; the distinction lives in the surfaced message text.
HARD_WARNING_TOKENS = ("palace_unreachable",)


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

    def query(self, question: str, n_results: int = 5) -> QueryResult:
        """POST /api/familiar/eval and deserialize the SME-shape response."""
        body = {
            "query": question[:250],
            "limit": n_results,
            "kind": "content",
            "mock": self.mock_inference,
        }
        status, payload = self._post_json("/api/familiar/eval", body)
        if status == -1:
            msg = payload.get("_network_error", "unknown network error") if isinstance(payload, dict) else "unknown error"
            return QueryResult(
                answer="",
                context_string="",
                retrieved_entities=[],
                retrieved_edges=[],
                error=f"familiar {msg}",
            )
        if status != 200:
            snippet = json.dumps(payload)[:200] if isinstance(payload, dict) else str(payload)[:200]
            return QueryResult(
                answer="",
                context_string="",
                retrieved_entities=[],
                retrieved_edges=[],
                error=f"familiar endpoint {status}: {snippet}",
            )
        return self._deserialize_query(payload)

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        """GET /api/familiar/graph (familiar's proxy of palace-daemon
        /graph) and project to (entities, edges) via the shared mapping
        module. Failure returns ([], []) per the SME contract — a missing
        snapshot zeroes out structural-category scores rather than
        raising."""
        status, body = self._get_json("/api/familiar/graph")
        if status != 200 or not isinstance(body, dict) or "wings" not in body:
            return [], []
        return project_graph(body)

    # --- Optional SMEAdapter methods ---

    def get_flat_retrieval(self, question: str, k: int = 5) -> QueryResult:
        """Optional: same path as query() but returns only the entities,
        used by Cat 7 token-budget analysis where the answer text is
        irrelevant and only retrieval changes."""
        body = {
            "query": question[:250],
            "limit": k,
            "kind": "content",
            "mock": self.mock_inference,
        }
        status, payload = self._post_json("/api/familiar/eval", body)
        if status != 200 or not isinstance(payload, dict):
            return QueryResult(
                answer="",
                context_string="",
                retrieved_entities=[],
                retrieved_edges=[],
                error=f"familiar flat-retrieval {status}",
            )
        raw_entities = payload.get("retrieved_entities") or []
        return QueryResult(
            answer="",
            context_string="",
            retrieved_entities=[self._entity_from_payload(e) for e in raw_entities],
            retrieved_edges=[],
        )

    def get_ontology_source(self) -> dict:
        """Wings/rooms taxonomy is author-declared (mempalace_get_taxonomy
        MCP tool). Same documented schema as the underlying MemPalace
        install — we proxy the same palace through familiar's pipeline
        without changing the ontology shape."""
        return {
            "type": "declared",
            "schema": [
                {
                    "kind": "structural",
                    "entities": [
                        "wing", "room", "hall", "tunnel", "closet", "drawer"
                    ],
                },
                {
                    "kind": "hall_vocabulary",
                    "values": [
                        "facts", "events", "discoveries",
                        "preferences", "advice",
                    ],
                },
            ],
            "documentation": (
                "Familiar wraps a MemPalace palace with a v0.2 retrieval "
                "pipeline (rerank, temporal decay, extractive compression, "
                "grounding directives). The underlying ontology is "
                "MemPalace's — Wings, Rooms, Halls, Tunnels, Closets, "
                "Drawers."
            ),
        }

    def get_harness_manifest(self) -> list:
        """Forward-compat for SME Cat 9 (Handshake). Returns descriptors of
        familiar's invocation surfaces — HTTP tool-call + MCP. Falls back
        to [] when the multipass-side descriptor types aren't yet
        importable (Cat 9 not implemented yet on this multipass version)."""
        try:
            from sme.harness import ToolCall, MCPResource  # type: ignore
        except ImportError:
            return []
        return [
            ToolCall(
                name="familiar_query",
                json_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                backend_endpoint=f"{self.base_url}/api/familiar/eval",
            ),
            MCPResource(
                server_url=f"{self.base_url}/mcp",
                resource_uri_pattern="familiar_(recall|reflect|chat)",
            ),
        ]

    # --- Internals ---

    def _deserialize_query(self, payload: dict) -> QueryResult:
        """Map familiar's JSON response onto SME QueryResult."""
        answer = payload.get("answer") or ""
        context_string = payload.get("context_string") or ""
        raw_entities = payload.get("retrieved_entities") or []
        raw_edges = payload.get("retrieved_edges") or []
        server_error = payload.get("error")
        warnings = payload.get("warnings") or []

        entities = [self._entity_from_payload(e) for e in raw_entities]
        edges = [self._edge_from_payload(e) for e in raw_edges]

        parts: list[str] = []
        if server_error:
            parts.append(str(server_error))
        if warnings:
            parts.append("WARN: " + "; ".join(warnings))
        error = " | ".join(parts) if parts else None

        return QueryResult(
            answer=answer,
            context_string=context_string,
            retrieved_entities=entities,
            retrieved_edges=edges,
            error=error,
        )

    @staticmethod
    def _entity_from_payload(p: dict) -> Entity:
        """Map a familiar SmeEntity dict to an SME Entity dataclass."""
        eid = p.get("id") or ""
        return Entity(
            id=eid,
            name=eid,
            entity_type=p.get("type") or "drawer",
            properties={
                k: v for k, v in p.items() if k not in ("id", "type") and v is not None
            },
        )

    @staticmethod
    def _edge_from_payload(p: dict) -> Edge:
        return Edge(
            source_id=p.get("subject") or "",
            target_id=p.get("object") or "",
            edge_type=p.get("predicate") or "",
        )

    def _post_json(self, path: str, body: dict) -> tuple[int, Any]:
        """POST JSON, return (status, parsed_body). Translates network and
        JSON-decode failures into a sentinel (-1 status, error-bearing dict)
        so the adapter's error contract stays no-raise."""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"content-type": "application/json"},
            method="POST",
        )
        opener = self._opener or urllib.request.urlopen
        try:
            with opener(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status if hasattr(resp, "status") else resp.getcode()
                try:
                    parsed = json.loads(raw) if raw else {}
                except json.JSONDecodeError as e:
                    return -1, {"_network_error": f"invalid JSON response: {e}"}
                return status, parsed
        except urllib.error.HTTPError as e:
            try:
                raw = e.read().decode("utf-8", errors="replace")
                try:
                    return e.code, json.loads(raw)
                except json.JSONDecodeError:
                    return e.code, {"_raw": raw[:200]}
            except Exception:
                return e.code, {"_raw": ""}
        except (socket.timeout, TimeoutError) as e:
            return -1, {"_network_error": f"timeout after {self.timeout_s}s ({e})"}
        except urllib.error.URLError as e:
            return -1, {"_network_error": f"connection failed: {e.reason}"}
        except Exception as e:
            return -1, {"_network_error": f"unexpected: {type(e).__name__}: {e}"}

    def _get_json(self, path: str) -> tuple[int, Any]:
        """GET JSON, mirror _post_json's no-raise contract."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        opener = self._opener or urllib.request.urlopen
        try:
            with opener(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status if hasattr(resp, "status") else resp.getcode()
                try:
                    parsed = json.loads(raw) if raw else {}
                except json.JSONDecodeError as e:
                    return -1, {"_network_error": f"invalid JSON: {e}"}
                return status, parsed
        except urllib.error.HTTPError as e:
            try:
                raw = e.read().decode("utf-8", errors="replace")
                try:
                    return e.code, json.loads(raw)
                except json.JSONDecodeError:
                    return e.code, {"_raw": raw[:200]}
            except Exception:
                return e.code, {"_raw": ""}
        except (socket.timeout, TimeoutError) as e:
            return -1, {"_network_error": f"timeout after {self.timeout_s}s ({e})"}
        except urllib.error.URLError as e:
            return -1, {"_network_error": f"connection failed: {e.reason}"}
        except Exception as e:
            return -1, {"_network_error": f"unexpected: {type(e).__name__}: {e}"}
