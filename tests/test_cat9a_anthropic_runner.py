"""AnthropicRunner tool-use loop — offline tests via an injected fake.

No API key, no network, no spend. A fake Anthropic client scripts the
tool-use protocol so the loop logic (invoke -> execute -> feed result
back -> answer), the auto/forced policy, usage accumulation, and the
unknown-tool path are all proven deterministically.
"""

from __future__ import annotations

from sme.adapters.base import HarnessDescriptor, ProbeResult
from sme.harness.runner import (
    AnthropicRunner,
    _safe_tool_name,
    manifest_to_tools,
)


# --- fake Anthropic SDK surface ---------------------------------------


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    def __init__(self, i=10, o=5):
        self.input_tokens = i
        self.output_tokens = o


class _Resp:
    def __init__(self, content):
        self.content = content
        self.usage = _Usage()


class _Messages:
    def __init__(self, behavior):
        self._behavior = behavior
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._behavior(kwargs)


class _FakeAnthropic:
    def __init__(self, behavior):
        self.messages = _Messages(behavior)


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


def _last_is_tool_result(kwargs) -> bool:
    content = kwargs["messages"][-1]["content"]
    return isinstance(content, list) and any(
        isinstance(c, dict) and c.get("type") == "tool_result" for c in content
    )


# --- invoke -> answer happy path --------------------------------------


def test_runner_invokes_then_grounds_answer():
    tool = _safe_tool_name("memory_search")

    def behavior(kwargs):
        if _last_is_tool_result(kwargs):
            # echo the retrieved content -> a grounded answer
            tr = kwargs["messages"][-1]["content"][0]
            return _Resp([_Block(type="text", text=tr["content"])])
        return _Resp(
            [_Block(type="tool_use", id="t1", name=tool, input={"query": "x"})]
        )

    runner = AnthropicRunner(client=_FakeAnthropic(behavior))
    trace = runner.run("when was the DCM investigation opened?", _manifest(
        execute=lambda args: "FDA opened the DCM investigation in July 2018."
    ))

    assert trace.invoked is True
    assert trace.call_through is True
    assert "July 2018" in trace.final_text
    assert len(trace.tool_calls_attempted) == 1
    assert runner.calls == 2
    assert runner.usage["input_tokens"] > 0


# --- model declines to invoke -----------------------------------------


def test_runner_answers_without_invoking():
    def behavior(kwargs):
        return _Resp([_Block(type="text", text="I already know: 1492.")])

    runner = AnthropicRunner(client=_FakeAnthropic(behavior))
    trace = runner.run("easy question", _manifest(execute=lambda a: "unused"))

    assert trace.invoked is False
    assert trace.call_through is False
    assert trace.final_text == "I already know: 1492."
    assert runner.calls == 1


# --- forced mode sets tool_choice on the first turn only --------------


def test_forced_mode_first_turn_tool_choice():
    tool = _safe_tool_name("memory_search")

    def behavior(kwargs):
        if _last_is_tool_result(kwargs):
            return _Resp([_Block(type="text", text="done")])
        return _Resp(
            [_Block(type="tool_use", id="t1", name=tool, input={"query": "x"})]
        )

    runner = AnthropicRunner(
        client=_FakeAnthropic(behavior), invocation_mode="forced"
    )
    runner.run("q", _manifest(execute=lambda a: "ctx"))

    calls = runner._client.messages.calls
    assert calls[0].get("tool_choice") == {"type": "any"}  # forced on turn 0
    assert "tool_choice" not in calls[1]  # auto afterward so it can finish


# --- unknown tool path ------------------------------------------------


def test_runner_handles_unknown_tool():
    def behavior(kwargs):
        if _last_is_tool_result(kwargs):
            return _Resp([_Block(type="text", text="fallback answer")])
        return _Resp(
            [_Block(type="tool_use", id="t1", name="bogus_tool", input={})]
        )

    runner = AnthropicRunner(client=_FakeAnthropic(behavior))
    trace = runner.run("q", _manifest(execute=lambda a: "ctx"))

    assert len(trace.tool_calls_attempted) == 1
    assert trace.tool_calls_attempted[0].succeeded is False
    assert "unknown tool" in (trace.tool_calls_attempted[0].error or "")


# --- API error surfaces as trace state, not a raise -------------------


def test_runner_surfaces_api_error():
    def behavior(kwargs):
        raise RuntimeError("rate limited")

    runner = AnthropicRunner(client=_FakeAnthropic(behavior))
    trace = runner.run("q", _manifest(execute=lambda a: "ctx"))
    assert trace.error is not None
    assert "rate limited" in trace.error


# --- tool definition building -----------------------------------------


def test_manifest_to_tools_sanitizes_names_and_maps():
    manifest = [
        HarnessDescriptor(
            name="memory search!", kind="tool_call",
            probe_fn=lambda: ProbeResult(success=True),
        )
    ]
    tools, name_map = manifest_to_tools(manifest)
    assert tools[0]["name"] == "memory_search_"
    assert "input_schema" in tools[0]
    assert name_map["memory_search_"] is manifest[0]
