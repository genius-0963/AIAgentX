# Runbook: API Down

## Overview
**Alert:** `APIDown`
**Severity:** Critical
**Component:** API

Triggered when the API health check endpoint returns non-200 for more than 1 minute.

## Impact
- Complete service outage
- All API consumers affected
- Immediate SLA breach

## Diagnosis

### 1. Verify API Status
```bash
# Check if pods are running
kubectl get pods -n aiagentx -l app.kubernetes.io/component=api

# Check pod status
kubectl describe pod -n aiagentx -l app.kubernetes.io/component=api

# Check health endpoint directly
kubectl exec -it <api-pod> -- curl -v http://localhost:8000/healthz
```

### 2. Check Pod Events
```bash
# Check for OOM kills, crashes
kubectl get events -n aiagentx --field-selector involvedObject.kind=Pod --sort-by='.lastTimestamp' | grep api

# Check pod logs
kubectl logs -n aiagentx -l app.kubernetes.io/component=api --previous --tail=200
```

### 3. Check Dependencies
```bash
# Database connectivity
kubectl exec -it <api-pod> -- pg_isready -h postgres -p 5432

# Redis connectivity
kubectl exec -it <api-pod> -- redis-cli -h redis ping
```

## Common Causes & Resolution

### Cause 1: Pod Crash / OOM Kill
**Resolution:**
```bash
# Check for OOM
kubectl describe pod <api-pod> -n aiagentx | grep -A 5 "Last State"

# Increase memory limits
kubectl patch deployment aiagentx-api -n aiagentx -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi"}}}]}}}}'

# Restart deployment
kubectl rollout restart deployment/aiagentx-api -n aiagentx
```

### Cause 2: Database Unavailable
**Resolution:**
```bash
# Check postgres status
kubectl get pods -n aiagentx -l app.kubernetes.io/component=database

# Check postgres logs
kubectl logs -n aiagentx -l app.kubernetes.io/component=database --tail=100

# Restart postgres if needed
kubectl rollout restart statefulset/postgres -n aiagentx
```

### Cause 3: Redis Unavailable
**Resolution:**
```bash
# Check redis status
kubectl get pods -n aiagentx -l app.kubernetes.io/component=cache

# Restart redis
kubectl rollout restart deployment/redis -n aiagentx
```

### Cause 4: Network Policy Blocking
**Resolution:**
```bash
# Check network policies
kubectl get networkpolicies -n aiagentx

# Temporarily allow all for debugging
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-all-api
  namespace: aiagentx
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - {}
  egress:
  - {}
EOF

# Remove after debugging
kubectl delete networkpolicy allow-all-api -n aiagentx
```

### Cause 5: Configuration Error
**Resolution:**
```bash
# Check configmap
kubectl get configmap aiagentx-config -n aiagentx -o yaml

# Check secrets
kubectl get secret aiagentx-secrets -n aiagentx -o yaml

# Rollback config if recently changed
kubectl rollout undo configmap/aiagentx-config -n aiagentx
```

## Verification
```bash
# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=api -n aiagentx --timeout=300s

# Verify health endpoint
curl -s http://api.aiagentx.io/healthz
```

## Escalation
- Immediate: Page on-call engineer
- If database down: Engage Database Team
- If infrastructure issue: Engage Platform Team

## Related Dashboards
- [System Overview](http://grafana.aiagentx.io/d/aiagentx-overview)

## Related Runbooks
- [High API Error Rate](./api-high-error-rate.md)
- [Database Pool Exhausted](./db-pool-exhausted.md)