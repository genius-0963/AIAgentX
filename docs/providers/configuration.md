# Provider Configuration

This document describes how to configure model providers in AIAgentX.

## Environment Variables

The following environment variables can be set to configure provider behavior:

### Provider Settings

- `DEFAULT_PROVIDER`: Default provider to use (default: "fake")
- `DEFAULT_MODEL`: Default model to use (default: "gpt-4o")
- `OPENAI_API_KEY`: API key for OpenAI
- `ANTHROPIC_API_KEY`: API key for Anthropic

### Circuit Breaker Settings

- `CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD`: Failure rate threshold (0.0-1.0, default: 0.5)
- `CIRCUIT_BREAKER_MINIMUM_REQUESTS`: Minimum requests before considering failure rate (default: 10)
- `CIRCUIT_BREAKER_OPEN_TIMEOUT_SECONDS`: How long to stay open before recovery (default: 60)
- `CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS`: Test calls in half-open state (default: 3)

### Retry Settings

- `PROVIDER_MAX_RETRIES`: Maximum retry attempts (default: 2)
- `PROVIDER_INITIAL_BACKOFF_MS`: Initial backoff in milliseconds (default: 1000)
- `PROVIDER_MAX_BACKOFF_MS`: Maximum backoff in milliseconds (default: 10000)
- `PROVIDER_BACKOFF_MULTIPLIER`: Backoff multiplier (default: 2.0)
- `PROVIDER_RETRY_JITTER`: Enable jitter in backoff (default: true)

### Timeout Settings

- `PROVIDER_TIMEOUT_SECONDS`: Request timeout in seconds (default: 45)
- `PROVIDER_CONNECT_TIMEOUT_SECONDS`: Connection timeout in seconds (default: 3)

### Fallback Settings

- `FALLBACK_ENABLED`: Enable fallback mechanism (default: false)
- `FALLBACK_PROVIDERS`: Comma-separated list of fallback providers
- `FALLBACK_MAX_ATTEMPTS`: Maximum fallback attempts (default: 2)

### Pricing Settings

- `PRICING_OPENAI_GPT4O_PROMPT_PRICE`: Price per 1M prompt tokens for GPT-4o (default: 2.50)
- `PRICING_OPENAI_GPT4O_COMPLETION_PRICE`: Price per 1M completion tokens for GPT-4o (default: 10.00)
- `PRICING_ANTHROPIC_CLAUDE3_OPUS_PROMPT_PRICE`: Price per 1M prompt tokens for Claude 3 Opus (default: 15.00)
- `PRICING_ANTHROPIC_CLAUDE3_OPUS_COMPLETION_PRICE`: Price per 1M completion tokens for Claude 3 Opus (default: 75.00)

## Example Configuration

```bash
# Provider selection
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o

# API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD=0.5
CIRCUIT_BREAKER_MINIMUM_REQUESTS=10
CIRCUIT_BREAKER_OPEN_TIMEOUT_SECONDS=60

# Retry
PROVIDER_MAX_RETRIES=2
PROVIDER_INITIAL_BACKOFF_MS=1000
PROVIDER_MAX_BACKOFF_MS=10000

# Fallback
FALLBACK_ENABLED=true
FALLBACK_PROVIDERS=anthropic
FALLBACK_MAX_ATTEMPTS=2

# Timeouts
PROVIDER_TIMEOUT_SECONDS=45
PROVIDER_CONNECT_TIMEOUT_SECONDS=3
```

## Provider Selection

Providers are selected based on the agent version's `model_policy` configuration:

```python
model_policy = {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4096,
}
```

## Testing with Fake Provider

For testing, use the fake provider which doesn't require API keys:

```bash
DEFAULT_PROVIDER=fake
DEFAULT_MODEL=gpt-4o
```

The fake provider is deterministic and can be configured with custom responses and delays.
