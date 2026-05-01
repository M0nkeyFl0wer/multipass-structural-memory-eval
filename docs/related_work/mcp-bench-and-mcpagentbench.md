# MCP-Bench and MCPAgentBench

Cross-validation reference for SME's Cat 9 (Handshake — harness integration).
This file inventories the two industry benchmarks closest to Cat 9, separates
their primary-source claims from third-party summaries, and maps each
benchmark's metrics onto the SME 9-sub-tests.

## VERIFICATION UPDATE 2026-05-01 — primary-source PDF fetched

The arXiv PDF for 2508.20453 (MCP-Bench, Accenture) was fetched
directly and grepped. Confirmed primary-source findings:

- **"Invocation Accuracy"** — **zero hits** in the paper. This metric
  name was a third-party-summary artifact; do not cite it as
  MCP-Bench's terminology.
- MCP-Bench's actual rule-based metrics, verbatim from §4 of the PDF:
  - **Tool Validity** (rule-based)
  - **Schema Compliance Rate** (rule-based, line 480 of pdftotext
    extract): "measures whether each tool invocation provides
    correctly..."
  - **Execution Success Rate** (rule-based, line 491 verbatim): "This
    metric quantifies the proportion of tool invocations that
    successfully [return results without runtime failure]."
  - **Dependency Order** (rule-based)
- LLM-judge axes (verbatim): **Task Completion Quality**, **Tool
  Usage Quality**, **Planning Effectiveness**.
- Cat 9b → **Execution Success Rate** is the correct verbatim
  citation. The mapping holds.
- Cat 9a → **no MCP-Bench metric isolates the binary
  invocation-decision signal from argument-correctness.** SME 9a is
  genuinely distinct, not a renaming of an existing metric. This is
  a strengthening of SME's positioning, not a weakening.

Corrections needed:
- Issue #3 reply on the SME repo (already public): retract the
  "Invocation Accuracy" framing-note at the bottom of that comment
  and replace with Execution Success Rate / Cat 9a-is-distinct
  framing.
- Issue #9 body: edit the Cat 9a row in the equivalence table.

**Note on namespace collision.** There are at least three benchmarks with
near-identical names. They are different work, with different methodologies:

- **MCP-Bench** — arXiv 2508.20453, Accenture, Aug 2025
- **MCP-AgentBench** (with hyphen) — arXiv 2509.09734, Sept 2025
- **MCPAgentBench** (no hyphen) — arXiv 2512.24565, Dec 2025

The user's prompt cited the third (2512.24565). All three are covered below
because they're easily confused in citation; the hyphenated 2509.09734 is
the one whose abstract matches the "locally-maintained MCP servers,
Autogen-based sandbox" phrasing in the user's prompt — not 2512.24565.

**Source-fidelity caveat.** Direct PDF/HTML body fetch was blocked by
the harness this session, so verbatim-quote claims here rely on
third-party summaries (MarkTechPost, Liner.com Quick Review, Medium
@huguosuo) plus the arXiv abstract pages, openreview forum, and the
GitHub README. Paraphrase-only material is marked
[third-party-summary]. **Re-grep the PDFs before quoting any of these
metric definitions in load-bearing prose.**

Read date: 2026-05-01.

---

## Part 1 — MCP-Bench

### Provenance

- arXiv: <https://arxiv.org/abs/2508.20453> (v1: Aug 2025)
- Title: *MCP-Bench: Benchmarking Tool-Using LLM Agents with Complex
  Real-World Tasks via MCP Servers*
- Authors: Wang et al. (Accenture Research). First-author surname Wang
  per ADS record `2025arXiv250820453W`.
- Venue: Submitted to OpenReview (`forum?id=fe8mzHwMxN`) — venue/decision
  not confirmed from the abstract page.
- GitHub: <https://github.com/Accenture/mcp-bench>
- Fetch method: arXiv abstract page + openreview + GitHub README + Liner
  Quick Review + MarkTechPost summary. PDF body not fetched directly.

### What it is

A benchmark in which an LLM agent is connected to **28 live MCP servers
exposing 250 tools** spanning finance, scientific computing, healthcare,
travel, and academic search. Tasks are designed so realistic workflows
require sequential and parallel tool use, sometimes across multiple
servers. **20 LLMs are evaluated** [third-party-summary], including
gpt-4o, o3, gpt-5, gpt-oss-120b, and qwen3-235b-a22b-2507; the full list
of 20 was not visible in fetched material.

