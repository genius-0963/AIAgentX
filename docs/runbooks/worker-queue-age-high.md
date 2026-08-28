# Runbook: Worker Queue Age High

## Overview
**Alert:** `QueueAgeHigh`
**Severity:** Warning
**Component:** Worker

Triggered when the oldest queued run exceeds 60 seconds for more than 2 minutes.

## Impact
- Delayed run execution
- Poor user experience
- Potential timeout of queued runs

## Diagnosis

### 1. Check Queue Metrics
```bash
# Check queue age
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=worker_queue_age_seconds'

# Check active runs
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=worker_active_runs'
```

### 2. Check Worker Status
```bash
# Check worker pods
kubectl get pods -n aiagentx -l app.kubernetes.io/component=worker

# Check worker logs
kubectl logs -n aiagentx -l app.kubernetes.io/component=worker --tail=100

# Check lease conflicts
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=rate(worker_lease_conflicts_total[5m])'
```

### 3. Check Run Queue
```bash
# Check queued runs in database
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT id, status, created_at, agent_version_id
FROM runs
WHERE status = 'queued'
ORDER BY created_at ASC
LIMIT 20;"
```

## Common Causes & Resolution

### Cause 1: Insufficient Workers
**Resolution:**
```bash
# Check current worker count
kubectl get deployment aiagentx-worker -n aiagentx

# Scale up workers
kubectl scale deployment aiagentx-worker -n aiagentx --replicas=5

# Check HPA status
kubectl get hpa aiagentx-worker-hpa -n aiagentx
```

### Cause 2: Long-Running Runs Blocking Workers
**Resolution:**
```bash
# Check for stuck runs
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT id, status, started_at, agent_version_id
FROM runs
WHERE status = 'running'
AND started_at < now() - interval '10 minutes';"

# Cancel stuck runs if needed
kubectl exec -it postgres -- psql -U aiagentx -c "
UPDATE runs SET status = 'cancelled', completed_at = now()
WHERE status = 'running'
AND started_at < now() - interval '30 minutes';"
```

### Cause 3: High Lease Conflicts
**Resolution:**
```bash
# Check lease conflict rate
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=rate(worker_lease_conflicts_total[5m])'

# Reduce worker count to reduce contention
kubectl scale deployment aiagentx-worker -n aiagentx --replicas=3

# Check worker polling interval
# (Adjust in worker configuration if needed)
```

### Cause 4: Provider Latency Slowing Runs
**Resolution:**
```bash
# Check provider latency
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(provider_request_duration_seconds_bucket[5m])) by (le, provider))'

# If provider slow, check their status page
# Consider enabling fallback
```

### Cause 5: Resource Limits Too Low
**Resolution:**
```bash
# Check worker resource usage
kubectl top pods -n aiagentx -l app.kubernetes.io/component=worker

# Increase limits
kubectl patch deployment aiagentx-worker -n aiagentx -p '{"spec":{"template":{"spec":{"containers":[{"name":"worker","resources":{"limits":{"cpu":"8000m","memory":"8Gi"}}}]}}}}'
```

## Verification
```bash
# Monitor queue age
watch -n 30 'curl -s "http://prometheus:9090/api/v1/query?query=worker_queue_age_seconds{state=%22queued%22}" | jq .data.result[0].value[1]'
```

## Escalation
- If queue age > 300s: Escalate to Worker Team Lead
- If workers consistently at capacity: Request capacity increase

## Related Dashboards
- [Worker & Queue](http://grafana.aiagentx.io/d/aiagentx-worker-queue)

## Related Runbooks
- [High Lease Conflicts](./worker-lease-conflicts.md)
- [Worker Down](./worker-down.md)
- [No Active Workers](./no-active-workers.md)