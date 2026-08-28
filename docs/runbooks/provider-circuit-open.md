# Runbook: Provider Circuit Breaker Open

## Overview
**Alert:** `ProviderCircuitBreakerOpen`
**Severity:** Critical
**Component:** Provider

Triggered when a provider's circuit breaker enters the OPEN state, preventing requests to that provider.

## Impact
- Requests to the affected provider will fail fast
- Fallback providers will be used if configured
- Potential service degradation if no fallback

## Diagnosis

### 1. Check Circuit Breaker Status
```bash
# Check circuit breaker state
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=provider_circuit_state'

# Check provider error rate
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(provider_errors_total[5m])) by (provider) / sum(rate(provider_requests_total[5m])) by (provider)'
```

### 2. Check Provider Health Endpoint
```bash
# Check provider health via API
curl -s http://api.aiagentx.io/v1/providers/<provider_name> | jq .

# Or check directly
kubectl exec -it <api-pod> -- curl -s http://localhost:8000/v1/providers/<provider_name> | jq .
```

### 3. Check Recent Errors
```bash
# Check error types
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(provider_errors_total[5m])) by (provider, error_type)'

# Check API logs
kubectl logs -n aiagentx -l app.kubernetes.io/component=api --since=10m | jq 'select(.provider=="<provider_name>" and .level=="error")'
```

## Common Causes & Resolution

### Cause 1: Provider API Outage
**Resolution:**
```bash
# Check provider status page
# Common providers:
# - OpenAI: https://status.openai.com
# - Anthropic: https://status.anthropic.com

# If outage confirmed, wait for resolution
# Circuit breaker will auto-recover after configured timeout (default 60s)
```

### Cause 2: Authentication Failure
**Resolution:**
```bash
# Check API key validity
kubectl exec -it <api-pod> -- curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# Update API key in secret
kubectl patch secret aiagentx-secrets -n aiagentx -p '{"stringData":{"OPENAI_API_KEY":"new-key"}}'

# Restart API to pick up new key
kubectl rollout restart deployment/aiagentx-api -n aiagentx
```

### Cause 3: Rate Limiting
**Resolution:**
```bash
# Check for rate limit errors
kubectl logs -n aiagentx -l app.kubernetes.io/component=api --since=10m | jq 'select(.error_type=="rate_limit")'

# Reduce request rate
# Adjust provider retry/backoff config
kubectl patch configmap aiagentx-config -n aiagentx -p '{"data":{"PROVIDER_MAX_RETRIES":"3","PROVIDER_INITIAL_BACKOFF_MS":"2000"}}'

# Enable fallback if configured
```

### Cause 4: Network Issues
**Resolution:**
```bash
# Test connectivity from API pod
kubectl exec -it <api-pod> -- curl -v --max-time 10 https://api.openai.com/v1/models

# Check DNS resolution
kubectl exec -it <api-pod> -- nslookup api.openai.com

# Check network policies
kubectl get networkpolicies -n aiagentx
```

### Cause 5: Circuit Breaker Configuration Too Aggressive
**Resolution:**
```bash
# Check current config
kubectl get configmap aiagentx-config -n aiagentx -o yaml | grep -A 5 CIRCUIT_BREAKER

# Adjust thresholds
kubectl patch configmap aiagentx-config -n aiagentx -p '{"data":{"CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD":"0.7","CIRCUIT_BREAKER_MINIMUM_REQUESTS":"20"}}'

# Restart API
kubectl rollout restart deployment/aiagentx-api -n aiagentx
```

## Manual Circuit Breaker Reset
```bash
# If auto-recovery not working, restart API pods
kubectl rollout restart deployment/aiagentx-api -n aiagentx

# Or scale to 0 and back
kubectl scale deployment aiagentx-api -n aiagentx --replicas=0
kubectl scale deployment aiagentx-api -n aiagentx --replicas=3
```

## Verification
```bash
# Monitor circuit breaker state
watch -n 10 'curl -s "http://prometheus:9090/api/v1/query?query=provider_circuit_state" | jq .data.result'

# Check provider health endpoint
curl -s http://api.aiagentx.io/v1/providers/<provider_name> | jq .circuit_breaker
```

## Escalation
- If provider outage > 30 minutes: Engage Provider Relations
- If authentication issue: Engage Security Team for key rotation
- If persistent: Consider removing provider temporarily

## Related Dashboards
- [Provider Health](http://grafana.aiagentx.io/d/aiagentx-provider-health)

## Related Runbooks
- [Provider High Error Rate](./provider-high-error-rate.md)
- [Provider High Latency](./provider-high-latency.md)
- [Provider Fallback Activations](./provider-fallback.md)