Tasks "test agents' ability to retrieve relevant tools from fuzzy
instructions without explicit tool names, plan multi-hop execution
trajectories for complex objectives, ground responses in intermediate
tool outputs, and orchestrate cross-domain workflows"
[third-party-summary, MarkTechPost].

### Evaluation methodology

A two-tier framework [third-party-summary, paraphrase from openreview
forum]:

1. **Rule-based checks** for tool validity, schema compliance, runtime
   success, and dependency order.
2. **Rubric-driven LLM-as-a-Judge** scoring of task completion, tool
   usage, and planning effectiveness.

Judge model: o4-mini by default. Prompt-shuffling and score averaging
are used to mitigate rubric-order sensitivity in the LLM judge.

### Metrics defined

**Rule-based tier (this is the load-bearing tier for SME Cat 9 mapping):**

- **Tool Validity** — whether each invoked tool name resolves to an
  available registered tool. [third-party-summary phrasing; "many models
  surpassing 98%" reported.]
- **Schema Compliance Rate** — "whether each tool invocation provides
  correctly structured parameters that match the tool's expected input
  schema, returning True if the tool is available and the parameters
  match the expected input schema of the tool" [third-party-summary
  paraphrase].
- **Execution Success Rate** — "the proportion of tool invocations that
  successfully return results without runtime failure, where the tool
  call is executed without runtime errors and produces a valid result"
  [third-party-summary paraphrase].
- **Dependency Order** — whether inter-tool dependencies are respected.

**Rubric tier (1–10 sub-dimensions, LLM-judge scored):**

- *Tool Usage Quality* — tool appropriateness; parameter accuracy.
- *Planning Effectiveness* — dependency awareness; parallelism &
  efficiency.
- *Task Completion* — quality of final solution.

**Verification gap.** I could not find a verbatim string "Invocation
Accuracy" anywhere in MCP-Bench's metric set. The closest concept is
**Tool Validity** (correct tool name resolution) plus **Schema
Compliance Rate** (correct argument structure). Earlier search summaries
that named "Invocation Accuracy" as MCP-Bench's metric appear to be
**conflating MCP-Bench with MCPAgentBench's TFS or with a generic tool-use
literature term**. Before quoting "Invocation Accuracy" as MCP-Bench
terminology in any external doc, grep the PDF.

---

## Part 2 — MCPAgentBench (and the MCP-AgentBench cousin)

### Provenance — MCPAgentBench (2512.24565)

- arXiv: <https://arxiv.org/abs/2512.24565> (v1: Dec 2025)
- Title: *MCPAgentBench: A Real-world Task Benchmark for Evaluating LLM
  Agent MCP Tool Use*
- Authors: not visible in fetched abstract metadata.
- GitHub: not surfaced in search.
- Read date: 2026-05-01.

### Provenance — MCP-AgentBench (2509.09734)

- arXiv: <https://arxiv.org/abs/2509.09734> (Sept 2025)
- Title: *MCP-AgentBench: Evaluating Real-World Language Agent
  Performance with MCP-Mediated Tools*
- This is the one that matches the "locally-maintained MCP servers,
  AutoGen-based sandbox" phrasing in the SME prompt — but watch out, the
  *AutoGen sandbox* description is also used by 2512.24565. The two
  papers are independent.

### What 2512.24565 is

[third-party-summary unless noted] An evaluation benchmark whose stated
gap-in-prior-work is that "current benchmarks exhibit insufficient
difficulty awareness, performing only simple task categorization and
lacking granular observation of the invocation complexity level."

Construction: the authors collected 841 tasks and >20,000 MCP tools
from MCP Marketplace, GitHub, HuggingFace; manual labeling/matching
distilled this to **180 high-quality task instances**. An AutoGen-based
sandbox loads MCP tools dynamically; for each task, the framework
samples a candidate list of K tools (K=20 or 30) consisting of correct
tools plus distractor tools.

Tasks are classified by **invocation complexity**:

- *Single-tool invocation* — "tests foundational ability to select the
  correct tool"
- *Dual-tool parallel invocation* — "assesses task decomposition and
  parallel planning capabilities"
- *Dual-tool serial invocation* — "assesses capabilities for multi-step
  reasoning, planning, and state maintenance"

(The set may extend to multi-tool; only the dual-tool decomposition is
explicitly described in fetched summaries.)

