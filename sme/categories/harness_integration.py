"""Category 9: Harness Integration — The Handshake.

Tests whether the memory system is actually reachable through its
declared invocation surfaces (MCP servers, Claude Code hooks, tool
calls, slash commands, custom actions). Every other SME category
measures offline retrieval — this category measures the layer between
retrieval and a running model.

Implemented:

  9a  Invocation rate       — run_cat9a + sme/harness/runner.py. MockRunner
                              (no cost), AnthropicRunner (real Claude), and
                              OllamaRunner (free local gemma/qwen).
  9b  Call-through success  — run_cat9b: for each ``HarnessDescriptor``,
                              invoke ``probe_fn`` once and report whether the
                              call completed. A low 9b means the integration
                              is broken (bad schema, timeout, tool not
                              registered, MCP server unreachable); it says
                              nothing about whether a model would invoke it.
  9c  Result usage          — Cat9aResult.result_use_rate (substring proxy;
                              upgradeable to an LLM judge).
  9d  Negative-control rate — Cat9aResult.unnecessary_invocation_rate over a
                              held-out no-answer set.

Planned (see spec v8 § Category 9):

  9e  Per-model sensitivity — loop runners over models (cheap now).
  9f  Per-harness portability — needs per-harness runners.
  9g  Hook-driven access    — needs per-harness shims (Claude Code,
                               Cursor, LangGraph, etc.).

Caveat: 9a's in-harness recall matches the model's (often terse) final
reply, while offline recall matches the full retrieved context — so the
integration_gap is sensitive to the match threshold and is directional
unless a judge-based matcher is used. See run_cat9a / format_cat9a_report.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from sme.adapters.base import HarnessDescriptor, ProbeResult, SMEAdapter

log = logging.getLogger(__name__)


# --- Bands for the Reading section ------------------------------------

_CALL_THROUGH_HEALTHY = 1.00   # all surfaces callable
_CALL_THROUGH_WARN = 0.80      # 80-99% — partial integration


def _band(value: float, healthy: float, warn: float) -> str:
    if value >= healthy:
        return "healthy"
    if value >= warn:
        return "warn"
    return "concerning"


# --- Result types -----------------------------------------------------


@dataclass
class ProbeReading:
    """One descriptor's probe outcome with SME-side wrapping."""

    descriptor: HarnessDescriptor
    result: ProbeResult


@dataclass
class Cat9bResult:
    """Category 9b — call-through success — scorecard."""

    total_probes: int
    successful_probes: int
    failed_probes: int
    # Probes grouped by HarnessDescriptor.kind for per-surface breakdown.
    by_kind: dict[str, dict[str, int]] = field(default_factory=dict)
    readings: list[ProbeReading] = field(default_factory=list)
    # Present when the adapter declares no manifest — distinct from zero
    # probes succeeding (which is a real failure).
    empty_manifest: bool = False

    @property
    def call_through_rate(self) -> Optional[float]:
        """Fraction of declared surfaces that answered.

        Returns ``None`` when the adapter declares no harness manifest —
        a "not measured" signal distinct from "every probe failed"
        (which would be ``0.0``). Consumers reading the JSON should
        treat ``null`` as "Cat 9b does not apply to this system" and
        ``0.0`` as a measured floor.
        """
        if self.empty_manifest:
            return None
        if self.total_probes == 0:
            return 0.0
        return self.successful_probes / self.total_probes

    @property
    def band(self) -> str:
        if self.empty_manifest:
            return "n/a"
        rate = self.call_through_rate
        if rate is None:
            return "n/a"
        return _band(rate, _CALL_THROUGH_HEALTHY, _CALL_THROUGH_WARN)


# --- Sub-test: 9b call-through success --------------------------------


