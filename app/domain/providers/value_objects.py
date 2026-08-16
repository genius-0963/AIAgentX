"""Provider value objects for configuration and usage tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderConfig:
    """Configuration for a model provider."""

    provider: str  # 'openai', 'anthropic', 'fake'
    model: str
    api_key: str
    base_url: str | None = None
    timeout_seconds: int = 45
    connect_timeout_seconds: int = 3
    max_retries: int = 2

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("Provider cannot be empty")
        if not self.model:
            raise ValueError("Model cannot be empty")
        if not self.api_key:
            raise ValueError("API key cannot be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if self.connect_timeout_seconds <= 0:
            raise ValueError("Connect timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageRecord:
    """Record of token usage for a single provider call."""

    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_microunits: int
    timestamp: float  # Unix timestamp
    request_id: str

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("Provider cannot be empty")
        if not self.model:
            raise ValueError("Model cannot be empty")
        if self.prompt_tokens < 0:
            raise ValueError("Prompt tokens cannot be negative")
        if self.completion_tokens < 0:
            raise ValueError("Completion tokens cannot be negative")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("Total tokens must equal prompt + completion")
        if self.cost_microunits < 0:
            raise ValueError("Cost cannot be negative")
        if self.timestamp <= 0:
            raise ValueError("Timestamp must be positive")
        if not self.request_id:
            raise ValueError("Request ID cannot be empty")


@dataclass(frozen=True, slots=True, kw_only=True)
class CostCalculation:
    """Cost calculation for a provider and model."""

    provider: str
    model: str
    prompt_price_usd_per_1m: Decimal  # Price per 1M prompt tokens
    completion_price_usd_per_1m: Decimal  # Price per 1M completion tokens

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> int:
        """Calculate cost in micro-units.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Cost in micro-units (1/1,000,000 USD)
        """
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("Token counts cannot be negative")

        # Calculate cost in USD
        prompt_cost_usd = (Decimal(prompt_tokens) * self.prompt_price_usd_per_1m) / Decimal("1_000_000")
        completion_cost_usd = (
            Decimal(completion_tokens) * self.completion_price_usd_per_1m
        ) / Decimal("1_000_000")
        total_cost_usd = prompt_cost_usd + completion_cost_usd

        # Convert to micro-units
        return int((total_cost_usd * Decimal("1_000_000")).to_integral_value())


@dataclass(frozen=True, slots=True, kw_only=True)
class RetryPolicy:
    """Retry policy configuration."""

    max_retries: int = 2
    initial_backoff_ms: int = 1000
    max_backoff_ms: int = 10000
    backoff_multiplier: float = 2.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")
        if self.initial_backoff_ms <= 0:
            raise ValueError("Initial backoff must be positive")
        if self.max_backoff_ms <= 0:
            raise ValueError("Max backoff must be positive")
        if self.backoff_multiplier <= 1.0:
            raise ValueError("Backoff multiplier must be greater than 1.0")


@dataclass(frozen=True, slots=True, kw_only=True)
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_rate_threshold: float = 0.5  # Circuit opens when failure rate exceeds this
    minimum_requests: int = 10  # Minimum requests before considering failure rate
    open_timeout_seconds: int = 60  # How long to stay open before attempting recovery
    half_open_max_calls: int = 3  # Number of test calls in half-open state

    def __post_init__(self) -> None:
        if not 0 <= self.failure_rate_threshold <= 1:
            raise ValueError("Failure rate threshold must be between 0 and 1")
        if self.minimum_requests <= 0:
            raise ValueError("Minimum requests must be positive")
        if self.open_timeout_seconds <= 0:
            raise ValueError("Open timeout must be positive")
        if self.half_open_max_calls <= 0:
            raise ValueError("Half-open max calls must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class FallbackConfig:
    """Fallback configuration."""

    primary_provider: str
    fallback_providers: list[str] = field(default_factory=list)
    require_same_data_residency: bool = True
    require_same_capability_class: bool = True
    max_fallback_attempts: int = 2

    def __post_init__(self) -> None:
        if not self.primary_provider:
            raise ValueError("Primary provider cannot be empty")
        if self.max_fallback_attempts < 0:
            raise ValueError("Max fallback attempts cannot be negative")
