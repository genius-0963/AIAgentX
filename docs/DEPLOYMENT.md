# AIAgentX Deployment Documentation

## Overview

This document provides comprehensive deployment guidance for AIAgentX, covering development setups using Docker Compose and production deployments using Kubernetes. It includes infrastructure requirements, configuration management, scaling strategies, monitoring setup, and backup procedures.

## Deployment Architecture

### High-Level Deployment Architecture

```mermaid
graph TB
    subgraph "External Access"
        USERS[Users/Applications]
        LB[Load Balancer/Ingress]
    end
    
    subgraph "API Layer"
        API_PODS[API Pods]
        HPA[Horizontal Pod Autoscaler]
    end
    
    subgraph "Worker Layer"
        WORKER_PODS[Worker Pods]
        WORKER_HPA[Worker HPA]
    end
    
    subgraph "Infrastructure"
        POSTGRES[(PostgreSQL)]
        REDIS[(Redis)]
        MESSAGE_QUEUE[Redis Queue]
    end
    
    subgraph "Observability"
        PROMETHEUS[Prometheus]
        GRAFANA[Grafana]
        OTEL_COLLECTOR[OTLP Collector]
    end
    
    subgraph "Storage"
        PV[Persistent Volumes]
        BACKUP[Backup Storage]
    end
    
    USERS --> LB
    LB --> API_PODS
    API_PODS --> HPA
    API_PODS --> POSTGRES
    API_PODS --> REDIS
    API_PODS --> MESSAGE_QUEUE
    API_PODS --> OTEL_COLLECTOR
    
    WORKER_PODS --> MESSAGE_QUEUE
    WORKER_PODS --> POSTGRES
    WORKER_PODS --> REDIS
    WORKER_PODS --> OTEL_COLLECTOR
    WORKER_PODS --> WORKER_HPA
    
    POSTGRES --> PV
    REDIS --> PV
    POSTGRES --> BACKUP
    
    OTEL_COLLECTOR --> PROMETHEUS
    PROMETHEUS --> GRAFANA
```

## Infrastructure Requirements

### Minimum Requirements

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| **CPU** | 2 cores | 4 cores | 8+ cores |
| **Memory** | 2 GB | 8 GB | 16+ GB |
| **Storage** | 20 GB | 50 GB | 100+ GB SSD |
| **PostgreSQL** | 15+ | 16 | 16 with RLS |
| **Redis** | 7+ | 7+ Alpine | 7+ with persistence |
| **Python** | 3.12+ | 3.12+ | 3.12+ |
| **Docker** | 24.0+ | 24.0+ | 24.0+ |
| **Kubernetes** | 1.25+ | 1.27+ | 1.28+ |

### Network Requirements

- **Inbound Ports:** 80 (HTTP), 443 (HTTPS), 8000 (API)
- **Outbound Access:** LLM provider APIs, external services
- **Internal Communication:** API ↔ Workers ↔ Database ↔ Redis
- **Bandwidth:** 100+ Mbps recommended

## Docker Compose Deployment

### Development Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: aiagentx
      POSTGRES_PASSWORD: aiagentx
      POSTGRES_DB: aiagentx
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aiagentx"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://aiagentx:aiagentx@postgres:5432/aiagentx
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-secret-key
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app

  worker:
    build: .
    command: python -m app.workers.executor
    environment:
      - DATABASE_URL=postgresql+asyncpg://aiagentx:aiagentx@postgres:5432/aiagentx
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-secret-key
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  postgres_data:
  redis_data:
```

### Development Commands

```bash
# Start all services
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# View logs
docker compose logs -f api

# Stop all services
docker compose down

# Clean up volumes
docker compose down -v
```

## Kubernetes Deployment

### Namespace Configuration

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: aiagentx
  labels:
    name: aiagentx
    environment: production
```

### ConfigMap Configuration

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aiagentx-config
  namespace: aiagentx
data:
  APP_ENV: "production"
  LOG_LEVEL: "INFO"
  DATABASE_POOL_SIZE: "20"
  REDIS_MAX_CONNECTIONS: "50"
  WORKER_CONCURRENCY: "4"
  MEMORY_ENABLED: "true"
  CIRCUIT_BREAKER_ENABLED: "true"
```

### Secret Configuration

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: aiagentx-secrets
  namespace: aiagentx
type: Opaque
stringData:
  SECRET_KEY: "your-production-secret-key"
  DATABASE_URL: "postgresql+asyncpg://user:password@postgres:5432/aiagentx"
  REDIS_URL: "redis://redis:6379/0"
  OPENAI_API_KEY: "sk-proj-..."
  ANTHROPIC_API_KEY: "sk-ant-..."
  JWT_SECRET_KEY: "your-jwt-secret"
```

### PostgreSQL Deployment