def run_cat9b(adapter: SMEAdapter, *, timeout_per_probe_s: float = 10.0) -> Cat9bResult:
    """Execute Category 9b against an adapter's declared harness manifest.

    Invokes each ``HarnessDescriptor.probe_fn`` exactly once and tallies
    successes. A probe that raises an exception counts as a failure with
    the exception message captured in ``ProbeResult.error``. A probe
    that exceeds ``timeout_per_probe_s`` is not automatically aborted —
    the probe_fn owns its own timeout semantics — but the elapsed
    wall-clock is recorded in ``ProbeResult.latency_ms``.

    Consumers of this function (the CLI, a CI harness, a test) should
    treat an empty manifest as "the adapter doesn't declare a harness
    surface" — a reporting outcome, not a pass/fail.
    """
    manifest = adapter.get_harness_manifest()

    if not manifest:
        return Cat9bResult(
            total_probes=0,
            successful_probes=0,
            failed_probes=0,
            empty_manifest=True,
        )

    readings: list[ProbeReading] = []
    by_kind: dict[str, dict[str, int]] = {}
    successful = 0
    failed = 0

    for descriptor in manifest:
        start = time.perf_counter()
        try:
            result = descriptor.probe_fn()
            if not isinstance(result, ProbeResult):
                # Tolerate the common mistake of returning a bool.
                result = ProbeResult(
                    success=bool(result),
                    latency_ms=(time.perf_counter() - start) * 1000,
                    error=None if result else "probe_fn returned non-ProbeResult falsy value",
                )
            # Fill latency if the probe forgot to.
            if result.latency_ms == 0.0:
                result.latency_ms = (time.perf_counter() - start) * 1000
        except Exception as exc:  # noqa: BLE001 — intentional; probe_fn is user code
            latency = (time.perf_counter() - start) * 1000
            log.debug("probe %r raised %s", descriptor.name, exc)
            result = ProbeResult(
                success=False,
                latency_ms=latency,
                error=f"{type(exc).__name__}: {exc}",
            )

        readings.append(ProbeReading(descriptor=descriptor, result=result))

        kind_bucket = by_kind.setdefault(descriptor.kind, {"success": 0, "fail": 0})
        if result.success:
            successful += 1
            kind_bucket["success"] += 1
        else:
            failed += 1
            kind_bucket["fail"] += 1

    return Cat9bResult(
        total_probes=len(manifest),
        successful_probes=successful,
        failed_probes=failed,
        by_kind=by_kind,
        readings=readings,
        empty_manifest=False,
    )


# --- Formatting helpers (used by the CLI) -----------------------------


def format_cat9b_report(result: Cat9bResult, *, source_label: str = "") -> str:
    """Return a human-readable scorecard for Category 9b.

    Follows the same banded-reading shape as ``cat4`` / ``cat5`` so the
    CLI output stays consistent. Probe-level detail is included so a
    failing call-through rate is actionable.
    """
    lines: list[str] = []

    header = "Category 9b — Harness Integration (Call-Through Success)"
    if source_label:
        header = f"{header} — {source_label}"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    if result.empty_manifest:
        lines.append(
            "  Adapter declared no harness manifest — pure library usage only. "
            "Cat 9b does not apply."
        )
        lines.append("")
        lines.append(
            "  If this memory system is reachable via MCP, hooks, tool calls, or "
            "slash commands, implement ``get_harness_manifest()`` so SME can probe "
            "each surface."
        )
        return "\n".join(lines) + "\n"

    rate = result.call_through_rate
    rate_pct = (rate * 100) if rate is not None else 0.0
    lines.append(
        f"  Probes: {result.total_probes} total — "
        f"{result.successful_probes} succeeded, "
        f"{result.failed_probes} failed "
        f"({rate_pct:.1f}% call-through, band: {result.band})"
    )
    lines.append("")

    if result.by_kind:
        lines.append("  By surface kind:")
        for kind, counts in sorted(result.by_kind.items()):
            total = counts["success"] + counts["fail"]
            success = counts["success"]
            pct = (success / total * 100) if total else 0.0
            lines.append(f"    {kind:22} {success}/{total} ({pct:.0f}%)")
        lines.append("")

    if result.failed_probes:
        lines.append("  Failed probes:")
        for reading in result.readings:
            if reading.result.success:
                continue
            error = reading.result.error or "(no error captured)"
            lines.append(
                f"    - {reading.descriptor.kind}/{reading.descriptor.name}: {error}"
            )
        lines.append("")

    lines.append("  Reading:")
    if result.band == "healthy":
        lines.append(
            "    All declared surfaces answered. The memory system is live at every "
            "harness point it claims to support."
        )
    elif result.band == "warn":
        lines.append(
            "    Some surfaces are unreachable. Likely integration regressions rather "
            "than retrieval problems — inspect the failed probes above."
        )
    else:
        lines.append(
            "    Most surfaces failed to respond. The memory system is effectively "
            "unavailable to callers using the declared harness contract. Cat 9a "
            "(invocation rate) readings downstream of this will be artificially low."
        )
    lines.append("")

    lines.append(
        "  Note: 9b measures whether a mock-invoker can reach each surface. It does "
        "NOT measure whether a real model would actually invoke the tool (9a), use "
        "the result (9c), or skip when unnecessary (9d). Those sub-tests require a "
        "real model runtime and are tracked separately."
    )
    return "\n".join(lines) + "\n"


