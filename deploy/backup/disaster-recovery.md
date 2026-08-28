# Disaster Recovery Plan

## Overview

This document outlines the disaster recovery procedures for the AIAgentX platform. It covers scenarios ranging from single-component failures to complete region outages.

## Recovery Objectives

| Metric | Target |
|--------|--------|
| RTO (Recovery Time Objective) | 4 hours |
| RPO (Recovery Point Objective) | 24 hours (daily backups) |
| Availability Target | 99.9% |

## Backup Strategy

### Database Backups
- **Frequency**: Daily at 2 AM UTC
- **Retention**: 30 days local, 90 days in S3
- **Encryption**: AES-256 at rest
- **Storage**: Local PVC + S3 (cross-region replication)
- **Format**: SQL dump with schema + data

### Configuration Backups
- **Kubernetes manifests**: Version controlled in Git
- **Secrets**: Stored in sealed-secrets or external secret manager
- **ConfigMaps**: Version controlled in Git

### Application State
- **Runs/Execution state**: Recoverable from database
- **Audit logs**: Recoverable from database (2555 day retention)
- **Metrics/Monitoring**: Recoverable from Prometheus (30 day retention)

## Recovery Scenarios

### Scenario 1: Single Pod Failure
**Impact**: Minimal - Kubernetes self-heals
**Recovery**: Automatic via kubelet
**Time**: < 5 minutes

### Scenario 2: Database Pod Failure
**Impact**: Read/write unavailable
**Recovery**: 
1. Kubernetes restarts pod automatically
2. If persistent volume corrupted, restore from backup
**Time**: 5-30 minutes

### Scenario 3: Complete Database Loss
**Impact**: Full data loss
**Recovery**:
1. Provision new PostgreSQL instance
2. Run restore script: `./restore.sh <timestamp>`
3. Verify data integrity
4. Reconfigure application
**Time**: 2-4 hours

### Scenario 4: Kubernetes Cluster Failure
**Impact**: Complete service outage
**Recovery**:
1. Provision new cluster (EKS/GKE/AKS)
2. Apply Kubernetes manifests: `kubectl apply -k deploy/k8s/overlays/production`
4. Restore database from backup
5. Update DNS to point to new cluster
**Time**: 2-4 hours

### Scenario 5: Region Outage
**Impact**: Complete service outage
**Recovery**:
1. Failover to DR region
2. Apply manifests to DR cluster
3. Restore database from cross-region S3 backup
5. Update global load balancer/DNS
**Time**: 4-8 hours

## Recovery Procedures

### Database Restore Procedure

#### From Local Backup
```bash
# List available backups
./restore.sh --list

# Restore specific backup
./restore.sh 20240115_020000

# Force restore without confirmation
./restore.sh --force 20240115_020000
```

#### From S3 Backup
```bash
# List S3 backups
aws s3 ls s3://my-backup-bucket/aiagentx/backups/

# Download and restore
./restore.sh --download 20240115_020000
```

#### Manual Restore Steps
```bash
# 1. Download/locate backup file
BACKUP_FILE="/backups/aiagentx_20240115_020000.sql.gz"

# 2. Decrypt if needed
openssl enc -aes-256-cbc -d -pbkdf2 -in backup.sql.gz.enc -out backup.sql.gz -pass pass:$KEY

# 3. Decompress
gunzip -c backup.sql.gz > backup.sql

# 4. Terminate connections
psql -h postgres -U aiagentx -d postgres -c "
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = 'aiagentx';"

# 5. Drop and recreate database
psql -h postgres -U aiagentx -d postgres -c "DROP DATABASE IF EXISTS aiagentx;"
psql -h postgres -U aiagentx -d postgres -c "CREATE DATABASE aiagentx OWNER aiagentx;"

# 5. Restore
psql -h postgres -U aiagentx -d aiagentx -f backup.sql

# 5. Verify
psql -h postgres -U aiagentx -d aiagentx -c "SELECT count(*) FROM runs;"
```

### Kubernetes Cluster Recovery

