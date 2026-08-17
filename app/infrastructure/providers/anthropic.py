"""Anthropic provider adapter."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.domain.providers.models import ModelRequest, ModelResponse
from app.domain.providers.value_objects import ProviderConfig, RetryPolicy
from app.infrastructure.providers.base import BaseProvider
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic provider adapter implementing ModelProvider protocol."""

    def __init__(self, config: ProviderConfig, retry_policy: RetryPolicy | None = None) -> None:
        super().__init__(config, retry_policy)
        # Set default base URL if not provided
        self._base_url = config.base_url or "https://api.anthropic.com"

    def _get_base_url(self) -> str:
        """Get the base URL for Anthropic API."""
        return self._base_url

    async def _complete_with_retry(self, request: ModelRequest, attempt: int) -> ModelResponse:
        """Execute the actual Anthropic API call.

        Args:
            request: The model request
            attempt: Current retry attempt number

        Returns:
            ModelResponse from Anthropic
        """
        client = await self._get_client()
        normalized_request = self._normalize_request(request)

        headers = {
            "x-api-key": self._config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        self._add_correlation_id(headers, request)

        start_time = time.time()

        response = await client.post(
            "/v1/messages",
            json=normalized_request,
            headers=headers,
        )

        response.raise_for_status()
        response_data = response.json()

        latency_ms = (time.time() - start_time) * 1000

        return self._normalize_response(response_data, request, latency_ms)

    def _normalize_request(self, request: ModelRequest) -> dict[str, Any]:
        """Normalize internal request to Anthropic format.

        Args:
            request: Internal model request

        Returns:
            Anthropic-specific request dictionary
        """
        # Anthropic expects messages in a specific format
        # The first message should be a "user" message with the system prompt
        anthropic_messages = []

        # Extract system prompt if present in first message
        system_prompt = None
        if request.messages and request.messages[0].get("role") == "system":
            system_prompt = request.messages[0].get("content")
            anthropic_messages = request.messages[1:]
        else:
            anthropic_messages = request.messages

        anthropic_request = {
            "model": request.model,
            "messages": anthropic_messages,
            "max_tokens": request.max_tokens or 4096,
        }

        if system_prompt:
            anthropic_request["system"] = system_prompt

        if request.temperature is not None:
            anthropic_request["temperature"] = request.temperature

        if request.tools:
            # Convert tool format to Anthropic's tools format
            anthropic_request["tools"] = self._normalize_tools(request.tools)

        return anthropic_request

    def _normalize_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize tools to Anthropic format.

        Args:
            tools: Internal tool format

        Returns:
            Anthropic tool format
        """
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                function = tool.get("function", {})
                anthropic_tools.append(
                    {
                        "name": function.get("name"),
                        "description": function.get("description", ""),
                        "input_schema": function.get("parameters", {}),
                    }
                )
        return anthropic_tools

    def _normalize_response(
        self, response_data: dict[str, Any], request: ModelRequest, latency_ms: float
    ) -> ModelResponse:
        """Normalize Anthropic response to internal format.

        Args:
            response_data: Anthropic response JSON
            request: Original request for context
            latency_ms: Request latency in milliseconds

        Returns:
            Internal ModelResponse
        """
        # Extract content
        content = None
        tool_calls = None

        # Anthropic returns content as a list of blocks
        content_blocks = response_data.get("content", [])
        text_blocks = [block for block in content_blocks if block.get("type") == "text"]
        tool_use_blocks = [block for block in content_blocks if block.get("type") == "tool_use"]

        if text_blocks:
            content = text_blocks[0].get("text")

        if tool_use_blocks:
            # Normalize tool calls to internal format
            tool_calls = [
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": block.get("input", {}),
                    },
                }
                for block in tool_use_blocks
            ]

        # Extract usage
        usage = response_data.get("usage", {})
        usage_dict = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }

        # Get stop reason
        stop_reason = response_data.get("stop_reason", "end_turn")
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
        }
        finish_reason = finish_reason_map.get(stop_reason, stop_reason)

        # Check for content filtering
        safety_stop = stop_reason == "content_filter"

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
        """Check if Anthropic provider is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            client = await self._get_client()
            headers = {
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
            }

            # Make a simple request to check API health
            response = await client.get("/v1/messages", headers=headers, timeout=5.0)
            # Anthropic returns 405 Method Not Allowed for GET on messages endpoint, which is expected
            return response.status_code in {200, 405}
        except Exception as e:
            logger.warning(
                "Anthropic health check failed",
                extra={"provider": self.provider_name, "error": str(e)},
            )
            return False
