"""Versioned model pricing for cost-per-correct computation (HELM methodology).

Pricing tables are YAML files at sme/eval/pricing_YYYY_MM.yaml.
Each table maps model identifiers to $/1M token rates for input
and output. Tables are versioned by date because pricing drifts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

PRICING_DIR = Path(__file__).parent


@dataclass
class ModelPricing:
    """Per-model pricing in USD per 1M tokens."""
    model_id: str
    input_per_1m: float
    output_per_1m: float

    def cost_for_tokens(self, input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1_000_000) * self.input_per_1m
            + (output_tokens / 1_000_000) * self.output_per_1m
        )


@dataclass
class PricingTable:
    """A versioned pricing table."""
    version: str
    models: dict[str, ModelPricing]

    def get(self, model_id: str) -> Optional[ModelPricing]:
        return self.models.get(model_id)

    def cost_for_tokens(self, model_id: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        pricing = self.get(model_id)
        if pricing is None:
            return None
        return pricing.cost_for_tokens(input_tokens, output_tokens)


def load_pricing_table(version: str = "2026_05") -> PricingTable:
    """Load a versioned pricing table from YAML."""
    path = PRICING_DIR / f"pricing_{version}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"pricing table not found: {path}. "
            f"Available: {[p.stem for p in PRICING_DIR.glob('pricing_*.yaml')]}"
        )
    raw = yaml.safe_load(path.read_text())
    declared_version = raw.get("version")
    if declared_version is not None and declared_version != version:
        raise ValueError(
            f"pricing table version mismatch: requested {version!r} "
            f"but {path.name} declares {declared_version!r}"
        )
    models = {}
    for model_id, rates in raw.get("models", {}).items():
        models[model_id] = ModelPricing(
            model_id=model_id,
            input_per_1m=float(rates.get("input_per_1m", 0)),
            output_per_1m=float(rates.get("output_per_1m", 0)),
        )
    return PricingTable(version=declared_version or version, models=models)


def cost_per_correct(
    total_cost_usd: float,
    correct_count: int,
    total_count: int,
) -> dict:
    """Compute cost-per-correct headline metric.

    Returns:
        {
            "total_cost_usd": float,
            "correct_count": int,
            "total_count": int,
            "cost_per_correct_usd": float or None (if 0 correct),
            "cost_per_query_usd": float,
        }
    """
    return {
        "total_cost_usd": round(total_cost_usd, 6),
        "correct_count": correct_count,
        "total_count": total_count,
        "cost_per_correct_usd": round(total_cost_usd / correct_count, 6) if correct_count > 0 else None,
        "cost_per_query_usd": round(total_cost_usd / total_count, 6) if total_count > 0 else 0.0,
    }
