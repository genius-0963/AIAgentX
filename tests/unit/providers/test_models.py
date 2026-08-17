"""Unit tests for provider models."""

import pytest

from app.domain.providers.models import ModelRequest, ModelResponse, ProviderError


def test_model_request_validation():
    """Test ModelRequest validation."""
    # Valid request
    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="test-id",
        tenant_id_hash="tenant-hash",
    )
    assert request.messages == [{"role": "user", "content": "test"}]
    assert request.model == "gpt-4o"

    # Invalid: empty messages
    with pytest.raises(ValueError, match="Messages cannot be empty"):
        ModelRequest(
            messages=[],
            model="gpt-4o",
            request_id="test-id",
            tenant_id_hash="tenant-hash",
        )

    # Invalid: empty model
    with pytest.raises(ValueError, match="Model cannot be empty"):
        ModelRequest(
            messages=[{"role": "user", "content": "test"}],
            model="",
            request_id="test-id",
            tenant_id_hash="tenant-hash",
        )

    # Invalid: timeout <= 0
    with pytest.raises(ValueError, match="Timeout must be positive"):
        ModelRequest(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4o",
            request_id="test-id",
            tenant_id_hash="tenant-hash",
            timeout_seconds=0,
        )


def test_model_response_validation():
    """Test ModelResponse validation."""
    # Valid response
    response = ModelResponse(
        content="Test response",
        tool_calls=None,
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        model="gpt-4o",
        finish_reason="stop",
        request_id="test-id",
        provider="openai",
        latency_ms=100.0,
    )
    assert response.content == "Test response"
    assert response.usage["total_tokens"] == 30

    # Invalid: missing usage keys
    with pytest.raises(ValueError, match="must contain"):
        ModelResponse(
            content="Test response",
            tool_calls=None,
            usage={"prompt_tokens": 10},  # Missing required keys
            model="gpt-4o",
            finish_reason="stop",
            request_id="test-id",
            provider="openai",
            latency_ms=100.0,
        )

    # Invalid: negative latency
    with pytest.raises(ValueError, match="Latency cannot be negative"):
        ModelResponse(
            content="Test response",
            tool_calls=None,
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            model="gpt-4o",
            finish_reason="stop",
            request_id="test-id",
            provider="openai",
            latency_ms=-1.0,
        )


def test_provider_error():
    """Test ProviderError classification."""
    # Valid error
    error = ProviderError(
        is_retryable=True,
        error_type="timeout",
        original_error=Exception("timeout"),
        provider="openai",
        message="Request timed out",
    )
    assert error.is_retryable is True
    assert error.error_type == "timeout"
    assert error.provider == "openai"

    # Invalid: empty provider
    with pytest.raises(ValueError, match="Provider cannot be empty"):
        ProviderError(
            is_retryable=True,
            error_type="timeout",
            original_error=Exception("timeout"),
            provider="",
        )

    # Invalid: invalid error type
    with pytest.raises(ValueError, match="Invalid error type"):
        ProviderError(
            is_retryable=True,
            error_type="invalid_type",
            original_error=Exception("test"),
            provider="openai",
        )

    # Test string representation
    error_str = str(error)
    assert "openai" in error_str
    assert "timeout" in error_str
