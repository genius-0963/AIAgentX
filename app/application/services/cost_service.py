"""Cost calculation service for provider usage."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.providers.value_objects import CostCalculation
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class CostService:
    """Service for calculating costs based on provider usage and pricing.

    This service maintains pricing configurations for different providers
    and models, and calculates costs based on token usage.
    """

    def __init__(self, pricing_config: dict[str, dict[str, Any]]) -> None:
        """Initialize cost service with pricing configuration.

        Args:
            pricing_config: Dictionary mapping "provider:model" to pricing info
                          Format: {"provider:model": {"prompt_price_usd_per_1m": float, "completion_price_usd_per_1m": float}}
        """
        self._pricing_config: dict[str, CostCalculation] = {}
        self._load_pricing_config(pricing_config)

    def _load_pricing_config(self, pricing_config: dict[str, dict[str, Any]]) -> None:
        """Load pricing configuration into CostCalculation objects.

        Args:
            pricing_config: Raw pricing configuration dictionary
        """
        for key, pricing in pricing_config.items():
            try:
                provider, model = key.split(":", 1)
                cost_calc = CostCalculation(
                    provider=provider,
                    model=model,
                    prompt_price_usd_per_1m=Decimal(str(pricing.get("prompt_price_usd_per_1m", 0))),
                    completion_price_usd_per_1m=Decimal(str(pricing.get("completion_price_usd_per_1m", 0))),
                )
                self._pricing_config[key] = cost_calc
                logger.info(
                    "Pricing loaded",
                    extra={
                        "provider": provider,
                        "model": model,
                        "prompt_price": str(cost_calc.prompt_price_usd_per_1m),
                        "completion_price": str(cost_calc.completion_price_usd_per_1m),
                    },
                )
            except Exception as e:
                logger.error(
                    "Failed to load pricing configuration",
                    extra={"key": key, "error": str(e)},
                )

    def calculate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> int:
        """Calculate cost in micro-units for a provider request.

        Args:
            provider: Provider name (e.g., 'openai')
            model: Model name (e.g., 'gpt-4o')
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Cost in micro-units (1/1,000,000 USD)

        Raises:
            ValueError: If pricing not found for provider:model
        """
        key = f"{provider}:{model}"
        cost_calc = self._pricing_config.get(key)

        if not cost_calc:
            logger.warning(
                "Pricing not found for provider:model, using default pricing",
                extra={"provider": provider, "model": model, "key": key},
            )
            # Use default pricing (very low to avoid runaway costs)
            cost_calc = CostCalculation(
                provider=provider,
                model=model,
                prompt_price_usd_per_1m=Decimal("0.01"),  # $0.01 per 1M tokens
                completion_price_usd_per_1m=Decimal("0.02"),  # $0.02 per 1M tokens
            )

        return cost_calc.calculate_cost(prompt_tokens, completion_tokens)

    def get_pricing(self, provider: str, model: str) -> CostCalculation | None:
        """Get pricing configuration for a provider and model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            CostCalculation if found, None otherwise
        """
        key = f"{provider}:{model}"
        return self._pricing_config.get(key)

    def list_pricing(self) -> list[dict[str, Any]]:
        """List all available pricing configurations.

        Returns:
            List of pricing configuration dictionaries
        """
        return [
            {
                "provider": calc.provider,
                "model": calc.model,
                "prompt_price_usd_per_1m": str(calc.prompt_price_usd_per_1m),
                "completion_price_usd_per_1m": str(calc.completion_price_usd_per_1m),
            }
            for calc in self._pricing_config.values()
        ]

    def add_pricing(
        self,
        provider: str,
        model: str,
        prompt_price_usd_per_1m: float,
        completion_price_usd_per_1m: float,
    ) -> None:
        """Add or update pricing for a provider and model.

        Args:
            provider: Provider name
            model: Model name
            prompt_price_usd_per_1m: Price per 1M prompt tokens in USD
            completion_price_usd_per_1m: Price per 1M completion tokens in USD
        """
        cost_calc = CostCalculation(
            provider=provider,
            model=model,
            prompt_price_usd_per_1m=Decimal(str(prompt_price_usd_per_1m)),
            completion_price_usd_per_1m=Decimal(str(completion_price_usd_per_1m)),
        )
        key = f"{provider}:{model}"
        self._pricing_config[key] = cost_calc

        logger.info(
            "Pricing updated",
            extra={
                "provider": provider,
                "model": model,
                "prompt_price": str(cost_calc.prompt_price_usd_per_1m),
                "completion_price": str(cost_calc.completion_price_usd_per_1m),
            },
        )

    def remove_pricing(self, provider: str, model: str) -> bool:
        """Remove pricing for a provider and model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            True if pricing was removed, False if not found
        """
        key = f"{provider}:{model}"
        if key in self._pricing_config:
            del self._pricing_config[key]
            logger.info("Pricing removed", extra={"provider": provider, "model": model})
            return True
        return False