# ======================================================================
# Sub-test: 9a invocation rate — The Handshake, by hop depth
# ======================================================================
#
# 9a is the agentic counterpart to the offline multi-hop work (Cat 2c).
# Cat 2c proved structured multi-hop retrieval earns its keep at depth —
# but only IF it is invoked. 9a measures whether a running model
# actually reaches for it, and whether the retrieved context lands in
# the reply. The headline cut is by ``min_hops``: the hypothesis is that
# an agent under-invokes precisely on the deep-hop questions where Cat
# 2c showed structure matters most (it gives up on traversal and answers
# from parametric memory).
#
# The Cat 1 substring matcher runs against the model's FINAL reply text,
# never the raw tool response — a tool result the model ignores does not
# count as retrieval. See sme/harness/runner.py for the model loop.

from sme.harness.runner import HandshakeTrace, ModelRunner  # noqa: E402


# --- Bands for invocation / integration-gap ---------------------------

_INVOKE_HEALTHY = 0.90   # agent reaches for memory on ≥90% of answerable q
_INVOKE_WARN = 0.60      # 60-89% — reaches inconsistently
_GAP_HEALTHY = 0.05      # offline−in-harness recall within 5pp
_GAP_WARN = 0.20         # 5-20pp leak between offline capability and use


def substring_recall(text: str, expected_sources: list[str]) -> float:
    """Fraction of ``expected_sources`` present (case-insensitive) in text.

    The same substring signal Cat 1 uses (see the corpus
    ``questions.yaml`` contract). Returns 0.0 for empty text; raises no
    error for empty expected (returns 0.0 — caller treats as no-oracle).
    """
    if not expected_sources or not text:
        return 0.0
    low = text.lower()
    hits = sum(1 for s in expected_sources if s.lower() in low)
    return hits / len(expected_sources)


def _question_hit(text: str, expected: list[str], threshold: float) -> bool:
    """A question is a 'hit' when substring_recall ≥ threshold (default all)."""
    return substring_recall(text, expected) >= threshold


# --- Result types -----------------------------------------------------


@dataclass
class HopHandshake:
    """9a tallies for one hop-depth bucket."""

    hops: int
    n: int = 0
    invoked: int = 0
    call_through: int = 0
    offline_hits: int = 0
    in_harness_hits: int = 0
    result_used: int = 0

    @property
    def invocation_rate(self) -> float:
        return self.invoked / self.n if self.n else 0.0

    @property
    def offline_recall(self) -> float:
        return self.offline_hits / self.n if self.n else 0.0

    @property
    def in_harness_recall(self) -> float:
        return self.in_harness_hits / self.n if self.n else 0.0

    @property
    def integration_gap(self) -> float:
        """Offline capability minus what actually reaches the reply."""
        return self.offline_recall - self.in_harness_recall


@dataclass
class Cat9aResult:
    """Category 9a — invocation rate — scorecard for one (model, harness)."""

    model: str
    harness: str
    n_positive: int
    per_hop: dict[int, HopHandshake] = field(default_factory=dict)
    n_negative: int = 0
    n_negative_invoked: int = 0
    empty_manifest: bool = False
    traces: list[HandshakeTrace] = field(default_factory=list)

    def _sum(self, attr: str) -> int:
        return sum(getattr(h, attr) for h in self.per_hop.values())

    @property
    def invocation_rate(self) -> float:
        return self._sum("invoked") / self.n_positive if self.n_positive else 0.0

    @property
    def offline_recall(self) -> float:
        return self._sum("offline_hits") / self.n_positive if self.n_positive else 0.0

    @property
    def in_harness_recall(self) -> float:
        return self._sum("in_harness_hits") / self.n_positive if self.n_positive else 0.0

    @property
    def integration_gap(self) -> float:
        """Headline metric: offline Cat 1 recall − in-harness recall."""
        return self.offline_recall - self.in_harness_recall

    @property
    def result_use_rate(self) -> float:
        through = self._sum("call_through")
        return self._sum("result_used") / through if through else 0.0

    @property
    def unnecessary_invocation_rate(self) -> float:
        """9d: invocation on no-answer negative-control questions."""
        return self.n_negative_invoked / self.n_negative if self.n_negative else 0.0

    @property
    def band(self) -> str:
        if self.empty_manifest:
            return "n/a"
        invoke_band = _band(self.invocation_rate, _INVOKE_HEALTHY, _INVOKE_WARN)
        # Gap is inverted (smaller is better), so band it by hand.
        gap = self.integration_gap
        gap_band = (
            "healthy" if gap <= _GAP_HEALTHY
            else "warn" if gap <= _GAP_WARN
            else "concerning"
        )
        # Worst of the two drives the headline.
        order = {"healthy": 0, "warn": 1, "concerning": 2}
        return invoke_band if order[invoke_band] >= order[gap_band] else gap_band


