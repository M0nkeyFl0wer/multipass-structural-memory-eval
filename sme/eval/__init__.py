"""SME evaluation utilities — wrappers around external benchmark scorers.

Currently:

- ``longmemeval_judge`` — thin wrapper around the LongMemEval (Wu et al.,
  ICLR 2025; arXiv 2410.10813) GPT-4o-judge methodology, used by the
  cross-validation harness in ``scripts/cross_validate_longmemeval.py``.

The intent of this package is to keep upstream-benchmark-specific scorer
code out of ``sme.adapters`` / ``sme.categories`` (those modules describe
SME's own measurements; this one wraps *other people's* measurements so
SME numbers can be calibrated against them).
"""

from sme.eval.longmemeval_judge import grade_answer

__all__ = ["grade_answer"]
