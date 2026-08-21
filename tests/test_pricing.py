"""Tests for pricing table and cost-per-correct computation."""
from sme.eval.pricing import load_pricing_table, cost_per_correct, ModelPricing
import pytest

def test_load_default_pricing_table():
    table = load_pricing_table("2026_05")
    assert table.version == "2026_05"
    assert len(table.models) > 0

def test_model_pricing_cost():
    p = ModelPricing("test", input_per_1m=2.0, output_per_1m=10.0)
    # 1M input + 1M output = $2 + $10 = $12
    assert p.cost_for_tokens(1_000_000, 1_000_000) == 12.0
    # 500K input + 0 output = $1
    assert p.cost_for_tokens(500_000, 0) == 1.0

def test_pricing_table_get():
    table = load_pricing_table("2026_05")
    gpt4o = table.get("gpt-4o")
    assert gpt4o is not None
    assert gpt4o.input_per_1m > 0

def test_pricing_table_unknown_model():
    table = load_pricing_table("2026_05")
    assert table.get("nonexistent-model") is None

def test_pricing_table_cost_for_tokens():
    table = load_pricing_table("2026_05")
    cost = table.cost_for_tokens("gpt-4o-mini", 100_000, 50_000)
    assert cost is not None
    assert cost > 0

def test_cost_per_correct_basic():
    result = cost_per_correct(1.0, 10, 100)
    assert result["cost_per_correct_usd"] == pytest.approx(0.1)
    assert result["cost_per_query_usd"] == pytest.approx(0.01)

def test_cost_per_correct_zero_correct():
    result = cost_per_correct(1.0, 0, 100)
    assert result["cost_per_correct_usd"] is None

def test_cost_per_correct_zero_total():
    result = cost_per_correct(0.0, 0, 0)
    assert result["cost_per_query_usd"] == 0.0

def test_load_nonexistent_version():
    with pytest.raises(FileNotFoundError):
        load_pricing_table("1999_01")

def test_local_model_zero_cost():
    table = load_pricing_table("2026_05")
    cost = table.cost_for_tokens("local", 1_000_000, 1_000_000)
    assert cost == 0.0