# --- Sub-test: 9a invocation rate -------------------------------------


def run_cat9a(
    adapter: SMEAdapter,
    runner: ModelRunner,
    questions: list[dict],
    *,
    negative_questions: list[dict] | None = None,
    match_threshold: float = 0.5,
) -> Cat9aResult:
    """Run Category 9a against an adapter using ``runner`` as the model.

    ``questions`` are the positive set — answerable, each a dict with
    ``text``, ``expected_sources`` (list[str]), and ``min_hops`` (int).
    Offline recall is computed from ``adapter.query()`` directly;
    in-harness recall from the model's reply via ``runner.run()``. Both
    use the same substring matcher, so the difference is purely the
    harness layer — that difference is the integration gap.

    ``match_threshold`` is the fraction of a question's ``expected_sources``
    that must appear for it to count as a hit. The default is 0.5 (partial
    credit), NOT 1.0: ``expected_sources`` often includes entities drawn
    from the *question* itself, so a correct-but-terse generative answer
    ("opened in July 2018") should not be failed for omitting "FDA"/"DCM".
    IMPORTANT: offline recall matches the full retrieved *context* while
    in-harness recall matches the model's short *final reply*, so the
    integration_gap is sensitive to this threshold — treat it as
    directional unless you raise the bar with a judge-based matcher.

    ``negative_questions`` (optional) is the held-out no-answer set for
    9d: how often the model invokes when it shouldn't.
    """
    manifest = adapter.get_harness_manifest()
    result = Cat9aResult(
        model=getattr(runner, "name", "model"),
        harness="(declared manifest)",
        n_positive=len(questions),
    )

    if not manifest:
        result.empty_manifest = True
        return result

    # Make 9a real against ANY adapter: a model tool-call should run a
    # genuine per-question retrieval. Adapters that declare an explicit
    # properties["execute"] keep it; the rest get one synthesized from
    # the required query() method, so the model's tool argument drives an
    # actual retrieval instead of falling back to the fixed probe_fn call.
    def _query_executor(args: dict) -> str:
        q = args.get("query") or args.get("text") or args.get("q") or ""
        qr = adapter.query(q)
        return (getattr(qr, "context_string", "") or "") or (
            getattr(qr, "answer", "") or ""
        )

    for descriptor in manifest:
        if "execute" not in descriptor.properties:
            descriptor.properties["execute"] = _query_executor

    # Let a hop-aware mock policy read min_hops without coupling to the
    # question schema (no-op for real runners that ignore hop_of).
    hop_map = {q.get("text", ""): int(q.get("min_hops", 1)) for q in questions}
    if getattr(runner, "hop_of", "missing") is None:
        runner.hop_of = lambda t: hop_map.get(t, 1)  # type: ignore[attr-defined]

    for q in questions:
        text = q.get("text", "")
        expected = q.get("expected_sources", []) or []
        hops = int(q.get("min_hops", 1))
        bucket = result.per_hop.setdefault(hops, HopHandshake(hops=hops))
        bucket.n += 1

        # Offline capability: does the adapter retrieve the answer at all?
        try:
            qr = adapter.query(text)
            offline_text = (qr.context_string or "") + " " + (qr.answer or "")
        except Exception:  # noqa: BLE001 — adapter is user code
            offline_text = ""
        if _question_hit(offline_text, expected, match_threshold):
            bucket.offline_hits += 1

        # In-harness: does the model invoke, and does the answer land?
        trace = runner.run(text, manifest)
        result.traces.append(trace)
        if trace.invoked:
            bucket.invoked += 1
        if trace.call_through:
            bucket.call_through += 1
        if _question_hit(trace.final_text, expected, match_threshold):
            bucket.in_harness_hits += 1
        # 9c proxy: retrieved content reflected in the reply at all.
        if trace.call_through and substring_recall(trace.final_text, expected) > 0:
            bucket.result_used += 1

    if negative_questions:
        result.n_negative = len(negative_questions)
        for q in negative_questions:
            trace = runner.run(q.get("text", ""), manifest)
            result.traces.append(trace)
            if trace.invoked:
                result.n_negative_invoked += 1

    return result


