"""Tests for judge variance / K-replicate functionality.

Covers ``grade_answer_replicated``: backward compatibility for K=1,
majority-vote aggregation for K>1, summed usage accounting, unanimous
agreement, and the all-ERROR fallback.

Fakes match the SDK response shape used in ``test_longmemeval_judge.py``:
an object with ``.choices[0].message.content`` and ``.usage.{prompt,
completion,total}_tokens``.
"""
from __future__ import annotations

from types import SimpleNamespace

from sme.eval.longmemeval_judge import grade_answer_replicated


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


class _ScriptedClient:
    """Returns a different response per call, drawn from a list."""

    def __init__(self, contents: list[str]):
        self._iter = iter(contents)
        self.calls: list[dict] = []
        outer = self

        class _Completions:
            def create(self, *, model, messages, temperature=0.0):
                outer.calls.append({"model": model, "messages": messages,
                                    "temperature": temperature})
                return _fake_response(next(outer._iter))

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


# --- backward compatibility: K=1 ------------------------------------------

def test_single_replicate_backward_compat():
    """K=1 returns exactly the grade_answer shape, no replicate diagnostics."""
    client = _ScriptedClient(['{"label": "CORRECT", "rationale": "good"}'])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hypothesis",
        replicates=1, client=client,
    )
    assert result["autoeval_label"] == "CORRECT"
    assert "replicates" not in result
    assert "label_counts" not in result
    assert "agreement_rate" not in result
    # Defaults to temperature=0.0 for K=1 (deterministic, paper setting).
    assert client.calls[0]["temperature"] == 0.0


def test_single_replicate_zero_also_delegates():
    """K=0 (or negative) treated as K=1 for safety."""
    client = _ScriptedClient(['{"label": "CORRECT", "rationale": "ok"}'])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=0, client=client,
    )
    assert result["autoeval_label"] == "CORRECT"
    assert "replicates" not in result


# --- majority vote aggregation ---------------------------------------------

def test_three_replicates_majority_vote():
    """2/3 CORRECT, 1/3 PARTIAL → majority CORRECT, agreement_rate=2/3."""
    client = _ScriptedClient([
        '{"label": "CORRECT", "rationale": "good"}',
        '{"label": "CORRECT", "rationale": "yes"}',
        '{"label": "PARTIAL", "rationale": "maybe"}',
    ])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hypothesis",
        replicates=3, client=client,
    )
    assert result["autoeval_label"] == "CORRECT"
    assert result["label_counts"]["CORRECT"] == 2
    assert result["label_counts"]["PARTIAL"] == 1
    assert result["agreement_rate"] == 2 / 3
    assert abs(result["flip_rate"] - 1 / 3) < 1e-9
    assert len(result["replicates"]) == 3
    # K>1 defaults to temperature=0.3 so variance can actually surface.
    assert client.calls[0]["temperature"] == 0.3


def test_replicates_all_agree():
    """Unanimous verdict → agreement_rate 1.0, flip_rate 0.0."""
    client = _ScriptedClient([
        '{"label": "INCORRECT", "rationale": "no"}',
        '{"label": "INCORRECT", "rationale": "nope"}',
        '{"label": "INCORRECT", "rationale": "wrong"}',
    ])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=3, client=client,
    )
    assert result["autoeval_label"] == "INCORRECT"
    assert result["agreement_rate"] == 1.0
    assert result["flip_rate"] == 0.0
    assert result["label_counts"] == {"INCORRECT": 3}


# --- deterministic tie-break -----------------------------------------------

def test_tie_break_two_replicates_split_prefers_correct():
    """K=2 with a 1-1 CORRECT/PARTIAL split → deterministic CORRECT.

    Counter.most_common() tie-break is arbitrary (depends on PYTHONHASHSEED);
    the pinned TIE_BREAK_ORDER (CORRECT > PARTIAL > INCORRECT > ABSTAIN) must
    win regardless of replicate order, so two researchers get the same label.
    """
    # PARTIAL listed first to prove order-independence of the result.
    client = _ScriptedClient([
        '{"label": "PARTIAL", "rationale": "partial first"}',
        '{"label": "CORRECT", "rationale": "correct second"}',
    ])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=2, client=client,
    )
    assert result["autoeval_label"] == "CORRECT"
    assert result["label_counts"] == {"PARTIAL": 1, "CORRECT": 1}
    assert result["agreement_rate"] == 0.5
    assert result["flip_rate"] == 0.5


