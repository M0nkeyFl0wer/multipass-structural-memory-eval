"""Model-runner shim for Category 9a (invocation rate — The Handshake).

Cat 9b asks "can an external caller reach each declared surface?" and
answers it with a mock invoker. Cat 9a asks the harder, agentic
question: **when a real model is handed the memory tool and a question
the memory system can answer, does the model actually reach for it —
and does the retrieved context land in its reply?**

That requires putting a model in the loop. A ``ModelRunner`` takes one
question plus the adapter's harness manifest, wires the declared tools
into a model turn, lets the model decide whether to invoke (and runs
the tool-use loop to completion), and returns a ``HandshakeTrace``: the
final reply text, every tool call attempted, and which ones succeeded.

The scorer (``sme.categories.harness_integration.run_cat9a``) consumes
the trace. The Cat 1 substring matcher runs against ``final_text`` — a
tool response buried in a conversation the model ignores does **not**
count as retrieval. That asymmetry is the whole point of Cat 9.

This module ships ``MockRunner`` (deterministic, no API, no cost) as
the floor — mirroring how 9b shipped against a mock invoker first. Real
runners (``AnthropicRunner`` first, then local ``OllamaRunner``) layer
on top behind a cost gate and are never exercised by the test suite.

Tool-execution convention
--------------------------
For 9a a descriptor must be *executable by the model*, not just
probeable. The runner looks, in order, for:

  1. ``descriptor.properties["execute"]`` — ``Callable[[dict], str]``
     taking the model's tool arguments and returning the tool response
     text. This is the richer convention 9a/9c/9d want; adapters add it
     alongside ``probe_fn`` (spec v8 § Cat 9 says park it in
     ``properties`` until the base contract grows a field).
  2. ``descriptor.probe_fn`` — falls back to the 9b dry-call. Its
     ``ProbeResult.output`` is used as the tool response, so existing
     9b-only manifests still run under 9a (with a fixed canned call).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

from sme.adapters.base import HarnessDescriptor, ProbeResult


# --- Trace types ------------------------------------------------------


@dataclass
class ToolCallRecord:
    """One tool invocation the model attempted during its turn."""

    name: str
    arguments: dict
    succeeded: bool
    response: str = ""
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class HandshakeTrace:
    """The observable result of one model turn with tools wired in.

    ``final_text`` is the model's last reply — the Cat 1 matcher scores
    against this, never against ``tool_calls_succeeded[*].response``.
    """

    question: str
    final_text: str
    tool_calls_attempted: list[ToolCallRecord] = field(default_factory=list)
    tool_calls_succeeded: list[ToolCallRecord] = field(default_factory=list)
    model: str = ""
    harness: str = ""
    error: Optional[str] = None

    @property
    def invoked(self) -> bool:
        """Did the model reach for the memory tool at all? (9a)"""
        return bool(self.tool_calls_attempted)

    @property
    def call_through(self) -> bool:
        """Did at least one invocation return a valid response? (9b-in-9a)"""
        return bool(self.tool_calls_succeeded)


# --- Tool resolution --------------------------------------------------


def resolve_executor(descriptor: HarnessDescriptor) -> Callable[[dict], ToolCallRecord]:
    """Return a callable that executes ``descriptor`` with model args.

    Honors the ``properties["execute"]`` convention, falling back to the
    9b ``probe_fn``. Always returns a ``ToolCallRecord`` so the runner
    never has to branch on which path fired.
    """
    execute = descriptor.properties.get("execute")

    def _run(arguments: dict) -> ToolCallRecord:
        start = time.perf_counter()
        try:
            if callable(execute):
                response = execute(arguments)
                latency = (time.perf_counter() - start) * 1000
                return ToolCallRecord(
                    name=descriptor.name,
                    arguments=arguments,
                    succeeded=True,
                    response=str(response),
                    latency_ms=latency,
                )
            # Fallback: 9b dry-call. probe_fn takes no args.
            result: ProbeResult = descriptor.probe_fn()
            latency = (time.perf_counter() - start) * 1000
            return ToolCallRecord(
                name=descriptor.name,
                arguments=arguments,
                succeeded=bool(result.success),
                response=result.output or "",
                latency_ms=result.latency_ms or latency,
                error=result.error,
            )
        except Exception as exc:  # noqa: BLE001 — tool code is user-owned
            latency = (time.perf_counter() - start) * 1000
            return ToolCallRecord(
                name=descriptor.name,
                arguments=arguments,
                succeeded=False,
                latency_ms=latency,
                error=f"{type(exc).__name__}: {exc}",
            )

    return _run


# --- Runner ABC -------------------------------------------------------


class ModelRunner(ABC):
    """Send one question to a model with the manifest's tools wired in.

    Implementations own the provider protocol (Anthropic tool-use,
    Ollama, etc.). They MUST run the tool-use loop to completion (the
    model may invoke, read the response, then answer) and return a
    single ``HandshakeTrace`` for the whole turn.
    """

    name: str = "runner"

    @abstractmethod
    def run(
        self, question: str, manifest: list[HarnessDescriptor]
    ) -> HandshakeTrace: ...


# --- MockRunner (no API, deterministic floor) -------------------------


class MockRunner(ModelRunner):
    """Deterministic stand-in for a real model — the Cat 9a floor.

    No network, no keys, no cost. It simulates an agent's *invocation
    policy* so the scorer, the hop-depth cut, and the report can be
    exercised end-to-end in CI exactly the way 9b is.

    Policies (``mode``):
      - ``"always"``  — invoke on every question, then echo the tool
        response as the reply. Simulates a perfectly cooperative agent:
        in-harness recall == offline recall, integration gap == 0.
      - ``"never"``   — never invoke; reply is ``answer_without_tool``.
        Simulates an agent that answers from parametric memory: the
        worst-case gap (== offline recall).
      - ``"hop_threshold"`` — invoke only when a question's ``min_hops``
        is ``<= max_hops``. Simulates the headline failure mode: the
        agent reaches for memory on shallow questions and gives up on
        deep multi-hop ones, producing a degrading invocation curve by
        hop depth.

    ``min_hops`` for the current question is read from ``hop_of`` (a
    callable the scorer wires to the question record) so the mock stays
    decoupled from the question schema.
    """

    def __init__(
        self,
        mode: str = "always",
        *,
        max_hops: int = 2,
        answer_without_tool: str = "",
        hop_of: Optional[Callable[[str], int]] = None,
        name: str = "mock",
    ) -> None:
        if mode not in {"always", "never", "hop_threshold"}:
            raise ValueError(f"unknown MockRunner mode: {mode!r}")
        self.mode = mode
        self.max_hops = max_hops
        self.answer_without_tool = answer_without_tool
        self.hop_of = hop_of
        self.name = name

    def _should_invoke(self, question: str) -> bool:
        if self.mode == "always":
            return True
        if self.mode == "never":
            return False
        # hop_threshold
        hops = self.hop_of(question) if self.hop_of else 1
        return hops <= self.max_hops

    def run(
        self, question: str, manifest: list[HarnessDescriptor]
    ) -> HandshakeTrace:
        trace = HandshakeTrace(
            question=question, final_text="", model=self.name, harness="mock"
        )

        if not manifest or not self._should_invoke(question):
            trace.final_text = self.answer_without_tool
            return trace

        # Cooperative mock: invoke the first declared surface, read its
        # response, and use it as the reply (so result-use + recall track
        # the underlying retrieval, not the mock's own text).
        descriptor = manifest[0]
        record = resolve_executor(descriptor)({"query": question})
        trace.tool_calls_attempted.append(record)
        if record.succeeded:
            trace.tool_calls_succeeded.append(record)
            trace.final_text = record.response
        else:
            trace.final_text = self.answer_without_tool
            trace.error = record.error
        return trace


# --- AnthropicRunner (real model, tool-use loop) ----------------------


def _safe_tool_name(name: str) -> str:
    """Coerce a descriptor name to Anthropic's ^[a-zA-Z0-9_-]{1,64}$."""
    safe = "".join(c if (c.isalnum() or c in "_-") else "_" for c in name)
    return (safe or "memory_tool")[:64]


