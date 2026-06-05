"""Tests for sme.eval.faithfulness."""

from __future__ import annotations

from types import SimpleNamespace

from sme.eval.faithfulness import grade_faithfulness


def _fake_openai_response(
    content: str,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


class _FakeOpenAIClient:
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


def test_perfect_score_when_all_claims_supported():
    client = _FakeOpenAIClient(
        _fake_openai_response(
            '{"claims": [{"text": "Paris is the capital of France", "verdict": "SUPPORTED"}]}'
        )
    )
    result = grade_faithfulness(
        context_string="Paris is the capital of France.",
        answer="Paris is the capital of France.",
        client=client,
    )
    assert result["error"] is None
    assert result["score"] == 1.0
    assert len(result["claims"]) == 1
    assert result["claims"][0]["verdict"] == "SUPPORTED"


def test_partial_score_when_some_unsupported():
    client = _FakeOpenAIClient(
        _fake_openai_response(
            '{"claims": [{"text": "Paris is the capital of France", "verdict": "SUPPORTED"}, '
            '{"text": "Paris has 10 million people", "verdict": "UNSUPPORTED"}]}'
        )
    )
    result = grade_faithfulness(
        context_string="Paris is the capital of France.",
        answer="Paris is the capital of France and has 10 million people.",
        client=client,
    )
    assert result["error"] is None
    assert result["score"] == 0.5
    assert len(result["claims"]) == 2


def test_zero_score_when_all_unsupported():
    client = _FakeOpenAIClient(
        _fake_openai_response(
            '{"claims": [{"text": "London is the capital of France", "verdict": "CONTRADICTED"}]}'
        )
    )
    result = grade_faithfulness(
        context_string="Paris is the capital of France.",
        answer="London is the capital of France.",
        client=client,
    )
    assert result["error"] is None
    assert result["score"] == 0.0
    assert len(result["claims"]) == 1


def test_error_handling_malformed_json():
    client = _FakeOpenAIClient(_fake_openai_response("not json"))
    result = grade_faithfulness(
        context_string="Paris is the capital of France.",
        answer="Paris is the capital of France.",
        client=client,
    )
    assert result["error"] is not None
    assert result["score"] == 0.0
    assert result["claims"] == []


def test_error_handling_api_failure():
    class _BrokenClient:
        def __init__(self):
            class _Completions:
                def create(self, *, model, messages, temperature=0.0):
                    raise RuntimeError("API down")

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    result = grade_faithfulness(
        context_string="Paris is the capital of France.",
        answer="Paris is the capital of France.",
        client=_BrokenClient(),
    )
    assert result["error"] is not None
    assert "judge call failed" in result["error"]
    assert result["score"] == 0.0
    assert result["claims"] == []
