"""Paired bootstrap confidence intervals (Efron & Tibshirani 1993).

Standard non-parametric CI for per-question paired differences.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BootstrapCIResult:
    """Result of a paired bootstrap CI computation."""

    mean_diff: float
    ci_lower: float
    ci_upper: float
    n_bootstrap: int
    confidence_level: float
    p_value_approx: float  # two-sided: 2x the fraction of bootstrap means on the opposite side of zero (capped at 1.0)


def paired_bootstrap_ci(
    scores_a: list[float],
    scores_b: list[float],
    *,
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapCIResult:
    """Paired bootstrap CI on per-item score differences.

    Args:
        scores_a: Per-item scores for condition A
        scores_b: Per-item scores for condition B (same length, paired)
        n_bootstrap: Number of bootstrap resamples
        confidence: Confidence level (default 0.95 for 95% CI)
        seed: RNG seed for reproducibility

    Returns:
        BootstrapCIResult with mean difference and CI bounds
    """
    if len(scores_a) != len(scores_b):
        raise ValueError(
            f"Paired scores must be same length: got {len(scores_a)} and {len(scores_b)}"
        )
    rng = np.random.RandomState(seed)
    a = np.array(scores_a, dtype=float)
    b = np.array(scores_b, dtype=float)
    diffs = a - b
    observed_mean = float(np.mean(diffs))
    n = len(diffs)

    boot_means = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        indices = rng.randint(0, n, size=n)
        boot_means[i] = np.mean(diffs[indices])

    alpha = 1.0 - confidence
    ci_lower = float(np.percentile(boot_means, 100 * alpha / 2))
    ci_upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    if observed_mean >= 0:
        p_approx = float(np.mean(boot_means < 0))
    else:
        p_approx = float(np.mean(boot_means > 0))
    p_approx = min(2 * p_approx, 1.0)

    return BootstrapCIResult(
        mean_diff=observed_mean,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence,
        p_value_approx=p_approx,
    )
