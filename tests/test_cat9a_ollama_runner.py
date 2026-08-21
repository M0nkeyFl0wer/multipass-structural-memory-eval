"""OllamaRunner tool-use loop — offline tests via an injected fake.

No network, no localhost, no Ollama daemon. A fake client scripts the
OpenAI-style /api/chat protocol so the loop logic (invoke -> execute ->
feed result back -> answer), the forced-mode shim (Ollama has no native
tool_choice=any), the unknown-tool path, API-error surfacing, and
arguments-as-JSON-string normalization are all proven deterministically.
"""

from __future__ import annotations

import json

from sme.adapters.base import HarnessDescriptor, ProbeResult
from sme.harness.runner import (
    OllamaRunner,
    _safe_tool_name,
)


# --- fake Ollama /api/chat surface ------------------------------------


class _FakeOllama:
    """Records each .chat() call and returns scripted responses.

    ``behavior(messages, tools) -> dict`` returns an Ollama-shaped
    response, i.e. ``{"message": {"content", "tool_calls"}, ...}``.
    """

    def __init__(self, behavior):
        self._behavior = behavior
        self.calls: list[dict] = []

    def chat(self, model, messages, tools) -> dict:
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self._behavior(messages, tools)


def _tool_call(name, arguments):
    return {"function": {"name": name, "arguments": arguments}}


def _resp(content="", tool_calls=None, prompt_eval_count=10, eval_count=5):
    return {
        "message": {"content": content, "tool_calls": tool_calls or []},
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
    }


def _last_is_tool_result(messages) -> bool:
    return bool(messages) and messages[-1].get("role") == "tool"


def _manifest(execute=None):
    props = {}
    if execute is not None:
        props["execute"] = execute
    return [
        HarnessDescriptor(
            name="memory_search",
            kind="tool_call",
            probe_fn=lambda: ProbeResult(success=True, output="probe-output"),
            description="search memory",
            properties=props,
        )
    ]


# --- invoke -> ground happy path --------------------------------------


def test_runner_invokes_then_grounds_answer():
    tool = _safe_tool_name("memory_search")

    def behavior(messages, tools):
        if _last_is_tool_result(messages):
            # echo the retrieved content -> a grounded answer
            return _resp(content=messages[-1]["content"])
        return _resp(tool_calls=[_tool_call(tool, {"query": "x"})])

    client = _FakeOllama(behavior)
    runner = OllamaRunner(client=client)
    trace = runner.run(
        "when was the DCM investigation opened?",
        _manifest(execute=lambda args: "FDA opened the DCM investigation in July 2018."),
    )

    assert trace.invoked is True
    assert trace.call_through is True
    assert "July 2018" in trace.final_text
    assert len(trace.tool_calls_attempted) == 1
    assert runner.calls == 2
    assert runner.usage["input_tokens"] > 0
    assert runner.name == "ollama:qwen2.5"


# --- model declines to invoke -----------------------------------------


def test_runner_answers_without_invoking():
    def behavior(messages, tools):
        return _resp(content="I already know: 1492.")

    runner = OllamaRunner(client=_FakeOllama(behavior))
    trace = runner.run("easy question", _manifest(execute=lambda a: "unused"))

    assert trace.invoked is False
    assert trace.call_through is False
    assert trace.final_text == "I already know: 1492."
    assert runner.calls == 1


# --- forced-mode shim fires a synthetic call --------------------------


def test_forced_mode_synthesizes_call_when_model_declines():
    tool = _safe_tool_name("memory_search")

    def behavior(messages, tools):
        if _last_is_tool_result(messages):
            return _resp(content="grounded answer")
        # Model declines to call a tool on turn 0.
        return _resp(content="")

    runner = OllamaRunner(client=_FakeOllama(behavior), invocation_mode="forced")
    trace = runner.run("q", _manifest(execute=lambda a: "synthetic-context"))

    # The shim fabricated a call to the first tool with {"query": question}.
    assert trace.invoked is True
    assert trace.call_through is True
    assert len(trace.tool_calls_attempted) == 1
    assert trace.tool_calls_attempted[0].name == tool
    assert trace.tool_calls_attempted[0].arguments == {"query": "q"}
    assert trace.final_text == "grounded answer"


# --- unknown tool path ------------------------------------------------


def test_runner_handles_unknown_tool():
    def behavior(messages, tools):
        if _last_is_tool_result(messages):
            return _resp(content="fallback answer")
        return _resp(tool_calls=[_tool_call("bogus_tool", {})])

    runner = OllamaRunner(client=_FakeOllama(behavior))
    trace = runner.run("q", _manifest(execute=lambda a: "ctx"))

    assert len(trace.tool_calls_attempted) == 1
    assert trace.tool_calls_attempted[0].succeeded is False
    assert "unknown tool" in (trace.tool_calls_attempted[0].error or "")


# --- API error surfaces as trace state, not a raise -------------------


def test_runner_surfaces_api_error():
    def behavior(messages, tools):
        raise RuntimeError("connection refused")

    runner = OllamaRunner(client=_FakeOllama(behavior))
    trace = runner.run("q", _manifest(execute=lambda a: "ctx"))
    assert trace.error is not None
    assert "connection refused" in trace.error


# --- arguments arriving as a JSON string are normalized ---------------


def test_runner_normalizes_json_string_arguments():
    tool = _safe_tool_name("memory_search")
    seen_args = {}

    def execute(args):
        seen_args.update(args)
        return "FDA opened the DCM investigation in July 2018."

    def behavior(messages, tools):
        if _last_is_tool_result(messages):
            return _resp(content=messages[-1]["content"])
        # arguments delivered as a JSON *string*, not a dict.
        return _resp(
            tool_calls=[_tool_call(tool, json.dumps({"query": "dcm"}))]
        )

    runner = OllamaRunner(client=_FakeOllama(behavior))
    trace = runner.run("q", _manifest(execute=execute))

    assert seen_args == {"query": "dcm"}
    assert trace.call_through is True
    assert "July 2018" in trace.final_text


# --- bare-callable client is accepted ---------------------------------


def test_runner_accepts_bare_callable_client():
    def client(model, messages, tools):
        return _resp(content="answered")

    runner = OllamaRunner(client=client)
    trace = runner.run("q", _manifest(execute=lambda a: "ctx"))
    assert trace.final_text == "answered"
    assert runner.calls == 1
