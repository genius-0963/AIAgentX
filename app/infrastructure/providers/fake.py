"""Deterministic fake provider for testing."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.domain.providers.models import ModelRequest, ModelResponse
from app.domain.providers.value_objects import ProviderConfig, RetryPolicy
from app.infrastructure.providers.base import BaseProvider
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class FakeProvider(BaseProvider):
    """Deterministic fake provider for testing.

    This provider allows for deterministic testing by:
    - Configurable responses
    - Configurable delays
    - Error simulation
    - Tool call simulation
    - Reproducible behavior based on request_id
    """

    def __init__(
        self,
        config: ProviderConfig,
        retry_policy: RetryPolicy | None = None,
        responses: dict[str, dict[str, Any]] | None = None,
        default_response: str = "Test response",
        default_delay_ms: float = 0,
        simulate_errors: bool = False,
        error_type: str = "none",
    ) -> None:
        super().__init__(config, retry_policy)
        self._responses = responses or {}
        self._default_response = default_response
        self._default_delay_ms = default_delay_ms
        self._simulate_errors = simulate_errors
        self._error_type = error_type
        self._call_count = 0

    async def _complete_with_retry(self, request: ModelRequest, attempt: int) -> ModelResponse:
        """Execute the fake provider call.

        Args:
            request: The model request
            attempt: Current retry attempt number

        Returns:
            ModelResponse from fake provider
        """
        self._call_count += 1

        # Check if we should simulate an error
        if self._simulate_errors:
            await self._simulate_error()

        # Apply delay if configured
        if self._default_delay_ms > 0:
            await asyncio.sleep(self._default_delay_ms / 1000)

        start_time = time.time()

        # Get response based on request_id or use default
        response_data = self._responses.get(request.request_id, {})
        content = response_data.get("content", self._default_response)
        tool_calls = response_data.get("tool_calls")
        tokens = response_data.get("tokens", {"prompt_tokens": 10, "completion_tokens": 20})

        latency_ms = (time.time() - start_time) * 1000 + self._default_delay_ms

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": tokens.get("prompt_tokens", 10),
                "completion_tokens": tokens.get("completion_tokens", 20),
                "total_tokens": tokens.get("prompt_tokens", 10) + tokens.get("completion_tokens", 20),
            },
            model=request.model,
            finish_reason="stop",
            request_id=request.request_id,
            provider=self.provider_name,
            latency_ms=latency_ms,
            safety_stop=False,
        )

    def _normalize_request(self, request: ModelRequest) -> dict[str, Any]:
        """Normalize request (no-op for fake provider).

        Args:
            request: Internal model request

        Returns:
            Request dictionary (unchanged)
        """
        return {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "tools": request.tools,
        }

    def _normalize_response(
        self, response_data: dict[str, Any], request: ModelRequest, latency_ms: float
    ) -> ModelResponse:
        """Normalize response (no-op for fake provider).

        Args:
            response_data: Response data
            request: Original request
            latency_ms: Latency in milliseconds

        Returns:
            ModelResponse
        """
        # This is not used in fake provider, but required by base class
        return ModelResponse(
            content=response_data.get("content", ""),
            tool_calls=response_data.get("tool_calls"),
            usage=response_data.get(
                "usage",
                {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            ),
            model=request.model,
            finish_reason="stop",
            request_id=request.request_id,
            provider=self.provider_name,
            latency_ms=latency_ms,
            safety_stop=False,
        )

    async def _simulate_error(self) -> None:
        """Simulate an error based on configured error type.

        Raises:
            Exception based on error_type configuration
        """
        if self._error_type == "timeout":
            await asyncio.sleep(100)  # Simulate timeout
        elif self._error_type == "rate_limit":
            from app.domain.providers.exceptions import ProviderRateLimitError

            raise ProviderRateLimitError("Rate limit exceeded", self.provider_name)
        elif self._error_type == "auth_error":
            from app.domain.providers.exceptions import ProviderAuthenticationError

            raise ProviderAuthenticationError("Authentication failed", self.provider_name)
        elif self._error_type == "server_error":
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError("Server error", self.provider_name)
        elif self._error_type == "validation_error":
            from app.domain.providers.exceptions import ProviderValidationError

            raise ProviderValidationError("Validation failed", self.provider_name)

    def set_response(self, request_id: str, response: dict[str, Any]) -> None:
        """Set a specific response for a request ID.

        Args:
            request_id: The request ID to set response for
            response: The response data
        """
        self._responses[request_id] = response

    def set_default_response(self, response: str) -> None:
        """Set the default response.

        Args:
            response: The default response text
        """
        self._default_response = response

    def set_delay(self, delay_ms: float) -> None:
        """Set the delay for responses.

        Args:
            delay_ms: Delay in milliseconds
        """
        self._default_delay_ms = delay_ms

    def set_error_simulation(self, simulate: bool, error_type: str = "none") -> None:
        """Configure error simulation.

        Args:
            simulate: Whether to simulate errors
            error_type: Type of error to simulate
        """
        self._simulate_errors = simulate
        self._error_type = error_type

    def reset_call_count(self) -> None:
        """Reset the call counter."""
        self._call_count = 0

    def get_call_count(self) -> int:
        """Get the number of calls made.

        Returns:
            Number of calls
        """
        return self._call_count

    async def health_check(self) -> bool:
        """Check if fake provider is healthy (always returns True).

        Returns:
            True
        """
        return True
