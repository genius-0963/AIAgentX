"""Unit tests for provider value objects."""

import pytest
from decimal import Decimal

from app.domain.providers.value_objects import (
    ProviderConfig,
    UsageRecord,
    CostCalculation,
    RetryPolicy,
    CircuitBreakerConfig,
    FallbackConfig,
)


def test_provider_config_validation():
    """Test ProviderConfig validation."""
    # Valid config
    config = ProviderConfig(
        provider="openai",
        model="gpt-4o",
        api_key="test-key",
    )
    assert config.provider == "openai"
    assert config.model == "gpt-4o"
    assert config.api_key == "test-key"

    # Invalid: empty provider
    with pytest.raises(ValueError, match="Provider cannot be empty"):
        ProviderConfig(
            provider="",
            model="gpt-4o",
            api_key="test-key",
        )

    # Invalid: empty API key
    with pytest.raises(ValueError, match="API key cannot be empty"):
        ProviderConfig(
            provider="openai",
            model="gpt-4o",
            api_key="",
        )

    # Invalid: negative timeout
    with pytest.raises(ValueError, match="Timeout must be positive"):
        ProviderConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
            timeout_seconds=-1,
        )


def test_usage_record_validation():
    """Test UsageRecord validation."""
    import time

    # Valid record
    record = UsageRecord(
        provider="openai",
        model="gpt-4o",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_microunits=100,
        timestamp=time.time(),
        request_id="test-id",
    )
    assert record.provider == "openai"
    assert record.total_tokens == 30

    # Invalid: total tokens mismatch
    with pytest.raises(ValueError, match="total_tokens must equal prompt"):
        UsageRecord(
            provider="openai",
            model="gpt-4o",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=35,  # Wrong total
            cost_microunits=100,
            timestamp=time.time(),
            request_id="test-id",
        )

    # Invalid: negative tokens
    with pytest.raises(ValueError, match="Prompt tokens cannot be negative"):
        UsageRecord(
            provider="openai",
            model="gpt-4o",
            prompt_tokens=-1,
            completion_tokens=20,
            total_tokens=19,
            cost_microunits=100,
            timestamp=time.time(),
            request_id="test-id",
        )


def test_cost_calculation():
    """Test CostCalculation."""
    calc = CostCalculation(
        provider="openai",
        model="gpt-4o",
        prompt_price_usd_per_1m=Decimal("2.50"),
        completion_price_usd_per_1m=Decimal("10.00"),
    )

    # Calculate cost
    cost = calc.calculate_cost(prompt_tokens=1000, completion_tokens=500)
    assert cost > 0

    # Test with zero tokens
    cost_zero = calc.calculate_cost(prompt_tokens=0, completion_tokens=0)
    assert cost_zero == 0

    # Test with negative tokens
    with pytest.raises(ValueError, match="Token counts cannot be negative"):
        calc.calculate_cost(prompt_tokens=-1, completion_tokens=500)


def test_retry_policy():
    """Test RetryPolicy validation."""
    # Valid policy
    policy = RetryPolicy(
        max_retries=3,
        initial_backoff_ms=1000,
        max_backoff_ms=10000,
        backoff_multiplier=2.0,
        jitter=True,
    )
    assert policy.max_retries == 3
    assert policy.jitter is True

    # Invalid: negative max retries
    with pytest.raises(ValueError, match="Max retries cannot be negative"):
        RetryPolicy(max_retries=-1)

    # Invalid: backoff multiplier <= 1
    with pytest.raises(ValueError, match="Backoff multiplier must be greater than"):
        RetryPolicy(backoff_multiplier=1.0)


def test_circuit_breaker_config():
    """Test CircuitBreakerConfig validation."""
    # Valid config
    config = CircuitBreakerConfig(
        failure_rate_threshold=0.5,
        minimum_requests=10,
        open_timeout_seconds=60,
        half_open_max_calls=3,
    )
    assert config.failure_rate_threshold == 0.5

    # Invalid: failure rate > 1
    with pytest.raises(ValueError, match="Failure rate threshold must be between"):
        CircuitBreakerConfig(failure_rate_threshold=1.5)

    # Invalid: failure rate < 0
    with pytest.raises(ValueError, match="Failure rate threshold must be between"):
        CircuitBreakerConfig(failure_rate_threshold=-0.1)


def test_fallback_config():
    """Test FallbackConfig validation."""
    # Valid config
    config = FallbackConfig(
        primary_provider="openai",
        fallback_providers=["anthropic"],
        max_fallback_attempts=2,
    )
    assert config.primary_provider == "openai"
    assert "anthropic" in config.fallback_providers

    # Invalid: empty primary provider
    with pytest.raises(ValueError, match="Primary provider cannot be empty"):
        FallbackConfig(primary_provider="")

    # Invalid: negative max attempts
    with pytest.raises(ValueError, match="Max fallback attempts cannot be negative"):
        FallbackConfig(
            primary_provider="openai",
            max_fallback_attempts=-1,
        )
