"""Regression guard: the suite must not be able to reach paid APIs or the network.

If one of these fails, the autouse fixture in conftest.py has been weakened,
and a plain `pytest` (including the pre-commit hook) may be spending money.
"""

from __future__ import annotations

import os
import socket

import pytest

from sme.eval.judge_base import RubricJudge
from sme.eval.llm_clients import load_api_key


def test_no_llm_key_in_environment():
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        assert os.environ.get(var) is None, f"{var} is visible to tests"


@pytest.mark.parametrize("service,env", [
    ("openai", "OPENAI_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
])
def test_keyring_is_unreachable(service, env):
    # The real failure: load_api_key consults the keyring BEFORE the env.
    assert load_api_key(service, env_fallback=env) is None


def test_judge_cannot_build_a_live_client():
    # The exact probe the calibration tests use to decide whether to go live.
    assert RubricJudge(provider="openai")._resolve_client() is None


def test_outbound_connection_is_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError, match="network blocked"):
            s.connect(("192.0.2.1", 443))  # TEST-NET-1, never routable
    finally:
        s.close()