```yaml
# postgres.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: aiagentx
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: aiagentx-secrets
              key: DATABASE_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: aiagentx-secrets
              key: DATABASE_PASSWORD
        - name: POSTGRES_DB
          value: aiagentx
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 20Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: aiagentx
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

### Redis Deployment

```yaml
# redis.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: aiagentx
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes"]
        volumeMounts:
        - name: redis-storage
          mountPath: /data
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
  volumeClaimTemplates:
  - metadata:
      name: redis-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: aiagentx
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### API Deployment

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aiagentx-api
  namespace: aiagentx
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aiagentx-api
  template:
    metadata:
      labels:
        app: aiagentx-api
    spec:
      containers:
      - name: api
        image: aiagentx/api:1.0.0
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: aiagentx-config
        - secretRef:
            name: aiagentx-secrets
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: aiagentx-api
  namespace: aiagentx
spec:
  selector:
    app: aiagentx-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aiagentx-api-hpa
  namespace: aiagentx
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aiagentx-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: aiagentx-api-pdb
  namespace: aiagentx
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: aiagentx-api
```

### Worker Deployment

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aiagentx-worker
  namespace: aiagentx
spec:
  replicas: 2
  selector:
    matchLabels:
      app: aiagentx-worker
  template:
    metadata:
      labels:
        app: aiagentx-worker
    spec:
      containers:
      - name: worker
        image: aiagentx/api:1.0.0
        command: ["python", "-m", "app.workers.executor"]
        envFrom:
        - configMapRef:
            name: aiagentx-config
        - secretRef:
            name: aiagentx-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aiagentx-worker-hpa
  namespace: aiagentx
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aiagentx-worker
  minReplicas: 2
  maxReplicas: 8
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Ingress Configuration

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: aiagentx-ingress
  namespace: aiagentx
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.aiagentx.com
    secretName: aiagentx-tls
  rules:
  - host: api.aiagentx.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: aiagentx-api
            port:
              number: 80
```

## Database Migrations

### Migration Strategy

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Alembic as Alembic
    participant DB as Database
    participant K8s as Kubernetes
    
    Dev->>Alembic: Generate migration
    Alembic->>Alembic: Create migration file
    Alembic-->>Dev: Migration file created
    
    Dev->>K8s: Apply migration job
    K8s->>Alembic: Run migration
    Alembic->>DB: Execute SQL
    DB-->>Alembic: Success
    Alembic-->>K8s: Migration complete
    K8s-->>Dev: Migration successful
```

### Migration Job

```yaml
# migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: aiagentx-migration
  namespace: aiagentx
spec:
  template:
    spec:
      containers:
      - name: migration
        image: aiagentx/api:1.0.0
        command: ["alembic", "upgrade", "head"]
        envFrom:
        - secretRef:
            name: aiagentx-secrets
      restartPolicy: OnFailure
```

## Configuration Management

### Environment Variables

```env
# Application Configuration
APP_ENV=production
LOG_LEVEL=INFO
DEBUG=false

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/aiagentx
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5

# Security Configuration
SECRET_KEY=your-production-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=RS256
JWT_EXPIRATION_MINUTES=60

# LLM Provider Configuration
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...

# Memory Configuration
MEMORY_ENABLED=true
EMBEDDING_PROVIDER=openai
DURABLE_MEMORY_RETENTION_DAYS=90

# Circuit Breaker Configuration
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT_SECONDS=60

# Observability Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
STRUCTLOG_LOG_LEVEL=INFO
```

## Scaling Strategies

### Horizontal Scaling

```mermaid
graph TB
    subgraph "API Scaling"
        API_HPA[API HPA]
        API_METRICS[CPU/Memory Metrics]
        API_SCALE[Scale Out/In]
    end
    
    subgraph "Worker Scaling"
        WORKER_HPA[Worker HPA]
        QUEUE_METRICS[Queue Depth Metrics]
        WORKER_SCALE[Scale Out/In]
    end
    
    subgraph "Database Scaling"
        READ_REPLICAS[Read Replicas]
        CONNECTION_POOL[Connection Pooling]
        QUERY_OPTIMIZATION[Query Optimization]
    end
    
    API_METRICS --> API_HPA
    API_HPA --> API_SCALE
    QUEUE_METRICS --> WORKER_HPA
    WORKER_HPA --> WORKER_SCALE
    API_SCALE --> CONNECTION_POOL
    WORKER_SCALE --> CONNECTION_POOL
    CONNECTION_POOL --> READ_REPLICAS
    READ_REPLICAS --> QUERY_OPTIMIZATION
