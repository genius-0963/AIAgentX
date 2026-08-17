# Testing with Fake Provider

This document describes how to use the fake provider for testing.

## Overview

The fake provider is a deterministic implementation of the `ModelProvider` protocol designed for testing. It allows you to:

- Test without external API calls
- Configure custom responses
- Simulate delays and errors
- Ensure reproducible test results

## Basic Usage

```python
from app.infrastructure.providers.fake import FakeProvider
from app.domain.providers.value_objects import ProviderConfig
from app.domain.providers.models import ModelRequest

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
```

## Configuration Options

### Default Response

Set a default response for all requests:

```python
provider = FakeProvider(config, default_response="Custom response")
```

### Request-Specific Responses

Configure different responses for specific request IDs:

```python
provider.set_response(
    "specific-id",
    {
        "content": "Specific response",
        "tokens": {"prompt_tokens": 50, "completion_tokens": 100},
    },
)
```

### Delay Simulation

Add delays to simulate network latency:

```python
provider = FakeProvider(config, default_delay_ms=100)  # 100ms delay
```

### Error Simulation

Simulate various error types:

```python
provider = FakeProvider(
    config,
    simulate_errors=True,
    error_type="timeout",  # or "rate_limit", "auth_error", "server_error", "validation_error"
)
```

## Deterministic Behavior

The fake provider ensures deterministic behavior:

```python
# Same request always returns same response
response1 = await provider.complete(request)
response2 = await provider.complete(request)

assert response1.content == response2.content
assert response1.usage == response2.usage
```

## Call Counting

Track the number of calls made:

```python
assert provider.get_call_count() == 0
await provider.complete(request)
assert provider.get_call_count() == 1

provider.reset_call_count()
assert provider.get_call_count() == 0
```

## Health Check

The fake provider always returns healthy:

```python
health = await provider.health_check()
assert health is True
```

## Testing Scenarios

### Test Retry Logic

```python
provider = FakeProvider(config, simulate_errors=True, error_type="timeout")

# Configure retry policy
retry_policy = RetryPolicy(max_retries=3)

# Should retry and eventually succeed or fail based on configuration
```

### Test Circuit Breaker

```python
provider = FakeProvider(config, simulate_errors=True, error_type="server_error")

# Configure circuit breaker
circuit_config = CircuitBreakerConfig(
    failure_rate_threshold=0.5,
    minimum_requests=5,
)

# Circuit should trip after failures
```

### Test Cost Calculation

```python
provider.set_response(
    "test-id",
    {
        "content": "Test",
        "tokens": {"prompt_tokens": 1000, "completion_tokens": 500},
    },
)

# Cost will be calculated based on token counts
```

## Best Practices

1. **Use Fake Provider for Unit Tests**: Avoid external dependencies
2. **Configure Deterministic Responses**: Ensure reproducible tests
3. **Test Error Scenarios**: Use error simulation for resilience testing
4. **Reset State Between Tests**: Use `reset_call_count()` to clean up
5. **Validate Behavior**: Ensure fake provider behaves like real providers

## Integration Tests

For integration tests that need to verify the full stack:

```python
# Use fake provider in integration tests
provider_service = ProviderService(
    registry=registry,
    health_monitor=health_monitor,
    cost_service=cost_service,
)

# Register fake provider
provider_service.register_provider(fake_provider, config)

# Test full flow
response = await provider_service.complete(request)
```