### Metrics defined — 2512.24565

[third-party-summary, paraphrase]

- **Task Finish Score (TFS)** — a task is "Finished" *iff* the set of
  tool invocations generated by the Agent is identical to the set of
  invocations in the golden solution, requiring an exact match of all
  *tool names* and *parameters*.
- **Task Efficiency Finish Score (TEFS)** — TFS variant that also
  accounts for execution efficiency. Formula not visible in fetched
  material.
- **Time Efficiency** — wall-clock metric. Definition not visible.
- **Token Efficiency** — token-budget metric. Definition not visible.

Reported finding: "average TFS for Dual Parallel Tool Tasks > Dual
Serial Tool Tasks" — suggests parallel decomposition is easier than
serial state-tracking under their scoring.

### What 2509.09734 (MCP-AgentBench) is

A separate benchmark: 33 operational MCP servers, 188 distinct tools,
600 systematically designed queries across 6 categories of varying
interaction complexity. It introduces **MCP-Eval**, an outcome-oriented
LLM-as-judge methodology that "prioritizes real-world task success"
rather than rigid execution-path matching. MCP-Eval reports 91.7%
agreement with human evaluators. Notable finding: Qwen3-235B and Kimi
K2 outperformed GPT-4o on its tasks.

This is a *softer* scorer than 2512.24565's exact-match TFS — it is
closer in spirit to MCP-Bench's LLM-as-judge rubric tier. SME's Cat 9
should be aware that 2509.09734 deliberately rejects exact-trajectory
matching as a metric.

---

## Mapping to SME Cat 9

