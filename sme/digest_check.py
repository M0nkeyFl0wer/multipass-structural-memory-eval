"""Turn the nightly `sme-eval check --json` reading into operator-digest findings.

The operator digest (spec: homelab-status
`findings/2026-11-13-operator-digest-spec.md`) runs one executable per check
and reads JSON lines from its stdout. Each line is a finding:

    {"project", "check", "key", "severity", "what", "action", "evidence"}

`severity` is one of page / act / watch / ok. The digest dedupes on
`(project, check, key)`, so `key` must name the PROBLEM, never its numbers:
that is what lets a regression read "STILL OPEN, day 3" instead of looking
new every morning.

Contract rules this module keeps (each one is a way a check goes silent):

- Always at least one line. A clean night is an explicit `ok` line, so a
  check that printed nothing is an error the digest can see, not "all clear".
- A reading that is missing, unreadable or old is itself a finding. The
  nightly once sat blind for ~9 nights (2026-06) with nobody told; a stale
  file must never pass for a healthy one.
- A reading with no `regression` block means the nightly ran WITHOUT
  `--baseline`, so nothing was being compared. That is reported too: the
  alarm being unplugged is exactly the failure this whole path exists for.

Read-only and deterministic: no graph access, no network, no LLM.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

CHECK = "sme-graph-health"


def _line(project: str, key: str, severity: str, what: str, *,
          action: str = "", evidence: str = "") -> dict:
    line = {"project": project, "check": CHECK, "key": key,
            "severity": severity, "what": what}
    if action:
        line["action"] = action
    if evidence:
        line["evidence"] = evidence
    return line


def digest_lines(reading: Path, *, project: str = "hybrid-OG-vault-rag",
                 max_age_hours: float = 36.0,
                 now: float | None = None) -> list[dict]:
    """Return the digest findings for one reading file. Never empty."""
    now = time.time() if now is None else now

    if not reading.exists():
        return [_line(
            project, "reading-missing", "act",
            f"no nightly SME reading at {reading}",
            action="systemctl --user status vault-rag-sme.service vault-rag-sme.timer",
        )]
    try:
        data = json.loads(reading.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [_line(
            project, "reading-unreadable", "act",
            f"nightly SME reading is unreadable ({exc.__class__.__name__})",
            action=f"inspect {reading}; the next nightly run rewrites it",
        )]

    lines: list[dict] = []
    mtime = reading.stat().st_mtime
    written = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    age_h = (now - mtime) / 3600
    if age_h > max_age_hours:
        lines.append(_line(
            project, "stale", "act",
            f"last SME reading is {age_h:.0f} h old: the nightly is not running",
            action="systemctl --user status vault-rag-sme.service vault-rag-sme.timer",
            evidence=f"{reading} written {written}",
        ))

    reg = data.get("regression")
    if reg is None:
        lines.append(_line(
            project, "no-baseline-compare", "watch",
            "the nightly ran without --baseline, so regressions are not being checked",
            action="run_sme.sh should pass --baseline; check that sme-eval "
                   "supports it (`sme-eval check --help`)",
            evidence=f"{reading} has no 'regression' block",
        ))
        status = None
    else:
        status = reg.get("status")
    baseline = (reg or {}).get("baseline", "")

    if status == "regressed":
        for f in reg.get("findings") or []:
            lines.append(_line(
                project, f"regression:{f.get('key', '?')}", "act",
                f"vault graph: {f.get('what', '?')}",
                # The alarm stays red until a human decides: the baseline only
                # advances on a clean night, so accepting is an explicit act.
                action=(
                    "go look (a merge, dedup or prune moves this legitimately; "
                    f"it does not mean corruption). If intended, accept it: "
                    f"cp {reading} {baseline}"
                ),
                evidence=f"{reading} written {written} vs {baseline}",
            ))
    elif status == "unreadable":
        lines.append(_line(
            project, "baseline-unreadable", "act",
            f"the regression baseline {baseline} could not be read",
            action=f"re-seed it from the last good reading: cp {reading} {baseline}",
        ))
    elif status == "no_baseline":
        lines.append(_line(
            project, "no-baseline-yet", "watch",
            "no regression baseline yet, so nothing was compared",
            action="normal on the first night only; a clean run seeds it",
            evidence=f"expected at {baseline}",
        ))

    if not lines:
        lines.append(_line(
            project, "ok", "ok",
            f"vault graph steady: no metric moved beyond tolerance "
            f"({data.get('cat4', {}).get('entities', '?')} entities, "
            f"{data.get('cat4', {}).get('edges', '?')} edges)",
            evidence=f"{reading} written {written}",
        ))
    return lines
