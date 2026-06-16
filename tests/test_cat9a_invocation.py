"""Cat 9a (invocation rate — The Handshake) — no-API floor tests.

Mirrors the discipline of the 9b tests: everything here runs against a
deterministic MockRunner, no model API, no cost. Proves the scorer, the
hop-depth cut, the integration-gap headline, and the 9d negative-control
path all behave before any real runner is wired in.
"""

from __future__ import annotations

from sme.adapters.base import (
    Edge,
    Entity,
    HarnessDescriptor,
    ProbeResult,
    QueryResult,
    SMEAdapter,
)
from sme.categories.harness_integration import (
    Cat9aResult,
    format_cat9a_report,
    run_cat9a,
    substring_recall,
)
from sme.harness.runner import HandshakeTrace, MockRunner

# A tiny "knowledge base": question text -> retrievable answer text.
_KB = {
    "q_hop1": "The FDA opened the DCM investigation in July 2018.",
    "q_hop2": "Hill's announced the vitamin D recall on January 31.",
    "q_hop3": "Schenkel's 1947 Expression Studies concerned wolves.",
}

_QUESTIONS = [
    {"text": "q_hop1", "expected_sources": ["FDA", "July 2018", "DCM"], "min_hops": 1},
    {"text": "q_hop2", "expected_sources": ["Hill's", "January 31"], "min_hops": 2},
    {"text": "q_hop3", "expected_sources": ["Schenkel", "wolves"], "min_hops": 3},
]


class _FakeAdapter(SMEAdapter):
    """Minimal adapter: query() retrieves from _KB; one executable surface."""

    def __init__(self, *, with_manifest: bool = True) -> None:
        self._with_manifest = with_manifest

    def ingest_corpus(self, corpus):  # pragma: no cover - unused
        return {"entities_created": 0, "edges_created": 0, "errors": [], "warnings": []}

    def query(self, question: str) -> QueryResult:
        return QueryResult(answer="", context_string=_KB.get(question, ""))

    def get_graph_snapshot(self) -> tuple[list[Entity], list[Edge]]:
        return [], []

    def get_harness_manifest(self) -> list[HarnessDescriptor]:
        if not self._with_manifest:
            return []

        def _execute(args: dict) -> str:
            return _KB.get(args.get("query", ""), "")

        return [
            HarnessDescriptor(
                name="memory_search",
                kind="tool_call",
                probe_fn=lambda: ProbeResult(success=True, output="ok"),
                properties={"execute": _execute, "input_schema": {"type": "object"}},
            )
        ]

    def close(self) -> None:  # pragma: no cover
        pass


# --- substring matcher ------------------------------------------------


def test_substring_recall_fraction():
    assert substring_recall("the FDA and DCM", ["FDA", "DCM"]) == 1.0
    assert substring_recall("the FDA only", ["FDA", "DCM"]) == 0.5
    assert substring_recall("", ["FDA"]) == 0.0
    assert substring_recall("anything", []) == 0.0


# --- always-invoke: gap closes ----------------------------------------


def test_always_invoke_closes_the_gap():
    res = run_cat9a(_FakeAdapter(), MockRunner("always"), _QUESTIONS)
    assert isinstance(res, Cat9aResult)
    assert res.invocation_rate == 1.0
    # Mock echoes the tool response (== offline context), so in-harness
    # recall matches offline recall: integration gap is zero.
    assert res.offline_recall == 1.0
    assert res.in_harness_recall == 1.0
    assert res.integration_gap == 0.0
    assert res.band == "healthy"
    assert res.result_use_rate == 1.0


# --- never-invoke: gap == offline capability --------------------------


def test_never_invoke_opens_full_gap():
    res = run_cat9a(_FakeAdapter(), MockRunner("never"), _QUESTIONS)
    assert res.invocation_rate == 0.0
    assert res.offline_recall == 1.0
    assert res.in_harness_recall == 0.0
    assert res.integration_gap == 1.0  # the system can answer; the agent never asks
    assert res.band == "concerning"
    assert res.result_use_rate == 0.0


