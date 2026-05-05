"""Tests for sme.eval.llm_clients.

The provider clients wrap external SDKs we don't want to import in CI,
so the tests exercise:

  - the prompt-splitting helper (`split_for_caching`) against real
    SME prompt templates,
  - the keyring loader's env-var fallback path,
  - the StubLLMClient's deterministic output, and
  - the AnthropicLLMClient.complete() against a fake `anthropic.Anthropic`
    that records the request shape (system block + cache_control + thinking).

For OpenAI / OpenRouter we cover the request shape via the judge's
multi-provider tests in test_longmemeval_judge.py — they share the
same OpenAI SDK shape so duplicating them here is just noise.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from sme.eval.llm_clients import (
    ANTHROPIC_DEFAULT_MODEL,
    OPENROUTER_DEFAULT_JUDGE_MODEL,
    StubLLMClient,
    load_api_key,
    split_for_caching,
)


# --- split_for_caching ----------------------------------------------------


def test_split_for_caching_article_prompt():
    prompt = (
        "You compile concise wiki articles.\n"
        "Style guide: ...\n\n"
        "Source path: notes/foo.md\n"
        "Source content:\n---\nbody\n---\n"
    )
    system, user = split_for_caching(prompt)
    assert "wiki articles" in system
    assert "Style guide" in system
    assert user.startswith("Source path: notes/foo.md")


def test_split_for_caching_index_prompt():
    prompt = (
        "Build a wiki index.\n\n"
        "Articles:\n- a.md\n- b.md\n"
    )
    system, user = split_for_caching(prompt)
    assert system == "Build a wiki index."
    assert user.startswith("Articles:")


def test_split_for_caching_question_prompt():
    prompt = (
        "Scoring rubric (Information Extraction):\n"
        "- CORRECT: ...\n\n"
        "Question: What did I buy?\n"
        "Gold answer: kayak\n"
    )
    system, user = split_for_caching(prompt)
    assert "Information Extraction" in system
    assert user.startswith("Question:")


def test_split_for_caching_no_marker_returns_empty_system():
    prompt = "no recognizable marker here"
    system, user = split_for_caching(prompt)
    assert system == ""
    assert user == prompt


# --- load_api_key ---------------------------------------------------------


def test_load_api_key_env_fallback_when_keyring_missing(monkeypatch):
    """If `secret-tool` is unavailable, env_fallback is used."""

    def fake_run(cmd, *a, **kw):
        # Simulate `secret-tool` not installed.
        raise FileNotFoundError("secret-tool not in PATH")

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("SME_TEST_KEY", "envkey-123")
    assert load_api_key("anything", env_fallback="SME_TEST_KEY") == "envkey-123"


def test_load_api_key_returns_none_when_no_source(monkeypatch):
    def fake_run(cmd, *a, **kw):
        raise FileNotFoundError("secret-tool not in PATH")

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.delenv("SME_TEST_KEY", raising=False)
    assert load_api_key("anything", env_fallback="SME_TEST_KEY") is None


def test_load_api_key_uses_keyring_when_available(monkeypatch):
    captured: dict = {}

    def fake_run(cmd, *a, **kw):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ring-key-456\n", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    out = load_api_key("anthropic")
    assert out == "ring-key-456"
    assert captured["cmd"] == ["secret-tool", "lookup", "service", "anthropic"]


def test_load_api_key_falls_through_when_keyring_returns_empty(monkeypatch):
    def fake_run(cmd, *a, **kw):
        return SimpleNamespace(returncode=1, stdout="", stderr="not found")

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("SME_TEST_KEY", "envkey-only")
    assert load_api_key("anthropic", env_fallback="SME_TEST_KEY") == "envkey-only"


# --- StubLLMClient --------------------------------------------------------


def test_stub_client_article_prompt_includes_source_path():
    client = StubLLMClient()
    out = client.complete(
        "Source path: notes/dogs.md\n"
        "Source content:\n---\nA Border Collie is a herding dog.\n---\n"
    )
    assert "Stub summary of notes/dogs.md" in out
    assert "Border Collie" in out


def test_stub_client_index_prompt_falls_through():
    client = StubLLMClient()
    out = client.complete("Articles:\n- a.md\n- b.md\n")
    assert "Index" in out
    assert "stub-generated" in out


# --- AnthropicLLMClient (fake SDK) ---------------------------------------


def _install_fake_anthropic(monkeypatch):
    """Stuff a fake `anthropic` module into sys.modules and capture the
    constructor + messages.create call shape."""
    state: dict = {"client_kwargs": None, "create_kwargs": None}

    class _Messages:
        def create(self, **kwargs):
            state["create_kwargs"] = kwargs
            return SimpleNamespace(
                content=[SimpleNamespace(
                    type="text",
                    text="Article body produced by anthropic-fake.",
                )],
                usage=SimpleNamespace(
                    input_tokens=42,
                    output_tokens=11,
                    cache_read_input_tokens=30,
                    cache_creation_input_tokens=12,
                ),
            )

    class _Anthropic:
        def __init__(self, **kwargs):
            state["client_kwargs"] = kwargs
            self.messages = _Messages()

    fake_module = SimpleNamespace(Anthropic=_Anthropic)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return state


def test_anthropic_client_caches_system_prefix_and_uses_adaptive_thinking(monkeypatch):
    state = _install_fake_anthropic(monkeypatch)
    # Force keyring lookup to succeed without actually calling secret-tool.
    monkeypatch.setattr(
        "sme.eval.llm_clients.load_api_key",
        lambda service, **kw: "fake-anthropic-key",
    )

    from sme.eval.llm_clients import AnthropicLLMClient
    client = AnthropicLLMClient()

    out = client.complete(
        "You compile concise wiki articles.\n"
        "Style guide: write 300 words.\n\n"
        "Source path: notes/foo.md\n"
        "Source content:\n---\nbody\n---\n"
    )

    assert out == "Article body produced by anthropic-fake."
    # API key was passed without being echoed.
    assert state["client_kwargs"]["api_key"] == "fake-anthropic-key"

    create_kwargs = state["create_kwargs"]
    assert create_kwargs["model"] == ANTHROPIC_DEFAULT_MODEL
    # System block carries cache_control on the static prefix.
    assert isinstance(create_kwargs["system"], list)
    assert create_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "wiki articles" in create_kwargs["system"][0]["text"]
    # Per-call body goes in the user message, marker-first.
    user_msg = create_kwargs["messages"][0]
    assert user_msg["role"] == "user"
    assert user_msg["content"].startswith("Source path: notes/foo.md")
    # Adaptive thinking is on, with display omitted by default.
    assert create_kwargs["thinking"] == {"type": "adaptive", "display": "omitted"}


def test_anthropic_client_handles_unsplittable_prompt(monkeypatch):
    """If the prompt has no recognized marker, the system block is empty
    and the entire prompt becomes the user message — no caching happens
    but the call still goes through."""
    state = _install_fake_anthropic(monkeypatch)
    monkeypatch.setattr(
        "sme.eval.llm_clients.load_api_key",
        lambda service, **kw: "k",
    )

    from sme.eval.llm_clients import AnthropicLLMClient
    client = AnthropicLLMClient()
    client.complete("plain prompt with no marker")

    create_kwargs = state["create_kwargs"]
    assert "system" not in create_kwargs  # no system block at all
    assert create_kwargs["messages"][0]["content"] == "plain prompt with no marker"


def test_anthropic_client_raises_when_no_key(monkeypatch):
    monkeypatch.setattr(
        "sme.eval.llm_clients.load_api_key", lambda service, **kw: None
    )
    # The class probes for the SDK before checking keys, so install a fake.
    _install_fake_anthropic(monkeypatch)
    from sme.eval.llm_clients import AnthropicLLMClient

    with pytest.raises(SystemExit) as excinfo:
        AnthropicLLMClient()
    assert "no Anthropic API key" in str(excinfo.value)


# --- OpenRouter default model is the namespaced GPT-4o ---------------------


def test_openrouter_default_model_is_namespaced():
    """OpenRouter expects model IDs of the form `<provider>/<model>`."""
    assert OPENROUTER_DEFAULT_JUDGE_MODEL == "openai/gpt-4o-2024-08-06"
