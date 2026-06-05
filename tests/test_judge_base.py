"""Tests for sme.eval.judge_base."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional


from sme.eval.judge_base import RubricJudge


def _fake_openai_response(
    content: str,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


class _FakeOpenAIClient:
    """Minimal stand-in for openai.OpenAI()."""

    def __init__(self, response_or_factory):
        self._resp = response_or_factory
        self.calls: list[dict] = []

        outer = self

        class _Completions:
            def create(self, *, model, messages, temperature=0.0):
                outer.calls.append(
                    {"model": model, "messages": messages, "temperature": temperature}
                )
                resp = outer._resp
                if callable(resp):
                    return resp(model=model, messages=messages)
                if isinstance(resp, Exception):
                    raise resp
                return resp

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class _FlakyOpenAIClient:
    """Fails N times, then succeeds with the given content."""

    def __init__(
        self,
        fail_n: int,
        then_content: str,
        final_exc: Optional[Exception] = None,
    ):
        self.fail_n = fail_n
        self.then_content = then_content
        self.final_exc = final_exc
        self.attempts = 0
        outer = self

        class _Completions:
            def create(self, *, model, messages, temperature=0.0):
                outer.attempts += 1
                if outer.attempts <= outer.fail_n:
                    raise RuntimeError(f"transient {outer.attempts}")
                if outer.final_exc is not None:
                    raise outer.final_exc
                return _fake_openai_response(outer.then_content)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class _FakeAnthropicClient:
    """Minimal stand-in for anthropic.Anthropic()."""

    def __init__(
        self,
        content: str,
        *,
        input_tokens: int = 12,
        output_tokens: int = 4,
        cache_read: int = 9,
        cache_creation: int = 3,
    ) -> None:
        self.calls: list[dict] = []
        outer = self

        class _Messages:
            def create(self, *, model, max_tokens, system, messages):
                outer.calls.append(
                    {
                        "model": model,
                        "max_tokens": max_tokens,
                        "system": system,
                        "messages": messages,
                    }
                )
                return SimpleNamespace(
                    content=[SimpleNamespace(type="text", text=content)],
                    usage=SimpleNamespace(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_read_input_tokens=cache_read,
                        cache_creation_input_tokens=cache_creation,
                    ),
                )

        self.messages = _Messages()


# --- happy path -------------------------------------------------------------


def test_judge_openai_returns_content():
    client = _FakeOpenAIClient(
        _fake_openai_response('{"label": "CORRECT", "rationale": "ok"}')
    )
    judge = RubricJudge(provider="openai", client=client)
    result = judge.judge("rubric text\n", "body text\n")
    assert result["error"] is None
    assert result["content"] == '{"label": "CORRECT", "rationale": "ok"}'
    assert result["usage"]["prompt_tokens"] == 10
    assert result["usage"]["total_tokens"] == 15
    assert client.calls[0]["model"] == "gpt-4o-2024-08-06"
    assert len(client.calls[0]["messages"]) == 1
    assert client.calls[0]["messages"][0]["role"] == "user"
    assert "rubric text" in client.calls[0]["messages"][0]["content"]
    assert "body text" in client.calls[0]["messages"][0]["content"]


def test_judge_openrouter_returns_content():
    client = _FakeOpenAIClient(_fake_openai_response('{"label": "CORRECT"}'))
    judge = RubricJudge(provider="openrouter", client=client)
    result = judge.judge("rubric", "body")
    assert result["error"] is None
    assert result["content"] == '{"label": "CORRECT"}'
    assert client.calls[0]["model"] == "openai/gpt-4o-2024-08-06"


def test_judge_anthropic_returns_content():
    client = _FakeAnthropicClient(
        '{"label": "PARTIAL", "rationale": "close"}'
    )
    judge = RubricJudge(provider="anthropic", client=client)
    result = judge.judge("rubric text", "body text")
    assert result["error"] is None
    assert result["content"] == '{"label": "PARTIAL", "rationale": "close"}'
    assert result["usage"]["prompt_tokens"] == 12
    assert result["usage"]["cache_read_input_tokens"] == 9
    sys_block = client.calls[0]["system"][0]
    assert sys_block["cache_control"] == {"type": "ephemeral"}
    assert "rubric text" in sys_block["text"]
    user_msg = client.calls[0]["messages"][0]
    assert user_msg["role"] == "user"
    assert "body text" in user_msg["content"]


# --- retries ---------------------------------------------------------------


def test_judge_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("sme.eval.judge_base.time.sleep", lambda *_: None)
    client = _FlakyOpenAIClient(
        fail_n=2,
        then_content='{"label": "CORRECT", "rationale": "ok"}',
    )
    judge = RubricJudge(provider="openai", client=client)
    result = judge.judge("rubric", "body")
    assert result["error"] is None
    assert result["content"] == '{"label": "CORRECT", "rationale": "ok"}'
    assert client.attempts == 3


def test_judge_returns_error_after_max_retries(monkeypatch):
    monkeypatch.setattr("sme.eval.judge_base.time.sleep", lambda *_: None)
    client = _FlakyOpenAIClient(fail_n=99, then_content="never")
    judge = RubricJudge(provider="openai", client=client)
    result = judge.judge("rubric", "body")
    assert result["error"] is not None
    assert "judge call failed" in result["error"]
    assert client.attempts == 3


# --- error handling --------------------------------------------------------


def test_judge_no_client_returns_error(monkeypatch):
    monkeypatch.setattr(
        "sme.eval.judge_base._default_client", lambda provider: None
    )
    judge = RubricJudge(provider="openai", client=None)
    result = judge.judge("rubric", "body")
    assert result["error"] is not None
    assert "no API key in keyring" in result["error"]


def test_judge_unknown_provider_returns_error():
    judge = RubricJudge(provider="bogus")
    result = judge.judge("rubric", "body")
    assert result["error"] is not None
    assert "unknown provider" in result["error"]


# --- parse_reply -----------------------------------------------------------


def test_parse_reply_strips_code_fences():
    raw = '```json\n{"label": "CORRECT", "rationale": "y"}\n```'
    parsed = RubricJudge.parse_reply(raw)
    assert parsed == {"label": "CORRECT", "rationale": "y"}


def test_parse_reply_handles_extra_prose():
    raw = (
        'Sure! Here is my verdict:\n'
        '{"label":"PARTIAL","rationale":"close"}\n'
        'Done.'
    )
    parsed = RubricJudge.parse_reply(raw)
    assert parsed == {"label": "PARTIAL", "rationale": "close"}


def test_parse_reply_empty_returns_none():
    assert RubricJudge.parse_reply("") is None


def test_parse_reply_malformed_json_returns_none():
    assert RubricJudge.parse_reply("not json") is None


def test_parse_reply_strips_code_fences_no_json_returns_none():
    assert RubricJudge.parse_reply("```json\nnot json\n```") is None