```

### Scaling Configuration

| Component | Scaling Metric | Threshold | Action |
|-----------|---------------|-----------|--------|
| **API Pods** | CPU Utilization | >70% | Scale out |
| **API Pods** | Memory Utilization | >80% | Scale out |
| **Worker Pods** | Queue Depth | >100 | Scale out |
| **Worker Pods** | CPU Utilization | >70% | Scale out |
| **Database** | Connection Pool | >80% | Add replicas |

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: aiagentx
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    scrape_configs:
    - job_name: 'aiagentx-api'
      kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
          - aiagentx
      relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: aiagentx-api
      - source_labels: [__meta_kubernetes_pod_ip]
        target_label: __address__
        replacement: $1:8000
    
    - job_name: 'aiagentx-worker'
      kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
          - aiagentx
      relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: aiagentx-worker
```

### Grafana Dashboards

```yaml
# grafana-dashboard-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards
  namespace: aiagentx
data:
  aiagentx-overview.json: |
    {
      "dashboard": {
        "title": "AIAgentX Overview",
        "panels": [
          {
            "title": "Request Rate",
            "targets": [
              {
                "expr": "rate(api_requests_total[5m])"
              }
            ]
          },
          {
            "title": "Error Rate",
            "targets": [
              {
                "expr": "rate(api_requests_total{status=~\"5..\"}[5m])"
              }
            ]
          },
          {
            "title": "Active Runs",
            "targets": [
              {
                "expr": "worker_active_runs"
              }
            ]
          }
        ]
      }
    }
```

## Backup and Recovery

### Backup Strategy

```mermaid
graph TB
    subgraph "Backup Process"
        SCHEDULE[Scheduled Backup]
        DUMP[Database Dump]
        ENCRYPT[Encryption]
        COMPRESS[Compression]
        UPLOAD[Upload to Storage]
    end
    
    subgraph "Storage"
        S3[S3 Storage]
        GLACIER[Glacier Archive]
    end
    
    subgraph "Recovery Process"
        DOWNLOAD[Download Backup]
        DECRYPT[Decryption]
        EXTRACT[Extraction]
        RESTORE[Database Restore]
        VERIFY[Verification]
    end
    
    SCHEDULE --> DUMP
    DUMP --> ENCRYPT
    ENCRYPT --> COMPRESS
    COMPRESS --> UPLOAD
    UPLOAD --> S3
    S3 --> GLACIER
    
    DOWNLOAD --> DECRYPT
    DECRYPT --> EXTRACT
    EXTRACT --> RESTORE
    RESTORE --> VERIFY
```

### Backup Configuration

```yaml
# backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: aiagentx
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16-alpine
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -U aiagentx -h postgres aiagentx | gzip > /backup/aiagentx-$(date +%Y%m%d).sql.gz
              aws s3 cp /backup/aiagentx-$(date +%Y%m%d).sql.gz s3://aiagentx-backups/
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: aiagentx-secrets
                  key: DATABASE_PASSWORD
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            emptyDir: {}
          restartPolicy: OnFailure
```

### Recovery Procedure

```bash
# Download backup
aws s3 cp s3://aiagentx-backups/aiagentx-20240101.sql.gz .

# Extract backup
gunzip aiagentx-20240101.sql.gz

# Restore database
psql -U aiagentx -h postgres -d aiagentx < aiagentx-20240101.sql

# Verify restore
psql -U aiagentx -h postgres -d aiagentx -c "SELECT COUNT(*) FROM agents;"
```

## Deployment Checklist

### Pre-Deployment Checklist

- [ ] Infrastructure requirements met
- [ ] DNS records configured
- [ ] SSL/TLS certificates obtained
- [ ] Database credentials secured
- [ ] API keys configured
- [ ] Secret management setup
- [ ] Monitoring configured
- [ ] Logging configured
- [ ] Backup strategy tested
- [ ] Disaster recovery plan documented

### Post-Deployment Checklist

- [ ] Health checks passing
- [ ] Database migrations successful
- [ ] API endpoints accessible
- [ ] Workers processing queue
- [ ] Metrics being collected
- [ ] Logs being shipped
- [ ] Alerts configured
- [ ] Backup verification
- [ ] Performance baseline established
- [ ] Security scan completed

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check database connectivity
kubectl exec -it deployment/aiagentx-api -- pg_isready -h postgres -U aiagentx

# Check database logs
kubectl logs -f deployment/postgres
```

#### Redis Connection Issues
```bash
# Check Redis connectivity
kubectl exec -it deployment/aiagentx-api -- redis-cli -h redis ping

# Check Redis logs
kubectl logs -f deployment/redis
```

#### Worker Not Processing
```bash
# Check worker logs
kubectl logs -f deployment/aiagentx-worker

# Check queue depth
kubectl exec -it deployment/aiagentx-worker -- redis-cli -h redis LLEN run_queue
```

This deployment documentation provides comprehensive guidance for deploying AIAgentX in both development and production environments, including detailed Kubernetes manifests, configuration management, scaling strategies, monitoring setup, and backup procedures.