def format_cat9a_report(result: Cat9aResult, *, source_label: str = "") -> str:
    """Human-readable 9a scorecard with the hop-depth table as headline."""
    lines: list[str] = []
    header = "Category 9a — Harness Integration (Invocation Rate)"
    if source_label:
        header = f"{header} — {source_label}"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    if result.empty_manifest:
        lines.append(
            "  Adapter declared no harness manifest — Cat 9a does not apply. "
            "Implement get_harness_manifest() with an executable surface."
        )
        return "\n".join(lines) + "\n"

    lines.append(f"  model={result.model}  positives={result.n_positive}")
    lines.append(
        f"  invocation_rate={result.invocation_rate:.2f}  "
        f"result_use_rate={result.result_use_rate:.2f}  "
        f"band={result.band}"
    )
    lines.append(
        f"  offline_recall={result.offline_recall:.2f}  "
        f"in_harness_recall={result.in_harness_recall:.2f}  "
        f"INTEGRATION_GAP={result.integration_gap:+.2f}"
    )
    if result.n_negative:
        lines.append(
            f"  unnecessary_invocation_rate(9d)={result.unnecessary_invocation_rate:.2f} "
            f"({result.n_negative_invoked}/{result.n_negative} no-answer q invoked)"
        )
    lines.append("")

    # The headline: every metric cut by hop depth.
    lines.append("  By hop depth (the agentic-multi-hop cut):")
    lines.append("    hop   n  invoke%  callthru%  used%    gap")
    for hops in sorted(result.per_hop):
        h = result.per_hop[hops]
        used_pct = (h.result_used / h.call_through) if h.call_through else 0.0
        # Flag on the trustworthy signals (invocation, result-use), NOT the
        # raw gap — the gap is matcher-sensitive (offline matches retrieved
        # context, in-harness matches a terse reply) and would mislabel.
        if h.invocation_rate < _INVOKE_WARN:
            flag = "  <- under-invoked"
        elif h.invoked and used_pct < 0.5:
            flag = "  <- result ignored"
        else:
            flag = ""
        lines.append(
            f"    {hops:>3} {h.n:>3}   {h.invocation_rate:>5.2f}     "
            f"{(h.call_through / h.n if h.n else 0):>5.2f}    {used_pct:>4.2f}  "
            f"{h.integration_gap:>+5.2f}{flag}"
        )
    lines.append("")

    lines.append("  Reading:")
    if result.band == "healthy":
        lines.append(
            "    The agent reaches for memory across hop depths and the retrieved "
            "context lands in its replies. Offline capability transfers to the harness."
        )
    elif result.band == "warn":
        lines.append(
            "    Invocation or result-use is uneven. Inspect the hop table — a gap that "
            "widens with depth means the agent abandons multi-hop traversal."
        )
    else:
        lines.append(
            "    Large integration gap: the memory system can answer offline but the "
            "agent isn't reaching it (or ignores the result) where it counts. This is "
            "the deployment failure pure retrieval metrics never surface."
        )
    lines.append("")
    lines.append(
        "  Note: in-harness recall is matched against the model's FINAL reply, not the "
        "raw tool response. A result the model ignores does not count as retrieval."
    )
    lines.append(
        "  Caveat: integration_gap is matcher-sensitive — offline recall matches the "
        "full retrieved context, in-harness recall matches a terse generative reply. "
        "Read the gap as directional; invocation% and used% are the trustworthy signals "
        "until a judge-based matcher lands."
    )
    return "\n".join(lines) + "\n"
