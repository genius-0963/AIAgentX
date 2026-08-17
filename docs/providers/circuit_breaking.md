# Circuit Breaking

This document describes the circuit breaker implementation in AIAgentX.

## Overview

The circuit breaker pattern prevents cascade failures by temporarily stopping requests to a failing provider. This improves system resilience and prevents overwhelming a struggling service.

## Circuit States

### Closed (Normal Operation)

- Requests pass through normally
- Success/failure rates are tracked
- Circuit trips if failure rate exceeds threshold

### Open (Circuit Tripped)

- Requests fail immediately without calling the provider
- No actual provider calls are made
- Waits for timeout period before attempting recovery

### Half-Open (Testing Recovery)

- Limited test requests are allowed
- Success leads to closing the circuit
- Failure leads back to open state

## Configuration

```python
from app.domain.providers.value_objects import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_rate_threshold=0.5,      # Trip at 50% failure rate
    minimum_requests=10,              # Need 10 requests before tripping
    open_timeout_seconds=60,          # Stay open for 60 seconds
    half_open_max_calls=3,            # Allow 3 test calls in half-open
)
```

## Environment Variables

- `CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD`: Failure rate threshold (default: 0.5)
- `CIRCUIT_BREAKER_MINIMUM_REQUESTS`: Minimum requests (default: 10)
- `CIRCUIT_BREAKER_OPEN_TIMEOUT_SECONDS`: Open timeout (default: 60)
- `CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS`: Half-open calls (default: 3)

## Usage

```python
from app.infrastructure.providers.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(config=config, provider_name="openai")

# Check if requests can execute
if breaker.can_execute():
    try:
        response = await provider.complete(request)
        breaker.record_success()
    except Exception:
        breaker.record_failure()
```

## Metrics

The circuit breaker tracks:

- `total_requests`: Total number of requests
- `successful_requests`: Number of successful requests
- `failed_requests`: Number of failed requests
- `failure_rate`: Current failure rate
- `consecutive_failures`: Consecutive failure count
- `consecutive_successes`: Consecutive success count
- `last_failure_time`: Timestamp of last failure
- `last_success_time`: Timestamp of last success

## Monitoring

Check circuit breaker status:

```python
status = breaker.get_status()
# Returns:
# {
#     "provider": "openai",
#     "state": "closed",
#     "can_execute": true,
#     "metrics": {...},
#     "config": {...}
# }
```

## Reset

Manually reset a circuit breaker:

```python
breaker.reset()
```

## Best Practices

1. **Tune Thresholds**: Adjust based on production metrics
2. **Monitor State Changes**: Log circuit state transitions
3. **Set Appropriate Timeouts**: Balance recovery speed and stability
4. **Test Scenarios**: Verify circuit behavior with fault injection
5. **Combine with Fallback**: Use fallback for high availability

## API Endpoints

Monitor circuit breakers via health endpoints:

- `/healthz/providers` - Overall provider status
- `/healthz/providers/{provider_name}` - Individual provider status

## Integration with Provider Service

The provider service automatically manages circuit breakers:

```python
provider_service = ProviderService(...)
provider_service.register_provider(
    provider,
    config,
    circuit_breaker_config=config,
)
```
