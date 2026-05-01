"""Tests for sme.eval.longmemeval_judge.

The judge wraps an OpenAI-shaped client; we mock that client so the
tests work without ``openai`` installed and without a network call.
The fakes match the SDK's response object shape minimally: an object
with ``.choices[0].message.content`` and ``.usage.{prompt,completion,total}_tokens``.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from sme.eval.longmemeval_judge import (
    DEFAULT_JUDGE_MODEL,
    _parse_judge_reply,
    grade_answer,
)


def _fake_response(content: str,
                   prompt_tokens: int = 10,
                   completion_tokens: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


class _FakeClient:
    """Minimal stand-in for openai.OpenAI()."""

    def __init__(self, response_or_factory):
        self._resp = response_or_factory
        self.calls: list[dict] = []

        outer = self

        class _Completions:
            def create(self, *, model, messages, temperature=0.0):
                outer.calls.append({"model": model, "messages": messages,
                                    "temperature": temperature})
                resp = outer._resp
                if callable(resp):
                    return resp(model=model, messages=messages)
                if isinstance(resp, Exception):
                    raise resp
                return resp

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


# --- happy path -------------------------------------------------------------

def test_grade_answer_correct_label():
    client = _FakeClient(_fake_response(
        '{"label": "CORRECT", "rationale": "matches gold fact."}'
    ))
    out = grade_answer(
        question_type="single-session-user",
        question="What did I buy?",
        gold_answer="A kayak",
        hypothesis="You bought a kayak.",
        client=client,
    )
    assert out["autoeval_label"] == "CORRECT"
    assert out["judge_model"] == DEFAULT_JUDGE_MODEL
    assert out["rationale"].startswith("matches gold")
    assert out["usage"]["prompt_tokens"] == 10
    assert out["usage"]["total_tokens"] == 15
    # Sanity: prompt contained the IE rubric.
    sent = client.calls[0]["messages"][0]["content"]
    assert "Information Extraction" in sent
    assert "A kayak" in sent


def test_grade_answer_incorrect_label():
    client = _FakeClient(_fake_response(
        '{"label": "INCORRECT", "rationale": "wrong vehicle"}'
    ))
    out = grade_answer(
        question_type="single-session-user",
        question="What did I buy?",
        gold_answer="A kayak",
        hypothesis="A submarine",
        client=client,
    )
    assert out["autoeval_label"] == "INCORRECT"


def test_grade_answer_abstention_returns_abstain():
    client = _FakeClient(_fake_response(
        '{"label": "ABSTAIN", "rationale": "system correctly refused"}'
    ))
    out = grade_answer(
        question_type="abstention",
        question="What did I say about my submarine?",
        gold_answer="abstain",
        hypothesis="I don't know.",
        client=client,
    )
    assert out["autoeval_label"] == "ABSTAIN"
    sent = client.calls[0]["messages"][0]["content"]
    assert "Abstention" in sent


def test_grade_answer_knowledge_update_uses_ku_rubric():
    client = _FakeClient(_fake_response(
        '{"label": "CORRECT", "rationale": "matches latest value"}'
    ))
    grade_answer(
        question_type="knowledge-update",
        question="Where do I work?",
        gold_answer="Acme",
        hypothesis="You work at Acme.",
        client=client,
    )
    sent = client.calls[0]["messages"][0]["content"]
    assert "Knowledge Update" in sent
    assert "MOST RECENT" in sent  # KU-specific verbiage


def test_grade_answer_temporal_uses_temporal_rubric():
    client = _FakeClient(_fake_response(
        '{"label": "PARTIAL", "rationale": "month right, year off"}'
    ))
    out = grade_answer(
        question_type="temporal-reasoning",
        question="When did I move?",
        gold_answer="March 2023",
        hypothesis="March 2024",
        client=client,
    )
    assert out["autoeval_label"] == "PARTIAL"
    sent = client.calls[0]["messages"][0]["content"]
    assert "Temporal Reasoning" in sent


# --- API key handling -------------------------------------------------------

def test_grade_answer_no_api_key_returns_error_label(monkeypatch):
    """When client is None and no key is present, return ERROR with a
    clear rationale rather than raising."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = grade_answer(
        question_type="single-session-user",
        question="q",
        gold_answer="g",
        hypothesis="h",
        client=None,
    )
    assert out["autoeval_label"] == "ERROR"
    assert "OPENAI_API_KEY" in out["rationale"]