#### Full Cluster Restore
```bash
# 1. Provision new cluster (example for EKS)
eksctl create cluster -f cluster-config.yaml

# 2. Install required operators
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
kubectl apply -f https://github.com/kubernetes-sigs/external-dns/releases/download/v0.13.0/external-dns.yaml

# 3. Apply AIAgentX manifests
kubectl apply -k deploy/k8s/overlays/production

# 4. Verify deployments
kubectl get pods -n aiagentx -w

# 5. Restore database (see above)

# 6. Update DNS
# Update Route53/CloudFlare to point to new ALB/ingress
```

### Configuration Recovery
```bash
# 1. Clone Git repository
git clone https://github.com/aiagentx/infrastructure.git

# 2. Apply sealed secrets
kubectl apply -f sealed-secrets/

# 3. Apply ConfigMaps
kubectl apply -k deploy/k8s/overlays/production

# 4. Verify secrets
kubectl get secrets -n aiagentx
```

## Validation Procedures

### Post-Recovery Validation
```bash
# 1. Run validation script
./scripts/deploy-validation/validate-deployment.py --namespace aiagentx

# 2. Check API health
curl -s https://api.aiagentx.io/healthz | jq .

# 3. Check database connectivity
curl -s https://api.aiagentx.io/v1/runs -H "Authorization: Bearer $TOKEN" | jq .

# 4. Check metrics
curl -s http://prometheus:9090/api/v1/query?query=up{job="aiagentx-api"}

# 5. Run smoke tests
./scripts/smoke-tests.sh
```

### Data Integrity Checks
```bash
# 1. Verify row counts
psql -h postgres -U aiagentx -d aiagentx -c "
SELECT 'tenants' as table, count(*) FROM tenants
UNION ALL SELECT 'runs', count(*) FROM runs
UNION ALL SELECT 'agents', count(*) FROM agents
UNION ALL SELECT 'audit_logs', count(*) FROM audit_logs;"

# 2. Verify recent data
psql -h postgres -U aiagentx -d aiagentx -c "
SELECT count(*) FROM runs WHERE created_at > now() - interval '24 hours';"

# 3. Verify audit log continuity
psql -h postgres -U aiagentx -d aiagentx -c "
SELECT max(created_at), min(created_at) FROM audit_logs;"
```

## Communication Plan

### Internal Notification
| Severity | Channel | Recipients |
|----------|---------|------------|
| Critical | PagerDuty + Slack + Email | On-call, Team Leads, Engineering Manager |
| Warning | Slack | On-call, Team Leads |
| Info | Slack | Team |

### External Communication
- Status page: status.aiagentx.io
- Customer notifications: Email for affected tenants
- Social media: Twitter @aiagentxstatus

## Testing Schedule

| Test | Frequency | Scope |
|------|-----------|-------|
| Backup integrity | Weekly | Verify backup can be restored |
| Full DR drill | Quarterly | Full cluster + DB restore |
| Partial DR | Monthly | DB restore only |
| Failover test | Semi-annually | Region failover |

## Contact Information

| Role | Name | Contact |
|------|------|---------|
| Incident Commander | TBD | pagerduty |
| Database Lead | TBD | pagerduty |
| Platform Lead | TBD | pagerduty |
| Engineering Manager | TBD | email/slack |
| Security Team | security@aiagentx.io | email |

## Post-Incident Process

1. **Incident Report**: Create within 24 hours
2. **Root Cause Analysis**: Within 72 hours
3. **Action Items**: Track in Jira/GitHub Issues
4. **Runbook Updates**: Update within 1 week
5. **Retrospective**: Within 2 weeks

## Appendix: Useful Commands

```bash
# Check backup status
kubectl get cronjob aiagentx-db-backup -n aiagentx
kubectl get jobs -n aiagentx -l app.kubernetes.io/component=backup

# Manual backup trigger
kubectl create job --from=cronjob/aiagentx-db-backup manual-backup-$(date +%s) -n aiagentx

# Check backup logs
kubectl logs -n aiagentx -l job-name=aiagentx-db-backup-<timestamp>

# Verify S3 backup
aws s3 ls s3://my-bucket/aiagentx/backups/ --human-readable --summarize

# Test restore to staging
./restore.sh --download --force 20240115_020000  # Run against staging namespace
```