def test_tie_break_higher_k_three_way_split_prefers_correct():
    """K=4 with a 2-1-1 split where two labels tie at the top.

    INCORRECT and CORRECT both reach 2 votes; CORRECT outranks INCORRECT in
    TIE_BREAK_ORDER, so the deterministic majority is CORRECT.
    """
    client = _ScriptedClient([
        '{"label": "INCORRECT", "rationale": "a"}',
        '{"label": "CORRECT", "rationale": "b"}',
        '{"label": "INCORRECT", "rationale": "c"}',
        '{"label": "CORRECT", "rationale": "d"}',
    ])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=4, client=client,
    )
    assert result["autoeval_label"] == "CORRECT"
    assert result["label_counts"]["CORRECT"] == 2
    assert result["label_counts"]["INCORRECT"] == 2
    assert result["agreement_rate"] == 0.5


def test_tie_break_partial_outranks_incorrect():
    """A PARTIAL/INCORRECT tie resolves to PARTIAL, not the lower-rank label."""
    client = _ScriptedClient([
        '{"label": "INCORRECT", "rationale": "a"}',
        '{"label": "PARTIAL", "rationale": "b"}',
    ])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=2, client=client,
    )
    assert result["autoeval_label"] == "PARTIAL"


# --- usage accounting -------------------------------------------------------

def test_replicates_usage_summed():
    """usage tokens are summed across all replicate calls."""
    client = _ScriptedClient([
        '{"label": "CORRECT", "rationale": "a"}',
        '{"label": "CORRECT", "rationale": "b"}',
    ])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=2, client=client,
    )
    assert result["usage"]["prompt_tokens"] == 20      # 10 * 2
    assert result["usage"]["completion_tokens"] == 10  #  5 * 2
    assert result["usage"]["total_tokens"] == 30       # 15 * 2


# --- temperature override --------------------------------------------------

def test_temperature_override():
    """Explicit temperature is forwarded to every replicate call."""
    client = _ScriptedClient([
        '{"label": "CORRECT", "rationale": "x"}',
        '{"label": "CORRECT", "rationale": "y"}',
    ])
    grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=2, client=client, temperature=0.7,
    )
    assert all(c["temperature"] == 0.7 for c in client.calls)


# --- failure-mode handling --------------------------------------------------

def test_all_replicates_error_returns_first_with_trace():
    """When every replicate ERRORs, return the first result with trace+summed usage."""
    # Malformed JSON triggers ERROR label inside grade_answer.
    client = _ScriptedClient(["garbage", "also garbage", "still garbage"])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=3, client=client,
    )
    assert result["autoeval_label"] == "ERROR"
    assert "replicates" in result
    assert len(result["replicates"]) == 3
    assert result["usage"]["total_tokens"] == 45  # 15 * 3
    # Diagnostic keys present (empty/zero) so the shape matches the K>1
    # success path — no AttributeError/KeyError for downstream consumers.
    assert result["label_counts"] == {}
    assert result["agreement_rate"] == 0.0
    assert result["flip_rate"] == 1.0


def test_mixed_error_and_valid_excludes_error_from_vote():
    """ERROR replicates don't get a vote; remaining labels decide majority."""
    client = _ScriptedClient([
        "garbage-not-json",                                # ERROR
        '{"label": "CORRECT", "rationale": "a"}',
        '{"label": "CORRECT", "rationale": "b"}',
    ])
    result = grade_answer_replicated(
        "single-session-user", "q?", "gold", "hyp",
        replicates=3, client=client,
    )
    assert result["autoeval_label"] == "CORRECT"
    assert result["label_counts"] == {"CORRECT": 2}
    # agreement_rate is over non-ERROR labels only.
    assert result["agreement_rate"] == 1.0
    # But usage still sums across all 3 calls.
    assert result["usage"]["total_tokens"] == 45
