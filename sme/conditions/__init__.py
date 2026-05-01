"""SME conditions package.

Holds adapters for SME's experimental conditions that don't correspond
to a specific memory system, but to a *retrieval/structure regime* used
as a comparison condition. See ``docs/cross_validation_2026.md`` § (4)
for the A/B/C/D condition framing.

Currently:

- ``full_context.FullContextAdapter`` — Condition D1, no retrieval, the
  entire corpus loaded into ``context_string``. Baseline that answers
  "is retrieval buying anything at all at this corpus size?"
- ``karpathy_compiled.KarpathyCompiledAdapter`` — Condition D2,
  reads an LLM-compiled wiki + index produced by
  ``wiki_compiler.compile_vault``. Tests whether LLM compression at
  the same context budget improves over D1's raw concatenation.
"""

from sme.conditions.full_context import FullContextAdapter
from sme.conditions.karpathy_compiled import KarpathyCompiledAdapter
from sme.conditions.wiki_compiler import (
    CompileReport,
    LLMClient,
    compile_vault,
)

__all__ = [
    "CompileReport",
    "FullContextAdapter",
    "KarpathyCompiledAdapter",
    "LLMClient",
    "compile_vault",
]
