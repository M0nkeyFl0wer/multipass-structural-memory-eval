"""Tests for sme.adapters.mempalace_daemon — HTTP-mocked, no live daemon."""

from __future__ import annotations

import os
import urllib.error
from pathlib import Path

import pytest

from sme.adapters.mempalace_daemon import MemPalaceDaemonAdapter


# --- Auth resolution -------------------------------------------------


def test_auth_explicit_kwargs_win(monkeypatch, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("PALACE_API_KEY=from-file\nPALACE_DAEMON_URL=http://from-file\n")
    monkeypatch.setenv("PALACE_API_KEY", "from-env")
    monkeypatch.setenv("PALACE_DAEMON_URL", "http://from-env")

    a = MemPalaceDaemonAdapter(
        api_url="http://explicit",
        api_key="explicit-key",
        env_file=env_file,
    )
    assert a.api_url == "http://explicit"
    assert a.api_key == "explicit-key"


def test_auth_env_file_used_when_no_kwargs(monkeypatch, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text(
        'PALACE_API_KEY="from-file"\nPALACE_DAEMON_URL=http://from-file:8085\n'
    )
    monkeypatch.delenv("PALACE_API_KEY", raising=False)
    monkeypatch.delenv("PALACE_DAEMON_URL", raising=False)

    a = MemPalaceDaemonAdapter(env_file=env_file)
    assert a.api_url == "http://from-file:8085"
    assert a.api_key == "from-file"


def test_auth_process_env_used_when_env_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PALACE_API_KEY", "from-env")
    monkeypatch.setenv("PALACE_DAEMON_URL", "http://from-env:8085")

    a = MemPalaceDaemonAdapter(env_file=tmp_path / "does-not-exist")
    assert a.api_url == "http://from-env:8085"
    assert a.api_key == "from-env"


def test_auth_raises_when_nothing_resolves(monkeypatch, tmp_path):
    monkeypatch.delenv("PALACE_API_KEY", raising=False)
    monkeypatch.delenv("PALACE_DAEMON_URL", raising=False)

    with pytest.raises(ValueError, match="api_url"):
        MemPalaceDaemonAdapter(env_file=tmp_path / "nope")


def test_auth_url_trailing_slash_is_stripped(monkeypatch, tmp_path):
    monkeypatch.delenv("PALACE_API_KEY", raising=False)
    monkeypatch.delenv("PALACE_DAEMON_URL", raising=False)
    a = MemPalaceDaemonAdapter(
        api_url="http://example/",
        api_key="k",
        env_file=tmp_path / "nope",
    )
    assert a.api_url == "http://example"
