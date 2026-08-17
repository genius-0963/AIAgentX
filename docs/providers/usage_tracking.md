# Usage Tracking

This document describes how usage tracking works in AIAgentX.

## Overview

AIAgentX tracks token usage and costs for each provider call at the step level. This enables:

- Accurate cost calculation per run
- Usage reporting and analytics
- Budget enforcement
- Provider performance monitoring

## Data Model

### Usage Records

Usage is tracked per run step with the following information:

- `provider`: Provider name (e.g., "openai")
- `model`: Model name (e.g., "gpt-4o")
- `prompt_tokens`: Number of tokens in the prompt
- `completion_tokens`: Number of tokens in the completion
- `total_tokens`: Total tokens used
- `cost_microunits`: Cost in micro-units (1/1,000,000 USD)
- `timestamp`: Unix timestamp of the request
- `request_id`: Unique request identifier

### Database Schema

Usage tracking is implemented through:

1. **Run Steps Table**: Extended with usage columns
   - `prompt_tokens`: INTEGER
   - `completion_tokens`: INTEGER
   - `total_tokens`: INTEGER
   - `cost_microunits`: BIGINT
   - `provider`: TEXT
   - `model`: TEXT

2. **Usage Summaries Table**: Aggregated usage data
   - `tenant_id`: Tenant identifier
   - `run_id`: Run identifier
   - `provider`: Provider name
   - `model`: Model name
   - `total_prompt_tokens`: Aggregate prompt tokens
   - `total_completion_tokens`: Aggregate completion tokens
   - `total_tokens`: Total tokens
   - `total_cost_microunits`: Total cost
   - `request_count`: Number of requests
   - `period_start`: Period start time
   - `period_end`: Period end time

## Cost Calculation

Costs are calculated based on provider-specific pricing:

```python
from app.application.services.cost_service import CostService

pricing_config = {
    "openai:gpt-4o": {
        "prompt_price_usd_per_1m": 2.50,
        "completion_price_usd_per_1m": 10.00,
    },
}

cost_service = CostService(pricing_config)
cost = cost_service.calculate_cost("openai", "gpt-4o", 1000, 500)
```

## Usage Recording

Usage is automatically recorded when provider calls are made:

```python
from app.application.services.provider_service import ProviderService

response = await provider_service.complete(request)
# Usage is automatically extracted from response and recorded
```

## Usage Reporting

Get usage statistics for a tenant:

```python
from app.domain.repositories.usage import UsageRepository

usage = await usage_repository.get_aggregated_usage(
    tenant_id=tenant_id,
    provider="openai",
    start_timestamp=start_time,
    end_timestamp=end_time,
)
```

## Budget Enforcement

Runs have maximum cost limits that are enforced:

```python
run = Run(
    tenant_id=tenant_id,
    agent_version_id=agent_version_id,
    max_cost=Money(10_000_000),  # $10 default
    ...
)

# Cost is checked before each provider call
if run.spent_cost + new_cost > run.max_cost:
    raise ValueError("Run would exceed max cost")
```

## Monitoring

Monitor usage through:

1. **Health Endpoints**: `/healthz/providers` for provider status
2. **Run Status**: Includes usage breakdown by provider
3. **Usage Repository**: Query usage data for analytics

## Best Practices

1. **Set Appropriate Budgets**: Configure `max_cost` based on expected usage
2. **Monitor Usage**: Regularly check usage reports for anomalies
3. **Update Pricing**: Keep pricing configurations current
4. **Track Costs**: Use cost data for billing and optimization
