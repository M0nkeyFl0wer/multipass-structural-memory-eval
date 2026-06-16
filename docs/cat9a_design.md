# Cat 9a — Invocation Rate (The Handshake), by hop depth

**Status:** MockRunner (no-cost floor) **and** AnthropicRunner (real
tool-use loop) both shipped and tested offline. The one paid step
remaining is an actual Claude run against a corpus.
**Code:** `sme/harness/runner.py` (`MockRunner`, `AnthropicRunner`),
`sme/categories/harness_integration.py` (`run_cat9a` /
`format_cat9a_report` / `Cat9aResult`), CLI `sme-eval cat9 --subtest 9a
[--model anthropic --invocation-mode auto|forced]`, tests
`tests/test_cat9a_invocation.py` + `tests/test_cat9a_anthropic_runner.py`.

**Real against any adapter.** `run_cat9a` synthesizes a tool executor
from the required `adapter.query()` for any surface lacking an explicit
`properties["execute"]`, so a model tool-call drives genuine
per-question retrieval — no per-adapter wiring needed. (No shipped
adapter declares `execute` today; mempalace's manifest carries only
metadata, familiar's returns `[]` because its `ToolCall`/`MCPResource`
types were never created.)

## Why this exists

Every other SME category measures retrieval offline. Cat 2c proved
structured **multi-hop** retrieval earns its keep at depth — *but only
if it is invoked*. 9a is the agentic counterpart: when a real model is
handed the memory tool and a question the system can answer, does the
model actually reach for it, and does the retrieved context land in the
reply?

The headline metric (per spec v8 § Cat 9):

> **integration gap = offline Cat 1 recall − in-harness recall**

and the cut that makes it *our* question — **the gap by `min_hops`**.
The hypothesis worth instrumenting: an agent under-invokes precisely on
the deep-hop questions where Cat 2c showed structure matters most. It
gives up on traversal and answers from parametric memory. The mock's
`hop_threshold` policy reproduces that curve deterministically so the
report and tests have a known shape to assert against:

```
By hop depth (the agentic-multi-hop cut):
  hop   n  invoke%  callthru%  used%    gap
    1   3    1.00     1.00    1.00   +0.00
    2   4    1.00     1.00    1.00   +0.00
    3   5    0.55     0.52    0.40   +0.31  <- agent gives up
    4   3    0.40     0.38    0.25   +0.44
```

## The three pieces (per spec, mapped to contracts)

1. **Harness manifest** — already exists
   (`SMEAdapter.get_harness_manifest() → list[HarnessDescriptor]`). 9b
   only uses `probe_fn`. 9a needs the surface *executable by the model*,
   so it reads two keys the spec says to park in `properties` until the
   base contract grows a field:
   - `properties["execute"]`: `Callable[[dict], str]` — runs the tool
     with the model's arguments, returns the response text.
   - `properties["input_schema"]`: JSON schema handed to the model.

   `resolve_executor()` falls back to `probe_fn` when `execute` is
   absent, so existing 9b-only manifests still run under 9a.

2. **Model runner shim** → `HandshakeTrace` (final reply, tool calls
   attempted, tool calls succeeded). The only genuinely new
   infrastructure. `ModelRunner` ABC; implementations own the provider
   protocol and **must run the tool-use loop to completion**.

3. **Matcher reuse** — `substring_recall()` (the Cat 1 signal) runs
   against `trace.final_text`, never the raw tool response. A result the
   model ignores does not count as retrieval. That asymmetry is the
   whole point of Cat 9.

## Sub-metrics that fall out of the trace

| Metric | Spec | Derivation |
|---|---|---|
| Invocation rate | 9a | `invoked / n_positive`, bucketed by hop |
| Call-through (model-driven) | 9b-in-9a | `tool_calls_succeeded` non-empty |
| Result-use rate | 9c | retrieved content reflected in `final_text` |
| Unnecessary-invocation rate | 9d | invocations over the held-out no-answer set |
| **Integration gap** | headline | `offline_recall − in_harness_recall` |

9c is a proxy for now (substring of expected content in the reply); the
spec allows upgrading it to an LLM judge at Cat 7's cost profile.

## Runners — build order

1. **MockRunner** *(shipped)* — deterministic, no API. Policies:
   `always` (gap → 0), `never` (gap → offline recall), `hop_threshold`
   (invoke at shallow hops, give up deep — the headline failure mode).
   This is the CI floor, exactly as 9b shipped against a mock invoker.
2. **AnthropicRunner** *(shipped)* — native Claude tool-use loop
   (invoke → execute → feed result back → answer). `auto` mode measures
   whether the model *chooses* to invoke; `forced` mode (`tool_choice:
   any` on turn 0) isolates call-through/result-use. Key from the
   keyring via `load_api_key` (never echoed); `self.usage`/`self.calls`
   accumulate for a `cost_budget_usd` gate at the experiment layer. The
   SDK client is dependency-injected, so the full loop is tested with a
   fake — the test suite never spends.
3. **OllamaRunner** *(next)* — local gemma/qwen, free; matches the existing
   gemma4/qwen3.5 readings referenced in the spec appendix (issue #3).
   Smaller readers should show the under-invocation signal more
   strongly.

## Decisions taken

- **Hop-depth cut is the headline**, not a secondary breakdown — it is
  the literal "does the agent use multi-hop retrieval when it should"
  question.
- **Anthropic is the first real runner** after the mock floor.

## Open / deferred

- `HandshakeTrace` may grow `hook_activity` for 9g (hook-driven access),
  which needs per-harness shims — out of scope here.
- Question set for real runs: the CKG `T3_path` multi-hop set already
  carries `path_ids` + hop labels; the `good-dog` / standard `2c` sets
  carry `min_hops`. Either works; pick per experiment.
- `ProbeResult` is documented as a stable floor that 9a/9c will extend
  with `reply_text` / `model_invoked` / `context_used`. We kept the
  richer state in `HandshakeTrace` instead of mutating `ProbeResult`, so
  9b's contract is untouched.
