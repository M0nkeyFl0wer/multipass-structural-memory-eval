"""Benjamini-Hochberg FDR correction for multiple comparisons."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class FDRResult:
    """Result of BH-FDR correction."""

    original_p_values: list[float]
    adjusted_p_values: list[float]
    rejected: list[bool]  # True = significant after correction
    alpha: float


def benjamini_hochberg(
    p_values: list[float],
    *,
    alpha: float = 0.05,
) -> FDRResult:
    """Benjamini-Hochberg FDR correction.

    Args:
        p_values: Raw p-values from multiple tests
        alpha: FDR threshold (default 0.05)

    Returns:
        FDRResult with adjusted p-values and rejection decisions
    """
    m = len(p_values)
    if m == 0:
        return FDRResult([], [], [], alpha)

    pv = np.array(p_values, dtype=float)
    sorted_idx = np.argsort(pv)
    sorted_pv = pv[sorted_idx]

    adjusted = np.empty(m)
    adjusted[sorted_idx[-1]] = sorted_pv[-1]
    for i in range(m - 2, -1, -1):
        rank = i + 1
        adj = sorted_pv[i] * m / rank
        adjusted[sorted_idx[i]] = min(adj, adjusted[sorted_idx[i + 1]])

    adjusted = np.minimum(adjusted, 1.0)
    rejected = adjusted <= alpha

    return FDRResult(
        original_p_values=p_values,
        adjusted_p_values=adjusted.tolist(),
        rejected=rejected.tolist(),
        alpha=alpha,
    )
