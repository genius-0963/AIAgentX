# Runbook: High API Error Rate

## Overview
**Alert:** `HighErrorRate`
**Severity:** Critical
**Component:** API

Triggered when the API 5xx error rate exceeds 5% over a 5-minute window.

## Impact
- Users experiencing failed requests
- Potential data loss or inconsistent state
- SLA breach risk

## Diagnosis

### 1. Check Current Error Rate
```bash
# Query Prometheus for current error rate
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(api_requests_total{status=~"5.."}[5m])) / sum(rate(api_requests_total[5m]))'
```

### 2. Identify Failing Endpoints
```bash
# Check which endpoints are failing
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(api_requests_total{status=~"5.."}[5m])) by (method, endpoint)'
```

### 3. Check Application Logs
```bash
# Get recent API logs
kubectl logs -n aiagentx -l app.kubernetes.io/component=api --tail=100 -f

# Or use structured logging query
kubectl logs -n aiagentx -l app.kubernetes.io/component=api --since=10m | jq 'select(.level=="error")'
```

### 4. Check Dependencies
- Database connectivity: `kubectl exec -it <api-pod> -- pg_isready -h postgres -p 5432`
- Redis connectivity: `kubectl exec -it <api-pod> -- redis-cli -h redis ping`
- Provider APIs: Check provider health endpoints

## Common Causes & Resolution

### Cause 1: Database Connection Issues
**Symptoms:** Connection pool exhausted, query timeouts
**Resolution:**
```bash
# Check DB pool usage
kubectl exec -it <api-pod> -- curl -s localhost:9090/metrics | grep db_pool

# Scale up API replicas temporarily
kubectl scale deployment aiagentx-api -n aiagentx --replicas=5

# Check for long-running queries
kubectl exec -it postgres -- psql -U aiagentx -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
```

### Cause 2: Provider API Failures
**Symptoms:** High error rate from specific provider
**Resolution:**
```bash
# Check provider circuit breaker status
curl -s localhost:9090/metrics | grep provider_circuit_state

# Check provider health endpoint
curl -s http://api.aiagentx.io/v1/providers/openai

# If circuit open, wait for half-open or manually reset
# (Circuit breaker auto-recovers after configured timeout)
```

### Cause 3: Resource Exhaustion
**Symptoms:** OOM kills, CPU throttling
**Resolution:**
```bash
# Check resource usage
kubectl top pods -n aiagentx -l app.kubernetes.io/component=api

# Increase resource limits
kubectl patch deployment aiagentx-api -n aiagentx -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi","cpu":"4000m"}}}]}}}}'
```

### Cause 4: Code Deployment Issue
**Symptoms:** Errors started after recent deploy
**Resolution:**
```bash
# Check recent deployments
kubectl rollout history deployment/aiagentx-api -n aiagentx

# Rollback if needed
kubectl rollout undo deployment/aiagentx-api -n aiagentx
```

## Verification
After fix, verify error rate returns to normal:
```bash
# Monitor error rate for 10 minutes
watch -n 30 'curl -s "http://prometheus:9090/api/v1/query?query=sum(rate(api_requests_total{status=~%225..%22}[5m]))%20/%20sum(rate(api_requests_total[5m]))" | jq .data.result[0].value[1]'
```

## Escalation
- If unresolved after 15 minutes: Escalate to API Team Lead
- If SLA breach imminent: Page on-call engineer
- If data corruption suspected: Engage Database Team immediately

## Related Dashboards
- [System Overview](http://grafana.aiagentx.io/d/aiagentx-overview)
- [API Performance](http://grafana.aiagentx.io/d/aiagentx-api-performance)

## Related Runbooks
- [API High Latency](./api-high-latency.md)
- [API Down](./api-down.md)
- [Database Pool Exhausted](./db-pool-exhausted.md)

## Post-Incident
- Create incident report
- Add action items to prevent recurrence
- Update runbook if new failure mode discovered