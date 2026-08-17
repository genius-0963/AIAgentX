"""Unit tests for fake provider."""

import pytest

from app.domain.providers.models import ModelRequest, ModelResponse
from app.domain.providers.value_objects import ProviderConfig, RetryPolicy
from app.infrastructure.providers.fake import FakeProvider


@pytest.mark.asyncio
async def test_fake_provider_basic():
    """Test basic fake provider functionality."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config)

    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="test-id",
        tenant_id_hash="tenant-hash",
    )

    response = await provider.complete(request)

    assert response.content == "Test response"
    assert response.provider == "fake"
    assert response.model == "gpt-4o"
    assert response.usage["total_tokens"] == 30  # Default: 10 prompt + 20 completion


@pytest.mark.asyncio
async def test_fake_provider_custom_response():
    """Test fake provider with custom response."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config, default_response="Custom response")

    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="test-id",
        tenant_id_hash="tenant-hash",
    )

    response = await provider.complete(request)

    assert response.content == "Custom response"


@pytest.mark.asyncio
async def test_fake_provider_response_by_request_id():
    """Test fake provider with request-specific responses."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config)

    # Set specific response for a request ID
    provider.set_response(
        "specific-id",
        {
            "content": "Specific response",
            "tokens": {"prompt_tokens": 50, "completion_tokens": 100},
        },
    )

    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="specific-id",
        tenant_id_hash="tenant-hash",
    )

    response = await provider.complete(request)

    assert response.content == "Specific response"
    assert response.usage["prompt_tokens"] == 50
    assert response.usage["completion_tokens"] == 100


@pytest.mark.asyncio
async def test_fake_provider_delay():
    """Test fake provider with delay."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config, default_delay_ms=100)

    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="test-id",
        tenant_id_hash="tenant-hash",
    )

    import time

    start = time.time()
    response = await provider.complete(request)
    elapsed = (time.time() - start) * 1000

    assert response.content == "Test response"
    assert elapsed >= 100  # Should have at least 100ms delay


@pytest.mark.asyncio
async def test_fake_provider_error_simulation():
    """Test fake provider error simulation."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config, simulate_errors=True, error_type="timeout")

    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="test-id",
        tenant_id_hash="tenant-hash",
    )

    with pytest.raises(Exception):  # Should raise timeout error
        await provider.complete(request)


@pytest.mark.asyncio
async def test_fake_provider_call_count():
    """Test fake provider call counting."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config)

    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="test-id",
        tenant_id_hash="tenant-hash",
    )

    assert provider.get_call_count() == 0

    await provider.complete(request)
    assert provider.get_call_count() == 1

    await provider.complete(request)
    assert provider.get_call_count() == 2

    provider.reset_call_count()
    assert provider.get_call_count() == 0


@pytest.mark.asyncio
async def test_fake_provider_health_check():
    """Test fake provider health check."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config)

    health = await provider.health_check()
    assert health is True  # Fake provider is always healthy


@pytest.mark.asyncio
async def test_fake_provider_deterministic():
    """Test that fake provider is deterministic."""
    config = ProviderConfig(
        provider="fake",
        model="gpt-4o",
        api_key="fake-key",
    )
    provider = FakeProvider(config)

    request = ModelRequest(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4o",
        request_id="test-id",
        tenant_id_hash="tenant-hash",
    )

    # Make multiple calls with same request
    response1 = await provider.complete(request)
    response2 = await provider.complete(request)

    # Should return identical responses
    assert response1.content == response2.content
    assert response1.usage == response2.usage
    assert response1.latency_ms == response2.latency_ms
