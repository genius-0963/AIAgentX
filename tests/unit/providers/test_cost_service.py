"""Unit tests for cost service."""

import pytest
from decimal import Decimal

from app.application.services.cost_service import CostService


def test_cost_service_initialization():
    """Test cost service initialization with pricing config."""
    pricing_config = {
        "openai:gpt-4o": {
            "prompt_price_usd_per_1m": 2.50,
            "completion_price_usd_per_1m": 10.00,
        },
        "anthropic:claude-3-opus": {
            "prompt_price_usd_per_1m": 15.00,
            "completion_price_usd_per_1m": 75.00,
        },
    }

    service = CostService(pricing_config)

    # Check pricing was loaded
    openai_pricing = service.get_pricing("openai", "gpt-4o")
    assert openai_pricing is not None
    assert openai_pricing.prompt_price_usd_per_1m == Decimal("2.50")
    assert openai_pricing.completion_price_usd_per_1m == Decimal("10.00")


def test_cost_calculation():
    """Test cost calculation."""
    pricing_config = {
        "openai:gpt-4o": {
            "prompt_price_usd_per_1m": 2.50,
            "completion_price_usd_per_1m": 10.00,
        },
    }

    service = CostService(pricing_config)

    # Calculate cost for 1000 prompt tokens and 500 completion tokens
    cost = service.calculate_cost("openai", "gpt-4o", 1000, 500)

    # Expected: (1000 * 2.50 / 1M) + (500 * 10.00 / 1M) = 0.0025 + 0.005 = 0.0075 USD
    # In micro-units: 0.0075 * 1M = 7500
    assert cost > 0
    assert cost == 7500  # 0.0075 USD in micro-units


def test_cost_calculation_with_zero_tokens():
    """Test cost calculation with zero tokens."""
    pricing_config = {
        "openai:gpt-4o": {
            "prompt_price_usd_per_1m": 2.50,
            "completion_price_usd_per_1m": 10.00,
        },
    }

    service = CostService(pricing_config)

    cost = service.calculate_cost("openai", "gpt-4o", 0, 0)
    assert cost == 0


def test_cost_calculation_unknown_provider():
    """Test cost calculation with unknown provider (uses default pricing)."""
    pricing_config = {}  # No pricing configured

    service = CostService(pricing_config)

    # Should use default pricing
    cost = service.calculate_cost("unknown", "unknown-model", 1000, 500)
    assert cost > 0


def test_add_pricing():
    """Test adding pricing dynamically."""
    pricing_config = {}
    service = CostService(pricing_config)

    # Add pricing
    service.add_pricing(
        provider="openai",
        model="gpt-4o",
        prompt_price_usd_per_1m=2.50,
        completion_price_usd_per_1m=10.00,
    )

    # Verify pricing was added
    pricing = service.get_pricing("openai", "gpt-4o")
    assert pricing is not None
    assert pricing.prompt_price_usd_per_1m == Decimal("2.50")


def test_remove_pricing():
    """Test removing pricing."""
    pricing_config = {
        "openai:gpt-4o": {
            "prompt_price_usd_per_1m": 2.50,
            "completion_price_usd_per_1m": 10.00,
        },
    }

    service = CostService(pricing_config)

    # Remove pricing
    removed = service.remove_pricing("openai", "gpt-4o")
    assert removed is True

    # Verify pricing was removed
    pricing = service.get_pricing("openai", "gpt-4o")
    assert pricing is None


def test_list_pricing():
    """Test listing all pricing."""
    pricing_config = {
        "openai:gpt-4o": {
            "prompt_price_usd_per_1m": 2.50,
            "completion_price_usd_per_1m": 10.00,
        },
        "anthropic:claude-3-opus": {
            "prompt_price_usd_per_1m": 15.00,
            "completion_price_usd_per_1m": 75.00,
        },
    }

    service = CostService(pricing_config)

    pricing_list = service.list_pricing()
    assert len(pricing_list) == 2

    providers = [p["provider"] for p in pricing_list]
    assert "openai" in providers
    assert "anthropic" in providers


def test_cost_calculation_negative_tokens():
    """Test cost calculation with negative tokens raises error."""
    pricing_config = {
        "openai:gpt-4o": {
            "prompt_price_usd_per_1m": 2.50,
            "completion_price_usd_per_1m": 10.00,
        },
    }

    service = CostService(pricing_config)

    with pytest.raises(ValueError, match="Token counts cannot be negative"):
        service.calculate_cost("openai", "gpt-4o", -1, 500)
