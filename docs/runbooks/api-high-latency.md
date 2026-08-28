# Runbook: High API Latency

## Overview
**Alert:** `HighLatency`
**Severity:** Warning
**Component:** API

Triggered when API P95 latency exceeds 5 seconds over a 5-minute window.

## Impact
- Degraded user experience
- Potential timeout cascades
- SLA breach risk for latency-sensitive operations

## Diagnosis

### 1. Check Current Latency
```bash
# Query P95 latency
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le))'
```

### 2. Identify Slow Endpoints
```bash
# Check latency by endpoint
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le, endpoint))'
```

### 3. Check Resource Utilization
```bash
# CPU/Memory usage
kubectl top pods -n aiagentx -l app.kubernetes.io/component=api

# Check for CPU throttling
kubectl exec -it <api-pod> -- cat /sys/fs/cgroup/cpu/cpu.stat | grep throttled
```

### 4. Check Dependency Latencies
```bash
# Database query latency
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(db_query_duration_seconds_bucket[5m])) by (le))'

# Redis command latency
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(redis_command_duration_seconds_bucket[5m])) by (le))'

# Provider latency
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(provider_request_duration_seconds_bucket[5m])) by (le, provider))'
```

## Common Causes & Resolution

### Cause 1: Database Slow Queries
**Resolution:**
```bash
# Check for long-running queries
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
AND state = 'active';"

# Check missing indexes
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT schemaname, tablename, seq_scan, idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan
ORDER BY seq_scan DESC LIMIT 20;"
```

### Cause 2: Provider API Latency
**Resolution:**
```bash
# Check provider latency
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(provider_request_duration_seconds_bucket[5m])) by (le, provider))'

# If specific provider slow, check their status page
# Consider enabling fallback if configured
```

### Cause 3: Resource Contention
**Resolution:**
```bash
# Check for CPU throttling
kubectl exec -it <api-pod> -- cat /sys/fs/cgroup/cpu/cpu.stat

# Increase CPU limits
kubectl patch deployment aiagentx-api -n aiagentx -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"cpu":"4000m"}}}]}}}}'

# Check memory pressure
kubectl exec -it <api-pod> -- cat /proc/meminfo
```

### Cause 4: Connection Pool Exhaustion
**Resolution:**
```bash
# Check pool usage
curl -s localhost:9090/metrics | grep db_pool_connections

# Increase pool size in configmap
kubectl patch configmap aiagentx-config -n aiagentx -p '{"data":{"DB_POOL_SIZE":"20","DB_MAX_OVERFLOW":"40"}}'

# Restart pods to pick up new config
kubectl rollout restart deployment/aiagentx-api -n aiagentx
```

## Verification
Monitor latency for 15 minutes after fix:
```bash
watch -n 30 'curl -s "http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le))" | jq .data.result[0].value[1]'
```

## Escalation
- If latency > 10s for 10 minutes: Escalate to API Team Lead
- If latency affects specific endpoint only: Engage feature team
- If database is bottleneck: Engage Database Team

## Related Dashboards
- [API Performance](http://grafana.aiagentx.io/d/aiagentx-api-performance)
- [Database Performance](http://grafana.aiagentx.io/d/aiagentx-db-performance)

## Related Runbooks
- [High API Error Rate](./api-high-error-rate.md)
- [Database Pool Exhausted](./db-pool-exhausted.md)
- [Database High Latency](./db-high-latency.md)