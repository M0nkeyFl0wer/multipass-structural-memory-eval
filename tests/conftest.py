"""Shared pytest fixtures for SME tests."""

from __future__ import annotations

import io
import json
import os
import socket
import subprocess

import pytest

from sme.topology.fixtures import synthetic_duplicates_graph, synthetic_gap_graph


# --- Isolation: tests must be UNABLE to reach paid APIs or remote hosts ------
#
# Found 2026-11-13: `sme.eval.llm_clients.load_api_key` reads the system
# keyring via `secret-tool` BEFORE it looks at the environment. So unsetting
# OPENAI_API_KEY did not stop a plain local `pytest` from making real, billed
# OpenAI calls, and the repo's own pre-commit hook runs pytest, so every commit
# did it. In CI there is no keyring, so the same tests silently skipped, which
# hid a real judge failure behind a green badge.
#
# Protection is the DEFAULT here, never opt-in (see ~/.claude/rules/
# test-isolation.md). A test escapes the guard only by being marked `slow`
# (live-API calibration tests, deselected by default in pyproject addopts and
# run deliberately with `pytest -m slow`) or by the operator exporting
# SME_ALLOW_NETWORK=1 for the env-gated live smoke tests.

_LLM_KEY_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def _block_live_credentials_and_network(request, monkeypatch):
    if request.node.get_closest_marker("slow"):
        return  # explicitly opted in to live calls
    if os.environ.get("SME_ALLOW_NETWORK") == "1":
        return  # operator is deliberately running live smoke tests

    # 1. No API keys from the environment.
    for var in _LLM_KEY_VARS:
        monkeypatch.delenv(var, raising=False)

    # 2. No API keys from the keyring. Raising FileNotFoundError is exactly
    #    what load_api_key already treats as "secret-tool not installed", so
    #    production code takes its normal no-key path. Tests that fake the
    #    keyring patch subprocess.run themselves; their patch replaces this one.
    real_run = subprocess.run

    def guarded_run(cmd, *args, **kwargs):
        argv0 = cmd[0] if isinstance(cmd, (list, tuple)) and cmd else str(cmd)
        if os.path.basename(str(argv0)) == "secret-tool":
            raise FileNotFoundError("secret-tool is blocked under test")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded_run)

    # 3. No outbound connections except loopback (fake local servers are fine).
    real_connect = socket.socket.connect

    def guarded_connect(self, address):
        if isinstance(address, tuple) and address and address[0] not in _LOOPBACK:
            raise OSError(f"network blocked under test: {address[0]}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def gap_graph():
    """Known-topology graph with a seeded structural gap.

    Returns ``(entities, edges, ground_truth)``. See
    ``sme.topology.fixtures.synthetic_gap_graph`` for the layout.
    """
    return synthetic_gap_graph()


@pytest.fixture
def duplicates_graph():
    """Known-collision graph for Cat 4 (The Threshold) tests.

    Returns ``(entities, edges, ground_truth)``. See
    ``sme.topology.fixtures.synthetic_duplicates_graph`` for the
    exact collisions seeded.
    """
    return synthetic_duplicates_graph()


class _FakeResponse:
    """Minimal stand-in for urlopen()'s return value.

    Mocks the context-manager + .read() shape that the adapter uses.
    """

    def __init__(self, body, status=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._buf = io.BytesIO(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._buf.read()


@pytest.fixture
def fake_urlopen_factory(monkeypatch):
    """Build a fake urlopen that returns canned responses per URL.

    Usage::

        fake_urlopen_factory({
            "GET http://daemon/search?q=hi&limit=5&kind=content": {"results": [...]},
            "POST http://daemon/mcp": {"result": {"content": [...]}},
        })

    The key is ``"<METHOD> <full URL up to but not including any extra query>"``.
    Match is by exact prefix on the URL — query strings are compared in full
    when present in the key, otherwise the prefix wins.

    A response value can be:
    * dict/list — JSON-encoded as 200 OK
    * str/bytes — sent as-is, 200 OK
    * tuple ``(status, body)`` — explicit status
    * Exception — raised when the URL is hit
    * callable ``(req) -> response`` — invoked to dispatch on the request
      body (used for JSON-RPC mocks)
    """

    def factory(routes):
        def fake_urlopen(req, timeout=None):
            method = req.get_method()
            url = req.full_url
            key_full = f"{method} {url}"
            if key_full in routes:
                resp = routes[key_full]
            else:
                base = url.split("?", 1)[0]
                key_base = f"{method} {base}"
                if key_base in routes:
                    resp = routes[key_base]
                else:
                    raise AssertionError(f"unexpected request: {key_full}")
            # If the registered response is a callable, invoke it with the
            # request — used for body-dispatching mocks (e.g. JSON-RPC).
            if callable(resp) and not isinstance(resp, Exception):
                resp = resp(req)
            if isinstance(resp, Exception):
                raise resp
            if isinstance(resp, tuple):
                status, body = resp
                return _FakeResponse(body, status=status)
            return _FakeResponse(resp)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        return fake_urlopen

    return factory