def _default_tool_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "the search query"}
        },
        "required": ["query"],
    }


def manifest_to_tools(
    manifest: list[HarnessDescriptor],
) -> tuple[list[dict], dict[str, HarnessDescriptor]]:
    """Build Anthropic tool definitions + a (tool_name -> descriptor) map."""
    tools: list[dict] = []
    name_map: dict[str, HarnessDescriptor] = {}
    for d in manifest:
        tool_name = _safe_tool_name(d.name)
        name_map[tool_name] = d
        tools.append(
            {
                "name": tool_name,
                "description": d.description
                or f"Query the {d.name} memory system for relevant context.",
                "input_schema": d.properties.get("input_schema")
                or _default_tool_schema(),
            }
        )
    return tools, name_map


def _block_attr(block, attr, default=None):
    """Read an attribute from an SDK block OR a plain dict (fakes/tests)."""
    if isinstance(block, dict):
        return block.get(attr, default)
    return getattr(block, attr, default)


def _block_to_dict(block) -> dict:
    """Normalize a response content block to the dict form messages expect."""
    btype = _block_attr(block, "type")
    if btype == "text":
        return {"type": "text", "text": _block_attr(block, "text", "")}
    if btype == "tool_use":
        return {
            "type": "tool_use",
            "id": _block_attr(block, "id", ""),
            "name": _block_attr(block, "name", ""),
            "input": _block_attr(block, "input", {}) or {},
        }
    return {"type": btype or "text", "text": ""}