# --- retries / transient errors --------------------------------------------

class _FlakyClient:
    """Fails N times, then succeeds with the given content."""

    def __init__(self, fail_n: int, then_content: str,
                 final_exc: Optional[Exception] = None):
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
                return _fake_response(outer.then_content)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def test_grade_answer_retries_then_succeeds(monkeypatch):
    # Make sleep instant so the test isn't slow.
    monkeypatch.setattr("sme.eval.longmemeval_judge.time.sleep", lambda *_: None)
    client = _FlakyClient(
        fail_n=2,
        then_content='{"label": "CORRECT", "rationale": "ok"}',
    )
    out = grade_answer(
        question_type="single-session-user",
        question="q", gold_answer="g", hypothesis="h",
        client=client,
    )
    assert out["autoeval_label"] == "CORRECT"
    assert client.attempts == 3


def test_grade_answer_returns_error_after_max_retries(monkeypatch):
    monkeypatch.setattr("sme.eval.longmemeval_judge.time.sleep", lambda *_: None)
    client = _FlakyClient(fail_n=99, then_content="never")
    out = grade_answer(
        question_type="single-session-user",
        question="q", gold_answer="g", hypothesis="h",
        client=client,
    )
    assert out["autoeval_label"] == "ERROR"
    assert "judge call failed" in out["rationale"]
    # Three retry attempts before bailing.
    assert client.attempts == 3


# --- malformed responses ---------------------------------------------------

def test_grade_answer_handles_malformed_json():
    client = _FakeClient(_fake_response("not even close to json"))
    out = grade_answer(
        question_type="single-session-user",
        question="q", gold_answer="g", hypothesis="h",
        client=client,
    )
    assert out["autoeval_label"] == "ERROR"
    assert "no JSON object" in out["rationale"] or "malformed" in out["rationale"]


def test_grade_answer_handles_unknown_label():
    client = _FakeClient(_fake_response(
        '{"label": "MAYBE", "rationale": "?"}'
    ))
    out = grade_answer(
        question_type="single-session-user",
        question="q", gold_answer="g", hypothesis="h",
        client=client,
    )
    assert out["autoeval_label"] == "ERROR"
    assert "unknown judge label" in out["rationale"]


def test_grade_answer_strips_code_fences():
    client = _FakeClient(_fake_response(
        '```json\n{"label": "CORRECT", "rationale": "y"}\n```'
    ))
    out = grade_answer(
        question_type="single-session-user",
        question="q", gold_answer="g", hypothesis="h",
        client=client,
    )
    assert out["autoeval_label"] == "CORRECT"


def test_parse_judge_reply_empty():
    label, rationale = _parse_judge_reply("")
    assert label == "ERROR"


def test_parse_judge_reply_extra_prose_around_json():
    label, rationale = _parse_judge_reply(
        'Sure! Here is my verdict:\n{"label":"PARTIAL","rationale":"close"}\nDone.'
    )
    assert label == "PARTIAL"
    assert rationale == "close"


# --- unknown question_type doesn't crash -----------------------------------

def test_grade_answer_unknown_question_type_still_calls_judge():
    client = _FakeClient(_fake_response(
        '{"label": "CORRECT", "rationale": "ok"}'
    ))
    out = grade_answer(
        question_type="made-up-type",
        question="q", gold_answer="g", hypothesis="h",
        client=client,
    )
    assert out["autoeval_label"] == "CORRECT"
    sent = client.calls[0]["messages"][0]["content"]
    assert "Generic" in sent  # falls back to generic rubric
