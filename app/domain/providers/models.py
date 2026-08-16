"""Model request and response dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, kw_only=True)
class ModelRequest:
    """Internal model request representation.

    This is the unified request format that gets normalized to provider-specific
    formats by each adapter.
    """

    messages: list[dict[str, Any]]
    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    request_id: str
    tenant_id_hash: str
    timeout_seconds: int = 45
    trace_context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("Messages cannot be empty")
        if not self.model:
            raise ValueError("Model cannot be empty")
        if not self.request_id:
            raise ValueError("Request ID cannot be empty")
        if not self.tenant_id_hash:
            raise ValueError("Tenant ID hash cannot be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if self.temperature is not None and (self.temperature < 0 or self.temperature > 2):
            raise ValueError("Temperature must be between 0 and 2")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive")


@dataclass(slots=True, kw_only=True)
class ModelResponse:
    """Internal model response representation.

    This is the unified response format that provider-specific responses
    get normalized to by each adapter.
    """

    content: str | None
    tool_calls: list[dict[str, Any]] | None
    usage: dict[str, int]  # {prompt_tokens, completion_tokens, total_tokens}
    model: str
    finish_reason: str
    request_id: str
    provider: str
    latency_ms: float
    safety_stop: bool = False

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("Model cannot be empty")
        if not self.request_id:
            raise ValueError("Request ID cannot be empty")
        if not self.provider:
            raise ValueError("Provider cannot be empty")
        if not self.finish_reason:
            raise ValueError("Finish reason cannot be empty")
        if self.latency_ms < 0:
            raise ValueError("Latency cannot be negative")
        # Validate usage dict has required keys
        required_keys = {"prompt_tokens", "completion_tokens", "total_tokens"}
        if not required_keys.issubset(self.usage.keys()):
            raise ValueError(f"Usage must contain {required_keys}")
        # Validate token counts are non-negative
        for key, value in self.usage.items():
            if value < 0:
                raise ValueError(f"{key} cannot be negative")


@dataclass(slots=True, kw_only=True)
class ProviderError:
    """Provider error classification.

    This class normalizes provider-specific errors into a consistent format
    for error handling and retry logic.
    """

    is_retryable: bool
    error_type: str  # timeout, rate_limit, server_error, auth_error, validation_error, etc.
    original_error: Exception
    provider: str
    message: str = ""

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("Provider cannot be empty")
        if not self.error_type:
            raise ValueError("Error type cannot be empty")
        valid_error_types = {
            "timeout",
            "rate_limit",
            "server_error",
            "auth_error",
            "validation_error",
            "unknown",
        }
        if self.error_type not in valid_error_types:
            raise ValueError(f"Invalid error type: {self.error_type}")

    def __str__(self) -> str:
        msg = self.message or str(self.original_error)
        return f"[{self.provider}] {self.error_type}: {msg}"
