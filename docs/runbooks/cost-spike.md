# Runbook: Cost Spike

## Overview
**Alert:** `CostSpike`
**Severity:** Warning
**Component:** Business

Triggered when the cost rate exceeds $10/second (approximately $36,000/hour) for more than 5 minutes.

## Impact
- Unexpected cost increase
- Budget overrun risk
- Potential runaway workload

## Diagnosis

### 1. Check Current Cost Rate
```bash
# Check cost rate
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=rate(cost_usd_total[5m])'

# Check cost by tenant/provider
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(cost_usd_total[5m])) by (tenant_id, provider)'
```

### 2. Check Token Usage
```bash
# Check token usage rate
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(tokens_total[5m])) by (tenant_id, provider, type)'

# Check runs rate
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(runs_total[5m])) by (tenant_id, status)'
```

### 3. Identify High-Cost Tenants
```bash
# Top tenants by cost (last hour)
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=topk(10, sum(increase(cost_usd_total[1h])) by (tenant_id))'
```

## Common Causes & Resolution

### Cause 1: Runaway Agent/Workflow
**Resolution:**
```bash
# Identify tenant with spike
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=topk(5, sum(rate(cost_usd_total[5m])) by (tenant_id))'

# Check tenant's runs
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT id, agent_version_id, status, created_at, spent_cost
FROM runs
WHERE tenant_id = '<tenant_id>'
AND created_at > now() - interval '1 hour'
ORDER BY spent_cost DESC LIMIT 20;"

# Cancel runaway runs
kubectl exec -it postgres -- psql -U aiagentx -c "
UPDATE runs SET status = 'cancelled', completed_at = now()
WHERE tenant_id = '<tenant_id>'
AND status = 'running'
AND created_at > now() - interval '1 hour';"
```

### Cause 2: Inefficient Prompt/Tool Usage
**Resolution:**
```bash
# Check token usage patterns
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(tokens_total[5m])) by (tenant_id, provider, type)'

# Check for specific agents with high usage
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT av.id, av.name, av.tenant_id, SUM(r.spent_cost) as total_cost
FROM runs r
JOIN agent_versions av ON r.agent_version_id = av.id
WHERE r.created_at > now() - interval '1 hour'
GROUP BY av.id, av.name, av.tenant_id
ORDER BY total_cost DESC LIMIT 10;"
```

### Cause 3: Provider Pricing Change
**Resolution:**
```bash
# Check if cost spike correlates with provider
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(cost_usd_total[5m])) by (provider)'

# Check provider pricing config
kubectl get configmap aiagentx-config -n aiagentx -o yaml | grep -i PRICING

# Update pricing if changed
kubectl patch configmap aiagentx-config -n aiagentx -p '{"data":{"PRICING_OPENAI_GPT4O_PROMPT_PRICE":"5.00"}}'

# Restart API
kubectl rollout restart deployment/aiagentx-api -n aiagentx
```

### Cause 4: Loop/Recursion in Agent
**Resolution:**
```bash
# Check for runs with many steps
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT r.id, r.agent_version_id, COUNT(rs.id) as step_count, r.spent_cost
FROM runs r
LEFT JOIN run_steps rs ON r.id = rs.run_id
WHERE r.created_at > now() - interval '1 hour'
GROUP BY r.id, r.agent_version_id, r.spent_cost
HAVING COUNT(rs.id) > 50
ORDER BY step_count DESC LIMIT 20;"

# Cancel runaway runs
kubectl exec -it postgres -- psql -U aiagentx -c "
UPDATE runs SET status = 'cancelled', completed_at = now()
WHERE id IN (
  SELECT r.id FROM runs r
  LEFT JOIN run_steps rs ON r.id = rs.run_id
  WHERE r.created_at > now() - interval '1 hour'
  GROUP BY r.id
  HAVING COUNT(rs.id) > 100
);"
```

### Cause 5: Malicious/Abusive Usage
**Resolution:**
```bash
# Check for unusual patterns
kubectl exec -it postgres -- psql -U aiagentx -c "
SELECT tenant_id, COUNT(*) as run_count, SUM(spent_cost) as total_cost
FROM runs
WHERE created_at > now() - interval '1 hour'
GROUP BY tenant_id
HAVING SUM(spent_cost) > 100
ORDER BY total_cost DESC;"

# Temporarily disable tenant
kubectl exec -it postgres -- psql -U aiagentx -c "
UPDATE tenants SET is_active = false WHERE id = '<tenant_id>';"

# Notify tenant
# Send email/notification about usage
```

## Verification
```bash
# Monitor cost rate
watch -n 30 'curl -s "http://prometheus:9090/api/v1/query?query=rate(cost_usd_total[5m])" | jq .data.result[0].value[1]'

# Monitor hourly cost
curl -G 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=increase(cost_usd_total[1h])'
```

## Escalation
- If cost > $1000/hour: Page Finance Lead
- If tenant abuse suspected: Engage Security Team
- If provider pricing issue: Engage Provider Relations

## Related Dashboards
- [Business Metrics](http://grafana.aiagentx.io/d/aiagentx-business-metrics)

## Related Runbooks
- [Run Creation Spike](./run-creation-spike.md)