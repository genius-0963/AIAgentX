# Fallback Mechanism

This document describes the fallback mechanism in AIAgentX.

## Overview

The fallback mechanism provides high availability by automatically switching to alternative providers when the primary provider fails. This ensures system resilience during provider outages.

## Fallback Triggers

Fallback is triggered when:

1. **Circuit Breaker Open**: Primary provider circuit is tripped
2. **Timeout**: Request to primary provider times out
3. **Rate Limit**: Primary provider rate limit is exceeded
4. **Server Error**: Primary provider returns 5xx error

## Safety Checks

Fallback only occurs when:

- **No Irreversible Effects**: Fallback before tool calls that modify state
- **Provider Compatibility**: Fallback provider has same data residency and capability
- **Idempotency**: Operation can be safely retried
- **Fallback Available**: Valid fallback provider exists

## Configuration

```python
from app.domain.providers.value_objects import FallbackConfig

config = FallbackConfig(
    primary_provider="openai",
    fallback_providers=["anthropic"],
    require_same_data_residency=True,
    require_same_capability_class=True,
    max_fallback_attempts=2,
)
```

## Environment Variables

- `FALLBACK_ENABLED`: Enable fallback (default: false)
- `FALLBACK_PROVIDERS`: Comma-separated fallback providers
- `FALLBACK_MAX_ATTEMPTS`: Maximum fallback attempts (default: 2)

## Usage

```python
from app.application.services.fallback_service import FallbackService

fallback_service = FallbackService(
    registry=registry,
    config=config,
)

# Execute with fallback
response = await fallback_service.execute_with_fallback(
    request=request,
    primary_provider_name="openai",
    error_type="timeout",
    circuit_state="closed",
    irreversible_effects_executed=False,
)
```

## Compatibility Validation

Fallback providers are validated for:

- **Data Residency**: Same geographic region requirements
- **Capability Class**: Similar model capabilities
- **Feature Parity**: Tool support, streaming, etc.

## Fallback Decision Logic

```python
# Check if fallback should occur
decision = fallback_service.should_fallback(
    primary_provider="openai",
    error_type="timeout",
    circuit_state="closed",
    irreversible_effects_executed=False,
)

if decision.should_fallback:
    # Execute fallback
    response = await fallback_service.execute_with_fallback(...)
```

## Metrics

The fallback service tracks:

- `total_fallback_attempts`: Total fallback attempts
- `successful_fallbacks`: Successful fallbacks
- `failed_fallbacks`: Failed fallbacks
- `by_reason`: Breakdown by trigger reason
- `by_provider`: Breakdown by primary provider

## Best Practices

1. **Configure Carefully**: Only enable fallback when providers are compatible
2. **Monitor Fallbacks**: Track fallback rate and success rate
3. **Test Scenarios**: Verify fallback behavior with provider failures
4. **Set Limits**: Use `max_fallback_attempts` to prevent cascading
5. **Log Events**: Record fallback events for debugging

## Safety Considerations

- **Before Irreversible Effects**: Only fallback before state changes
- **Data Residency**: Ensure fallback provider meets compliance requirements
- **Capability Matching**: Verify fallback provider has required features
- **Cost Awareness**: Fallback providers may have different pricing

## Integration with Provider Service

The provider service integrates fallback automatically:

```python
provider_service = ProviderService(
    registry=registry,
    health_monitor=health_monitor,
    cost_service=cost_service,
    fallback_config=config,
)

# Fallback is automatically enabled when enable_fallback=True
response = await provider_service.complete(
    request,
    enable_fallback=True,
)
```

## Monitoring

Monitor fallback activity:

```python
metrics = fallback_service.get_fallback_metrics()
# Returns:
# {
#     "total_fallback_attempts": 10,
#     "successful_fallbacks": 8,
#     "failed_fallbacks": 2,
#     "by_reason": {...},
#     "by_provider": {...}
# }
```

## Troubleshooting

### Fallback Not Triggering

- Check `FALLBACK_ENABLED` is true
- Verify fallback providers are configured
- Ensure error type is fallbackable
- Check circuit breaker state

### Fallback Failing

- Verify fallback provider compatibility
- Check fallback provider API keys
- Ensure fallback provider is healthy
- Review fallback logs for errors

### High Fallback Rate

- Indicates primary provider issues
- Review primary provider health
- Check primary provider configuration
- Consider adjusting fallback thresholds