# Default model id. Smaller readers under-invoke more strongly, so 9a is
# often most interesting at Haiku; Sonnet 4.6 is the safe default.
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicRunner(ModelRunner):
    """Real-model runner: wires the manifest as Anthropic tools and runs
    the tool-use loop to completion, returning a single HandshakeTrace.

    Invocation policy (``invocation_mode``):
      - ``"auto"``   — ``tool_choice`` is left to the model. This is what
        9a actually measures: does the model *choose* to reach for
        memory? (Forcing a call would peg invocation at 1.0 and measure
        nothing.)
      - ``"forced"`` — ``tool_choice={"type": "any"}`` on the first turn
        forces one call, then drops to auto so the model can finish.
        Isolates 9b/9c (call-through + result-use) from the model's
        decision to invoke — the "forced" arm of the vanilla/forced
        comparison in the spec appendix.

    Cost discipline: the API key is read from the keyring via
    ``load_api_key`` (never echoed). Token usage accumulates on
    ``self.usage`` and call count on ``self.calls`` so an experiment
    driver can enforce a ``cost_budget_usd`` and ``--dry-run`` above this
    layer. The test suite injects a fake ``client`` and never spends.
    """

    def __init__(
        self,
        *,
        model: str = ANTHROPIC_DEFAULT_MODEL,
        invocation_mode: str = "auto",
        max_tokens: int = 1024,
        max_turns: int = 6,
        system: Optional[str] = None,
        client=None,
    ) -> None:
        if invocation_mode not in {"auto", "forced"}:
            raise ValueError(f"unknown invocation_mode: {invocation_mode!r}")
        self.model = model
        self.invocation_mode = invocation_mode
        self.max_tokens = max_tokens
        self.max_turns = max_turns
        self.name = f"anthropic:{model}"
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.calls = 0
        self.system = system or (
            "Answer the user's question. A memory-search tool is available; "
            "use it when the question needs information you don't already "
            "know, and ground your answer in what it returns. If you don't "
            "need it, just answer."
        )
        if client is not None:
            self._client = client
        else:
            # Lazy: import + keyring lookup only when a real run happens.
            from sme.eval.llm_clients import load_api_key

            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - runtime install
                raise SystemExit(
                    "anthropic package not installed; run `pip install anthropic`."
                ) from exc
            api_key = load_api_key("anthropic")
            if not api_key:
                raise SystemExit(
                    "no Anthropic API key in keyring (service=anthropic)."
                )
            self._client = anthropic.Anthropic(api_key=api_key)

    def run(
        self, question: str, manifest: list[HarnessDescriptor]
    ) -> HandshakeTrace:
        trace = HandshakeTrace(
            question=question, final_text="", model=self.model, harness="anthropic"
        )
        if not manifest:
            trace.error = "empty manifest"
            return trace

        tools, name_map = manifest_to_tools(manifest)
        messages: list[dict] = [{"role": "user", "content": question}]

        try:
            for turn in range(self.max_turns):
                kwargs = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": self.system,
                    "tools": tools,
                    "messages": messages,
                }
                if self.invocation_mode == "forced" and turn == 0:
                    kwargs["tool_choice"] = {"type": "any"}

                resp = self._client.messages.create(**kwargs)
                self.calls += 1
                usage = _block_attr(resp, "usage")
                if usage is not None:
                    self.usage["input_tokens"] += _block_attr(usage, "input_tokens", 0) or 0
                    self.usage["output_tokens"] += _block_attr(usage, "output_tokens", 0) or 0

                content = list(_block_attr(resp, "content", []) or [])
                tool_uses = [b for b in content if _block_attr(b, "type") == "tool_use"]
                text_parts = [
                    _block_attr(b, "text", "")
                    for b in content
                    if _block_attr(b, "type") == "text"
                ]
                if text_parts:
                    trace.final_text = "\n".join(t for t in text_parts if t)

                if not tool_uses:
                    break  # the model answered — done

                # Record the assistant turn, execute tools, feed results back.
                messages.append(
                    {"role": "assistant", "content": [_block_to_dict(b) for b in content]}
                )
                tool_results = []
                for tu in tool_uses:
                    descriptor = name_map.get(_block_attr(tu, "name", ""))
                    args = _block_attr(tu, "input", {}) or {}
                    if descriptor is None:
                        record = ToolCallRecord(
                            name=_block_attr(tu, "name", "?"),
                            arguments=args,
                            succeeded=False,
                            error="model called an unknown tool",
                        )
                    else:
                        record = resolve_executor(descriptor)(args)
                    trace.tool_calls_attempted.append(record)
                    if record.succeeded:
                        trace.tool_calls_succeeded.append(record)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": _block_attr(tu, "id", ""),
                            "content": record.response or record.error or "",
                            "is_error": not record.succeeded,
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
        except Exception as exc:  # noqa: BLE001 — surface API errors as trace state
            trace.error = f"{type(exc).__name__}: {exc}"

        return trace