| SME sub-test | MCP-Bench (2508.20453) | MCPAgentBench (2512.24565) | MCP-AgentBench (2509.09734) | SME-distinctive? |
|---|---|---|---|---|
| **9a** invocation rate `P(tool_calls ≥ 1)` | Not directly. **Tool Validity** is the closest, but it is conditional on a tool call already being attempted. | Not directly. TFS *requires* the right tool calls — a model that emits zero calls scores 0, but TFS doesn't isolate the "did the model decide to invoke" signal. | Not directly; MCP-Eval is outcome-oriented. | **Yes, partially.** No surveyed benchmark explicitly reports the binary "did the model emit a tool call at all" rate decoupled from correctness. SME 9a's signal is unique in isolating the *invocation decision* from the *invocation argument quality*. |
| **9b** call-through success | **Execution Success Rate** is the direct equivalent: "proportion of tool invocations that successfully return results without runtime failure." | Subsumed inside TFS (a failed call cannot match the golden solution); not isolated. | Subsumed in MCP-Eval task-success score. | MCP-Bench's Execution Success Rate is **the closest 1:1 industry analogue** to Cat 9b. SME should cite it explicitly when describing 9b. |
| **9c** result usage (does the model actually condition on the tool's return?) | Partially: Rubric tier's *task completion* + *grounding-in-intermediate-outputs* phrasing in task design. Not isolated as a metric. | Not isolated. | Implicit in MCP-Eval task-success. | **SME-distinctive** if 9c isolates "tool returned, but answer ignored it." |
| **9e** per-model sensitivity | Reports per-model scores across 20 LLMs — yes, this dimension is covered. | Reports per-model TFS; covered. | Covered (Qwen3 vs GPT-4o etc.). | Not distinctive; all three benchmarks cover this. |
| **9f** per-harness portability | **No.** MCP-Bench fixes its harness. | **No.** AutoGen sandbox is fixed. | **No.** | **SME-distinctive.** Cat 9f's per-harness decomposition (Claude Code vs Cursor vs ChatGPT-via-MCP) is not present in any of these benchmarks. |
| **9g** event-driven invocation | **No.** Tasks are user-prompted. | No. | No. | **SME-distinctive.** Event-driven / proactive invocation is not in scope for any of the three. |

**Strongest equivalences to anchor in the SME paper:**

- For 9b call-through success → cite **MCP-Bench's Execution Success
  Rate** (paraphrase per Liner Quick Review of arXiv 2508.20453: "the
  proportion of tool invocations that successfully return results
  without runtime failure"). This is the cleanest cross-validation
  hook.
- For 9a invocation rate → there is **no clean industry equivalent**.
  MCP-Bench's Tool Validity is conditional on a call having been made;
  MCPAgentBench's TFS conflates invocation-decision with
  argument-correctness. SME should frame 9a as a contribution, not a
  replication.

---

## What SME could directly incorporate

Three concrete integration moves, ordered by cost:

1. **Adopt MCP-Bench's *Execution Success Rate* terminology in Cat 9b
   prose.** Zero engineering cost. Note that 9b should report both the
   raw rate and the per-(adapter, model, harness) breakdown — the
   breakdown is the SME-distinctive contribution.

2. **Pull MCP-Bench's 28-server task suite as an external Cat 9
   stress-corpus.** Accenture/mcp-bench is open source. SME's Cat 9
   scorer would need an MCP-server-launching harness (it does not have
   one yet — the existing 9b runs against SME's own registered memory
   tool). Cost estimate: 1–2 days for the harness scaffolding plus
   whatever credits to run 20 servers. Value: SME becomes directly
   comparable to MCP-Bench's published numbers.

3. **Register SME's memory adapter as a benchmark target inside
   MCPAgentBench (2512.24565)**. MCPAgentBench's AutoGen sandbox
   dynamically loads MCP tools, so registering SME's memory tool as one
   of the candidate tools is mechanically straightforward. The challenge
   is task design — MCPAgentBench's 180 instances aren't memory-tasks,
   so the cross-validation is "does the memory tool show up as a
   distractor that gets correctly ignored" rather than "is the memory
   tool correctly invoked." This is closer to a *negative* 9a test
   (false-positive invocation rate). Probably not worth doing as a Cat
   9 hook; might be worth doing as a Cat 11 (anti-memory) hook.

---

## What SME measures that these benchmarks don't

1. **Per-(adapter, model, harness, corpus) decomposition.** All three
   benchmarks fix the harness and report per-model averages only. SME
   reports the cross-product. [unverified vs. SME spec_v8.md.]
2. **Memory-specific call-through.** Cat 9 measures invocation of the
   *registered memory tool* — the model has to *want* to remember,
   unlike a stock-price tool called when explicitly asked.
3. **Event-driven (9g) and per-harness (9f).** Noted in the table.
4. **9a in isolation** — `P(any tool call | task warrants it)`,
   independent of correctness. The binary "handshake fired" signal is
   absent from the surveyed literature.

---

## Open questions

1. **What models exactly does MCP-Bench evaluate?** Search summaries say
   "20 advanced LLMs" but only ~5 are named. Need direct PDF read.
2. **Does MCPAgentBench (2512.24565) report TFS separately for the
   "model emitted no tool calls" failure mode?** This determines whether
   it can be retroactively used as a 9a proxy. Search material doesn't
   answer.
3. **What is MCP-AgentBench (2509.09734)'s per-category breakdown of its
   600 queries across 6 categories?** Could one of those categories map
   to memory-tool invocation?
4. **Is "Invocation Accuracy" actually in either paper, or is it a
   third-party-summary hallucination?** I never saw the verbatim string
   in fetched material. The user's prompt asserted it. **Grep the PDFs
   before citing this term.** This is a textbook
   verification-discipline-rule-1 case — a number/term repeated across
   conversation that may collapse on first grep.
5. **Is there a Cat 4 (Threshold) equivalent in any of these
   benchmarks?** None surfaced; worth a separate sweep.

---

## Citations

- MCP-Bench paper: <https://arxiv.org/abs/2508.20453>
- MCP-Bench openreview: <https://openreview.net/forum?id=fe8mzHwMxN>
- MCP-Bench code: <https://github.com/Accenture/mcp-bench>
- MCPAgentBench (2512.24565): <https://arxiv.org/abs/2512.24565>
- MCP-AgentBench (2509.09734): <https://arxiv.org/abs/2509.09734>
- MarkTechPost summary of MCP-Bench:
  <https://www.marktechpost.com/2025/08/29/accenture-research-introduce-mcp-bench-a-large-scale-benchmark-that-evaluates-llm-agents-in-complex-real-world-tasks-via-mcp-servers/>
- Liner Quick Review (MCP-Bench):
  <https://liner.com/review/mcpbench-benchmarking-toolusing-llm-agents-with-complex-realworld-tasks-via>

### Adjacent benchmarks for follow-up

- MCP-Universe (arXiv 2508.14704); LiveMCPBench (2508.01780); MCPMark
  (2509.24002); OSWorld-MCP (2510.24563); MCP-Atlas (Scale, non-arXiv);
  AgentBench (THUDM, ICLR'24); TOUCAN (2510.01179).
