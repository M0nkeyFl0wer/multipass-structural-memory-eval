"""Unit tests for FamiliarAdapter."""

from __future__ import annotations

import json
import socket
import urllib.error

import pytest

from sme.adapters.familiar import FamiliarAdapter


# --- Task 2: instantiation ---

def test_default_construction():
    adapter = FamiliarAdapter()
    assert adapter.base_url == "http://familiar:8080"
    assert adapter.timeout_s == 30.0
    assert adapter.mock_inference is True


def test_explicit_construction():
    adapter = FamiliarAdapter(
        base_url="https://familiar.jphe.in",
        timeout_s=10.0,
        mock_inference=False,
    )
    assert adapter.base_url == "https://familiar.jphe.in"
    assert adapter.timeout_s == 10.0
    assert adapter.mock_inference is False


def test_base_url_trailing_slash_stripped():
    adapter = FamiliarAdapter(base_url="https://familiar.jphe.in/")
    assert adapter.base_url == "https://familiar.jphe.in"


# --- Task 3: ingest_corpus stub ---

def test_ingest_corpus_is_noop():
    adapter = FamiliarAdapter()
    result = adapter.ingest_corpus([{"id": "doc-1", "text": "anything"}])
    assert result["entities_created"] == 0
    assert result["edges_created"] == 0
    assert result["errors"] == []
    assert any("diagnostic-only" in w.lower() or "no-op" in w.lower()
               for w in result["warnings"])
