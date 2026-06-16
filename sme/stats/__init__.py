"""Statistical testing utilities for SME (bootstrap CIs, FDR correction)."""
from sme.stats.bootstrap import BootstrapCIResult, paired_bootstrap_ci
from sme.stats.fdr import FDRResult, benjamini_hochberg

__all__ = [
    "BootstrapCIResult",
    "FDRResult",
    "benjamini_hochberg",
    "paired_bootstrap_ci",
]
