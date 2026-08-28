# Runbook: Database Pool Exhausted

## Overview
**Alert:** `DatabasePoolExhausted`
**Severity:** Critical
**Component:** Database

Triggered when database connection pool usage exceeds 90% for more than 5 minutes.

## Impact
- New database connections fail
- API requests timeout waiting for connections
- Complete service degradation

## Diagnosis

### 1. Check Pool Usage
```bash
# Check pool metrics
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=db_pool_connections_active / db_pool_connections_total * 100'

# Check active connections
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=db_pool_connections_active'
```

### 2. Check Active Connections
```bash
# Check PostgreSQL connections
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT pid, usename, application_name, client_addr, state, query_start, state_change, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start;"

# Check connection count
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT count(*) as total_connections,
       count(*) FILTER (WHERE state = 'active') as active,
       count(*) FILTER (WHERE state = 'idle') as idle,
       count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_tx
FROM pg_stat_activity;"
```

### 3. Check for Long-Running Queries
```bash
# Find long-running queries
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, state, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '30 seconds'
AND state = 'active';"

# Check for idle in transaction
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT pid, now() - pg_stat_activity.state_change AS duration, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
AND now() - pg_stat_activity.state_change > interval '60 seconds';"
```

## Common Causes & Resolution

### Cause 1: Connection Leak in Application
**Resolution:**
```bash
# Check for connections not returned to pool
# Look for "idle in transaction" connections

# Terminate idle in transaction connections
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
AND now() - state_change > interval '5 minutes';"

# Restart API to reset pools
kubectl rollout restart deployment/aiagentx-api -n aiagentx
```

### Cause 2: Pool Size Too Small
**Resolution:**
```bash
# Increase pool size
kubectl patch configmap aiagentx-config -n aiagentx -p '{"data":{"DB_POOL_SIZE":"30","DB_MAX_OVERFLOW":"60"}}'

# Restart API to pick up new config
kubectl rollout restart deployment/aiagentx-api -n aiagentx

# Verify new pool size
curl -s localhost:9090/metrics | grep db_pool_connections_total
```

### Cause 3: Long-Running Queries Blocking Connections
**Resolution:**
```bash
# Identify and kill long-running queries
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT pg_cancel_backend(pid)
FROM pg_stat_activity
WHERE (now() - query_start) > interval '2 minutes'
AND state = 'active'
AND query NOT LIKE '%pg_stat_activity%';"

# Check for missing indexes
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT schemaname, tablename, seq_scan, idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan
ORDER BY seq_scan DESC LIMIT 20;"
```

### Cause 4: Too Many API Replicas
**Resolution:**
```bash
# Check current replica count
kubectl get deployment aiagentx-api -n aiagentx

# Reduce replicas if pool can't support
kubectl scale deployment aiagentx-api -n aiagentx --replicas=3

# Or increase pool size instead
```

### Cause 5: Worker Connections Also Using Pool
**Resolution:**
```bash
# Check worker pool usage
# Workers may have their own pools or share

# Check total connections from all sources
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT application_name, count(*)
FROM pg_stat_activity
GROUP BY application_name;"

# Ensure workers use separate pool or connection limiter
```

## Verification
```bash
# Monitor pool usage
watch -n 10 'curl -s "http://prometheus:9090/api/v1/query?query=db_pool_connections_active%20/%20db_pool_connections_total%20*%20100" | jq .data.result[0].value[1]'
```

## Escalation
- If pool exhausted > 10 minutes: Page Database Team
- If caused by query performance: Engage Database Team for optimization
- If recurrent: Consider connection pooling middleware (PgBouncer)

## Related Dashboards
- [Database Performance](http://grafana.aiagentx.io/d/aiagentx-db-performance)

## Related Runbooks
- [Database High Latency](./db-high-latency.md)
- [Database Query Errors](./db-query-errors.md)