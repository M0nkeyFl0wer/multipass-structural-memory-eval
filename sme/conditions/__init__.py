"""SME conditions package.

Holds adapters for SME's experimental conditions that don't correspond
to a specific memory system, but to a *retrieval/structure regime* used
as a comparison condition. See ``docs/cross_validation_2026.md`` § (4)
for the A/B/C/D condition framing.

Currently:

- ``full_context.FullContextAdapter`` — Condition D1, no retrieval, the
  entire corpus loaded into ``context_string``. Baseline that answers
  "is retrieval buying anything at all at this corpus size?"
"""

from sme.conditions.full_context import FullContextAdapter

__all__ = ["FullContextAdapter"]