# --- hop_threshold: the headline failure mode -------------------------


def test_hop_threshold_degrades_with_depth():
    # Agent reaches for memory at hop <= 2, gives up at hop 3.
    res = run_cat9a(
        _FakeAdapter(),
        MockRunner("hop_threshold", max_hops=2, hop_of=None),
        _QUESTIONS,
    )
    assert res.per_hop[1].invocation_rate == 1.0
    assert res.per_hop[2].invocation_rate == 1.0
    assert res.per_hop[3].invocation_rate == 0.0
    # Gap is zero where it invokes, full where it gives up.
    assert res.per_hop[1].integration_gap == 0.0
    assert res.per_hop[3].integration_gap == 1.0
    # Aggregate invocation rate is 2/3.
    assert abs(res.invocation_rate - (2 / 3)) < 1e-9


# --- 9d negative control ----------------------------------------------


def test_negative_control_unnecessary_invocation():
    negatives = [{"text": "q_unknown", "expected_sources": [], "min_hops": 1}]
    always = run_cat9a(
        _FakeAdapter(), MockRunner("always"), _QUESTIONS, negative_questions=negatives
    )
    assert always.unnecessary_invocation_rate == 1.0  # invokes even with no answer

    never = run_cat9a(
        _FakeAdapter(), MockRunner("never"), _QUESTIONS, negative_questions=negatives
    )
    assert never.unnecessary_invocation_rate == 0.0


# --- empty manifest ---------------------------------------------------


def test_empty_manifest_is_not_applicable():
    res = run_cat9a(_FakeAdapter(with_manifest=False), MockRunner("always"), _QUESTIONS)
    assert res.empty_manifest is True
    assert res.band == "n/a"
    assert "does not apply" in format_cat9a_report(res)


# --- probe_fn fallback (9b-only manifest still runs under 9a) ----------


def test_probe_fn_fallback_when_no_execute():
    class _ProbeOnlyAdapter(_FakeAdapter):
        def get_harness_manifest(self):
            return [
                HarnessDescriptor(
                    name="legacy",
                    kind="tool_call",
                    probe_fn=lambda: ProbeResult(success=True, output="FDA DCM July 2018"),
                    properties={},  # no execute -> falls back to probe_fn
                )
            ]

    res = run_cat9a(_ProbeOnlyAdapter(), MockRunner("always"), _QUESTIONS[:1])
    assert res.per_hop[1].call_through == 1
    assert res.per_hop[1].invoked == 1


# --- report smoke -----------------------------------------------------


def test_report_renders_hop_table():
    res = run_cat9a(
        _FakeAdapter(), MockRunner("hop_threshold", max_hops=2), _QUESTIONS
    )
    report = format_cat9a_report(res, source_label="mock")
    assert "By hop depth" in report
    assert "INTEGRATION_GAP" in report
    assert "agent gives up" in report  # hop-3 bucket is flagged


def test_handshake_trace_invoked_flags():
    trace = HandshakeTrace(question="q", final_text="x")
    assert trace.invoked is False
    assert trace.call_through is False


def test_synthesized_executor_from_query_when_no_execute():
    """A manifest with no execute still drives real per-question retrieval
    via the adapter's query() — the case for every shipped adapter."""

    class _NoExecuteAdapter(_FakeAdapter):
        def get_harness_manifest(self):
            return [
                HarnessDescriptor(
                    name="memory_search",
                    kind="mcp_resource",
                    probe_fn=lambda: ProbeResult(success=True, output="probe"),
                    properties={"tool_name": "memory_search"},  # no execute
                )
            ]

    res = run_cat9a(_NoExecuteAdapter(), MockRunner("always"), _QUESTIONS)
    # query() retrieved the answer per question, so the gap still closes —
    # proving the tool call ran a real retrieval, not the canned probe.
    assert res.in_harness_recall == 1.0
    assert res.integration_gap == 0.0
