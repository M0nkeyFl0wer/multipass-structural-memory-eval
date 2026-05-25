"""Tests for sme/stats/ — bootstrap CI and FDR correction."""
from __future__ import annotations

import pytest

from sme.stats.bootstrap import paired_bootstrap_ci
from sme.stats.fdr import benjamini_hochberg


class TestPairedBootstrapCI:
    def test_identical_scores_zero_diff(self):
        """Identical paired scores should give CI containing zero."""
        scores = [0.8, 0.6, 0.7, 0.9, 0.5]
        result = paired_bootstrap_ci(scores, scores)
        assert result.mean_diff == 0.0
        assert result.ci_lower <= 0.0 <= result.ci_upper

    def test_clear_winner_positive_ci(self):
        """When A clearly beats B, CI should be entirely positive."""
        a = [1.0] * 50
        b = [0.0] * 50
        result = paired_bootstrap_ci(a, b)
        assert result.mean_diff == 1.0
        assert result.ci_lower > 0.0
        assert result.p_value_approx < 0.05

    def test_seed_determinism(self):
        """Same seed should give identical results."""
        a = [0.8, 0.6, 0.7, 0.9, 0.5, 0.4, 0.8, 0.7, 0.6, 0.5]
        b = [0.5, 0.4, 0.6, 0.7, 0.3, 0.2, 0.6, 0.5, 0.4, 0.3]
        r1 = paired_bootstrap_ci(a, b, seed=123)
        r2 = paired_bootstrap_ci(a, b, seed=123)
        assert r1.mean_diff == r2.mean_diff
        assert r1.ci_lower == r2.ci_lower
        assert r1.ci_upper == r2.ci_upper

    def test_mismatched_lengths_raises(self):
        with pytest.raises(AssertionError):
            paired_bootstrap_ci([1, 2, 3], [1, 2])


class TestBenjaminiHochberg:
    def test_no_pvalues(self):
        result = benjamini_hochberg([])
        assert result.adjusted_p_values == []
        assert result.rejected == []

    def test_all_significant(self):
        """Very small p-values should all survive correction."""
        result = benjamini_hochberg([0.001, 0.002, 0.003])
        assert all(result.rejected)

    def test_mixed_significance(self):
        """Mix of significant and non-significant p-values.

        For [0.01, 0.04, 0.5, 0.8] with m=4 and alpha=0.05, BH-adjusted
        p-values are [0.04, 0.08, 0.667, 0.8] — only the first survives.
        """
        result = benjamini_hochberg([0.01, 0.04, 0.5, 0.8])
        assert result.rejected[0] is True
        assert result.rejected[2] is False
        assert result.rejected[3] is False

    def test_adjusted_monotonic_with_original_order(self):
        """Adjusted p-values should never be less than originals."""
        pvals = [0.01, 0.03, 0.05, 0.1, 0.5]
        result = benjamini_hochberg(pvals)
        for orig, adj in zip(pvals, result.adjusted_p_values):
            assert adj >= orig or abs(adj - orig) < 1e-10
