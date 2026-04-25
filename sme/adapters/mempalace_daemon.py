"""MemPalace daemon HTTP adapter for SME.

Talks to a running palace-daemon (https://github.com/jphein/palace-daemon)
over HTTP. Unlike sme.adapters.mempalace.MemPalaceAdapter (which opens
ChromaDB directly), this adapter does NO filesystem access and holds NO
parallel handles to the palace SQLite — it only makes HTTP requests.

Use this adapter when:
* you run palace-daemon (the daemon is the single writer to the palace),
* OR you want SME's structural readings to flow through the same
  retrieval path your production agents use.

For single-process MemPalace installs without the daemon, the existing
MemPalaceAdapter is correct — direct ChromaDB access is fine when there
is no concurrent writer to fight with.

See ``docs/superpowers/specs/2026-04-25-mempalace-daemon-adapter-design.md``
for the full design.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from sme.adapters.base import Edge, Entity, QueryResult, SMEAdapter

log = logging.getLogger(__name__)


DEFAULT_ENV_FILE = "~/.config/palace-daemon/env"
DEFAULT_KIND = "content"
DEFAULT_TIMEOUT = 180.0  # seconds — list_wings on a 151K-drawer palace ~30s


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser. Strips surrounding double-quotes.

    Ignores blank lines and ``# ...`` comments. Does NOT do shell expansion;
    the daemon's env file is a flat key/value list, not a shell script.
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if val and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        out[key] = val
    return out


class MemPalaceDaemonAdapter(SMEAdapter):
    """SMEAdapter against a running palace-daemon HTTP API.

    Construction does not connect — auth is resolved eagerly but the first
    network call happens in ``query()`` or ``get_graph_snapshot()``.

    Args:
        api_url: Daemon base URL (e.g. ``http://disks.jphe.in:8085``).
            Trailing slash stripped.
        api_key: Sent as ``X-API-Key`` header on every request.
        env_file: Path to an env file with ``PALACE_DAEMON_URL`` /
            ``PALACE_API_KEY``. Defaults to ``~/.config/palace-daemon/env``.
        kind: Default ``kind`` filter for ``/search``. ``"content"``
            (default) excludes Stop-hook auto-save checkpoints; pass
            ``"all"`` to disable, ``"checkpoint"`` for snapshot-only.
        api_timeout: Per-request HTTP timeout in seconds.
        prefer_graph_endpoint: If True (default), ``get_graph_snapshot``
            tries ``GET /graph`` first; on 404 it falls back to walking
            the four MCP tools. Set False to force the MCP path.
        read_only: Accepted for CLI parity. Ignored — this adapter only
            reads via HTTP.
        db_path: Accepted for CLI parity. Ignored — daemon owns the file.
    """

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        env_file: Optional[str | Path] = None,
        kind: str = DEFAULT_KIND,
        api_timeout: float = DEFAULT_TIMEOUT,
        prefer_graph_endpoint: bool = True,
        read_only: bool = True,
        db_path: Optional[str] = None,
    ) -> None:
        self.kind = kind
        self.api_timeout = api_timeout
        self.prefer_graph_endpoint = prefer_graph_endpoint

        env_path = Path(os.path.expanduser(str(env_file or DEFAULT_ENV_FILE)))
        env_vars = _parse_env_file(env_path)

        resolved_url = (
            api_url
            or env_vars.get("PALACE_DAEMON_URL")
            or os.environ.get("PALACE_DAEMON_URL")
        )
        resolved_key = (
            api_key
            or env_vars.get("PALACE_API_KEY")
            or os.environ.get("PALACE_API_KEY")
        )

        if not resolved_url:
            raise ValueError(
                "MemPalaceDaemonAdapter needs api_url. Pass it explicitly, "
                f"set PALACE_DAEMON_URL in {env_path}, or export it in the "
                "environment."
            )
        if not resolved_key:
            raise ValueError(
                "MemPalaceDaemonAdapter needs api_key. Pass it explicitly, "
                f"set PALACE_API_KEY in {env_path}, or export it in the "
                "environment."
            )

        self.api_url = resolved_url.rstrip("/")
        self.api_key = resolved_key

    # --- SMEAdapter required methods ---------------------------------

    def ingest_corpus(self, corpus: list[dict]) -> dict:
        raise NotImplementedError(
            "MemPalaceDaemonAdapter is diagnostic-only (Mode B). To seed a "
            "test palace, use the daemon's /memory POST endpoint or the "
            "mempalace CLI directly."
        )

    def query(self, question: str, **_kwargs: Any) -> QueryResult:
        raise NotImplementedError("Implemented in a later task")

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        raise NotImplementedError("Implemented in a later task")

    def close(self) -> None:
        pass
