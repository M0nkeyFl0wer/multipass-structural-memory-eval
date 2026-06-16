"""Tests for sme.eval.answer_relevancy."""

from __future__ import annotations

from types import SimpleNamespace

from sme.eval.answer_relevancy import grade_relevancy


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


def test_perfect_relevancy():
    client = _FakeOpenAIClient(
        _fake_openai_response(
            '{"score": 1.0, "rationale": "Fully answers the question."}'
        )
    )
    result = grade_relevancy(
        question="What is the capital of France?",
        answer="The capital of France is Paris.",
        client=client,
        use_cache=False,
    )
    assert result["error"] is None
    assert result["score"] == 1.0
    assert result["rationale"] == "Fully answers the question."


def test_partial_relevancy():
    client = _FakeOpenAIClient(
        _fake_openai_response(
            '{"score": 0.5, "rationale": "Misses the second part."}'
        )
    )
    result = grade_relevancy(
        question="What is the capital of France and its population?",
        answer="The capital of France is Paris.",
        client=client,
        use_cache=False,
    )
    assert result["error"] is None
    assert result["score"] == 0.5


def test_irrelevant():
    client = _FakeOpenAIClient(
        _fake_openai_response(
            '{"score": 0.0, "rationale": "Completely unrelated."}'
        )
    )
    result = grade_relevancy(
        question="What is the capital of France?",
        answer="The Eiffel Tower is in Paris.",
        client=client,
        use_cache=False,
    )
    assert result["error"] is None
    assert result["score"] == 0.0


def test_malformed_json():
    client = _FakeOpenAIClient(_fake_openai_response("not json"))
    result = grade_relevancy(
        question="What is the capital of France?",
        answer="Paris.",
        client=client,
        use_cache=False,
    )
    assert result["error"] is not None
    assert result["score"] is None  # conflation guard: None = "could not judge"


def test_api_failure():
    class _BrokenClient:
        def __init__(self):
            class _Completions:
                def create(self, *, model, messages, temperature=0.0):
                    raise RuntimeError("API down")

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    result = grade_relevancy(
        question="What is the capital of France?",
        answer="Paris.",
        client=_BrokenClient(),
        use_cache=False,
    )
    assert result["error"] is not None
    assert "judge call failed" in result["error"]
    assert result["score"] is None  # conflation guard: None = "could not judge"
