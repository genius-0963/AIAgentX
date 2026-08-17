"""OpenAI provider adapter."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.domain.providers.models import ModelRequest, ModelResponse
from app.domain.providers.value_objects import ProviderConfig, RetryPolicy
from app.infrastructure.providers.base import BaseProvider
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI provider adapter implementing ModelProvider protocol."""

    def __init__(self, config: ProviderConfig, retry_policy: RetryPolicy | None = None) -> None:
        super().__init__(config, retry_policy)
        # Set default base URL if not provided
        self._base_url = config.base_url or "https://api.openai.com/v1"

    def _get_base_url(self) -> str:
        """Get the base URL for OpenAI API."""
        return self._base_url

    async def _complete_with_retry(self, request: ModelRequest, attempt: int) -> ModelResponse:
        """Execute the actual OpenAI API call.

        Args:
            request: The model request
            attempt: Current retry attempt number

        Returns:
            ModelResponse from OpenAI
        """
        client = await self._get_client()
        normalized_request = self._normalize_request(request)

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        self._add_correlation_id(headers, request)

        start_time = time.time()

        response = await client.post(
            "/chat/completions",
            json=normalized_request,
            headers=headers,
        )

        response.raise_for_status()
        response_data = response.json()

        latency_ms = (time.time() - start_time) * 1000

        return self._normalize_response(response_data, request, latency_ms)

    def _normalize_request(self, request: ModelRequest) -> dict[str, Any]:
        """Normalize internal request to OpenAI format.

        Args:
            request: Internal model request

        Returns:
            OpenAI-specific request dictionary
        """
        openai_request = {
            "model": request.model,
            "messages": request.messages,
        }

        if request.temperature is not None:
            openai_request["temperature"] = request.temperature

        if request.max_tokens is not None:
            openai_request["max_tokens"] = request.max_tokens

        if request.tools:
            openai_request["tools"] = request.tools

        return openai_request

    def _normalize_response(
        self, response_data: dict[str, Any], request: ModelRequest, latency_ms: float
    ) -> ModelResponse:
        """Normalize OpenAI response to internal format.

        Args:
            response_data: OpenAI response JSON
            request: Original request for context
            latency_ms: Request latency in milliseconds

        Returns:
            Internal ModelResponse
        """
        choice = response_data["choices"][0]
        message = choice["message"]
        usage = response_data["usage"]

        # Extract content
        content = message.get("content")

        # Extract tool calls
        tool_calls = message.get("tool_calls")
        if tool_calls:
            # Normalize tool calls to internal format
            tool_calls = [
                {
                    "id": tc.get("id"),
                    "type": tc.get("type"),
                    "function": {
                        "name": tc.get("function", {}).get("name"),
                        "arguments": tc.get("function", {}).get("arguments"),
                    },
                }
                for tc in tool_calls
            ]

        # Extract usage
        usage_dict = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        # Check for content filtering
        finish_reason = choice.get("finish_reason", "unknown")
        safety_stop = finish_reason == "content_filter"

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage_dict,
            model=response_data.get("model", request.model),
            finish_reason=finish_reason,
            request_id=request.request_id,
            provider=self.provider_name,
            latency_ms=latency_ms,
            safety_stop=safety_stop,
        )

    async def health_check(self) -> bool:
        """Check if OpenAI provider is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            client = await self._get_client()
            headers = {"Authorization": f"Bearer {self._config.api_key}"}

            # Make a simple request to check API health
            response = await client.get("/models", headers=headers, timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning(
                "OpenAI health check failed",
                extra={"provider": self.provider_name, "error": str(e)},
            )
            return False
