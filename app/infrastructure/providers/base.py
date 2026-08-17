"""Base provider adapter with common functionality."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.domain.providers.exceptions import (
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderValidationError,
)
from app.domain.providers.models import ModelRequest, ModelResponse, ProviderError
from app.domain.providers.protocols import ModelProvider
from app.domain.providers.value_objects import ProviderConfig, RetryPolicy
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class BaseProvider(ABC, ModelProvider):
    """Base provider adapter with common functionality.

    This abstract base class provides common functionality for all provider
    adapters including timeout handling, error classification, structured logging,
    and correlation ID propagation.
    """

    def __init__(self, config: ProviderConfig, retry_policy: RetryPolicy | None = None) -> None:
        self._config = config
        self._retry_policy = retry_policy or RetryPolicy()
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return self._config.provider

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(
                connect=self._config.connect_timeout_seconds,
                read=self._config.timeout_seconds,
                write=self._config.timeout_seconds,
            )
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

            base_url = self._get_base_url()
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                base_url=base_url,
            )
        return self._client

    def _get_base_url(self) -> str:
        """Get the base URL for the provider.

        Can be overridden by subclasses to provide custom base URLs.
        """
        return self._config.base_url or ""

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Execute a model completion request with retry logic.

        This method implements the retry logic with exponential backoff and
        delegates the actual provider call to the subclass implementation.
        """
        last_error: Exception | None = None
        start_time = time.time()

        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                response = await self._complete_with_retry(request, attempt)
                latency_ms = (time.time() - start_time) * 1000

                logger.info(
                    "Provider request completed",
                    extra={
                        "provider": self.provider_name,
                        "model": request.model,
                        "request_id": request.request_id,
                        "attempt": attempt,
                        "latency_ms": latency_ms,
                        "tokens": response.usage.get("total_tokens", 0),
                    },
                )

                return response

            except Exception as e:
                last_error = e
                provider_error = self._classify_error(e)

                if not provider_error.is_retryable or attempt >= self._retry_policy.max_retries:
                    logger.error(
                        "Provider request failed permanently",
                        extra={
                            "provider": self.provider_name,
                            "model": request.model,
                            "request_id": request.request_id,
                            "attempt": attempt,
                            "error_type": provider_error.error_type,
                            "error_message": str(e),
                        },
                    )
                    raise self._map_exception(provider_error) from e

                # Calculate backoff and wait
                backoff_ms = self._calculate_backoff(attempt)
                logger.warning(
                    "Provider request failed, retrying",
                    extra={
                        "provider": self.provider_name,
                        "model": request.model,
                        "request_id": request.request_id,
                        "attempt": attempt,
                        "backoff_ms": backoff_ms,
                        "error_type": provider_error.error_type,
                    },
                )
                await self._sleep(backoff_ms / 1000)

        # This should never be reached, but just in case
        if last_error:
            raise last_error
        raise ProviderUnavailableError("Max retries exceeded", self.provider_name)

    @abstractmethod
    async def _complete_with_retry(self, request: ModelRequest, attempt: int) -> ModelResponse:
        """Execute the actual provider call (subclass implementation).

        Args:
            request: The model request
            attempt: Current retry attempt number

        Returns:
            ModelResponse from the provider
        """
        ...

    @abstractmethod
    def _normalize_request(self, request: ModelRequest) -> dict[str, Any]:
        """Normalize request to provider-specific format.

        Args:
            request: Internal model request

        Returns:
            Provider-specific request dictionary
        """
        ...

    @abstractmethod
    def _normalize_response(self, response_data: dict[str, Any], request: ModelRequest) -> ModelResponse:
        """Normalize provider response to internal format.

        Args:
            response_data: Provider-specific response
            request: Original request for context

        Returns:
            Internal ModelResponse
        """
        ...

    def _classify_error(self, error: Exception) -> ProviderError:
        """Classify error as retryable or non-retryable.

        Args:
            error: The exception to classify

        Returns:
            ProviderError with classification
        """
        if isinstance(error, httpx.TimeoutException):
            return ProviderError(
                is_retryable=True,
                error_type="timeout",
                original_error=error,
                provider=self.provider_name,
                message="Request timed out",
            )
        elif isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if status_code == 429:
                return ProviderError(
                    is_retryable=True,
                    error_type="rate_limit",
                    original_error=error,
                    provider=self.provider_name,
                    message="Rate limit exceeded",
                )
            elif 500 <= status_code < 600:
                return ProviderError(
                    is_retryable=True,
                    error_type="server_error",
                    original_error=error,
                    provider=self.provider_name,
                    message=f"Server error: {status_code}",
                )
            elif status_code == 401:
                return ProviderError(
                    is_retryable=False,
                    error_type="auth_error",
                    original_error=error,
                    provider=self.provider_name,
                    message="Authentication failed",
                )
            elif status_code == 400:
                return ProviderError(
                    is_retryable=False,
                    error_type="validation_error",
                    original_error=error,
                    provider=self.provider_name,
                    message="Request validation failed",
                )
            else:
                return ProviderError(
                    is_retryable=False,
                    error_type="unknown",
                    original_error=error,
                    provider=self.provider_name,
                    message=f"HTTP error: {status_code}",
                )
        elif isinstance(error, httpx.ConnectError):
            return ProviderError(
                is_retryable=True,
                error_type="server_error",
                original_error=error,
                provider=self.provider_name,
                message="Connection failed",
            )
        else:
            return ProviderError(
                is_retryable=False,
                error_type="unknown",
                original_error=error,
                provider=self.provider_name,
                message=str(error),
            )

    def _map_exception(self, provider_error: ProviderError) -> Exception:
        """Map ProviderError to specific exception type.

        Args:
            provider_error: The classified provider error

        Returns:
            Specific exception type
        """
        error_map = {
            "timeout": ProviderTimeoutError,
            "rate_limit": ProviderRateLimitError,
            "auth_error": ProviderAuthenticationError,
            "validation_error": ProviderValidationError,
            "server_error": ProviderUnavailableError,
            "unknown": ProviderUnavailableError,
        }

        exception_class = error_map.get(provider_error.error_type, ProviderUnavailableError)
        return exception_class(provider_error.message, provider_error.provider)

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter.

        Args:
            attempt: Current retry attempt

        Returns:
            Backoff time in milliseconds
        """
        import random

        base_backoff = self._retry_policy.initial_backoff_ms * (
            self._retry_policy.backoff_multiplier ** attempt
        )
        capped_backoff = min(base_backoff, self._retry_policy.max_backoff_ms)

        if self._retry_policy.jitter:
            # Full jitter: random value between 0 and capped_backoff
            return random.uniform(0, capped_backoff)
        return capped_backoff

    async def _sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio

        await asyncio.sleep(seconds)

    async def health_check(self) -> bool:
        """Check if provider is healthy.

        Default implementation makes a simple health check request.
        Subclasses can override for provider-specific health checks.
        """
        try:
            client = await self._get_client()
            base_url = self._get_base_url()
            if not base_url:
                return True  # Fake provider or no base URL

            # Simple health check - adjust based on provider
            response = await client.get("/", timeout=5.0)
            return response.status_code < 500
        except Exception:
            return False

    def _get_trace_context(self, request: ModelRequest) -> dict[str, Any]:
        """Extract trace context from request for logging.

        Args:
            request: The model request

        Returns:
            Trace context dictionary
        """
        return request.trace_context or {}

    def _add_correlation_id(self, headers: dict[str, str], request: ModelRequest) -> None:
        """Add correlation ID to headers if available in trace context.

        Args:
            headers: Headers dictionary to modify
            request: The model request
        """
        trace_context = self._get_trace_context(request)
        if correlation_id := trace_context.get("correlation_id"):
            headers["X-Correlation-ID"] = correlation_id
