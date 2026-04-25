"""Shared pytest fixtures for SME tests."""

from __future__ import annotations

import pytest

from sme.topology.fixtures import synthetic_duplicates_graph, synthetic_gap_graph


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


import io
import json
import urllib.error


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
