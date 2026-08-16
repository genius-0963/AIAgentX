"""Model provider protocol and interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.providers.models import ModelRequest, ModelResponse


@runtime_checkable
class ModelProvider(Protocol):
    """Protocol for model provider adapters.

    This protocol defines the interface that all model provider adapters
    must implement. It enables the system to work with different LLM providers
    (OpenAI, Anthropic, etc.) through a unified interface.
    """

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Execute a model completion request.

        Args:
            request: The model request with messages, model, and parameters

        Returns:
            ModelResponse with content, tool calls, usage information

        Raises:
            ProviderUnavailableError: If provider is unavailable
            ProviderTimeoutError: If request times out
            ProviderRateLimitError: If rate limit is exceeded
            ProviderAuthenticationError: If authentication fails
            ProviderValidationError: If request validation fails
        """
        ...

    @property
    def provider_name(self) -> str:
        """Return provider identifier (e.g., 'openai', 'anthropic', 'fake')."""
        ...

    async def health_check(self) -> bool:
        """Check if provider is healthy.

        This is used by the circuit breaker to determine if the provider
        should receive requests.

        Returns:
            True if provider is healthy, False otherwise
        """
        ...
