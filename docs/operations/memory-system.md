# Memory System Operational Documentation

## Overview

The AIAgentX Memory System provides three tiers of memory storage for AI agents:

1. **Ephemeral Memory** - Per-run, in-memory (Redis) with 24h TTL
2. **Session Memory** - Cross-run conversational context (Redis + PostgreSQL summaries)
3. **Durable Memory** - Long-term knowledge with semantic search (PostgreSQL + pgvector)

All memory operations enforce strict **tenant isolation** at multiple layers.

---

## Architecture

### Storage Layers

| Scope | Primary Storage | TTL | Use Case |
|-------|----------------|-----|----------|
| Ephemeral | Redis | 24h (configurable) | Single run context |
| Session | Redis + PostgreSQL | 7d (configurable) | Conversation continuity |
| Durable | PostgreSQL + pgvector | No default | Long-term knowledge |

### Tenant Isolation Layers

1. **Application Layer** - Mandatory `tenant_id` in all service methods
2. **Repository Layer** - All queries include `tenant_id` filter
3. **Database Layer** - Row Level Security (RLS) policies
4. **Encryption Layer** - Per-tenant keys via HKDF-SHA256
5. **Cache Layer** - Redis keys prefixed with tenant context

---

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
# Requires pgvector extension

# Redis
REDIS_URL=redis://host:6379/0

# Encryption
ENCRYPTION_MASTER_SECRET=32-byte-base64-encoded-secret

# Embeddings (optional - uses fake provider if not set)
OPENAI_API_KEY=sk-...

# Memory Settings
MEMORY_EPHEMERAL_TTL_SECONDS=86400      # 24h
MEMORY_SESSION_TTL_SECONDS=604800       # 7d
MEMORY_DEFAULT_LIMIT=8                   # Vector search results
MEMORY_MAX_LIMIT=50                      # Hard limit
MEMORY_CHUNK_SIZE=600                    # Tokens per chunk
MEMORY_CHUNK_OVERLAP=0.1                 # 10% overlap
```

### Retention Policies (Per Tenant + Scope)

Configure via API or database:

```sql
INSERT INTO memory_retention_policies (tenant_id, scope, retention_days, max_records_per_tenant, max_storage_mb)
VALUES 
  ('tenant-uuid', 'ephemeral', 1, 1000, 10),
  ('tenant-uuid', 'session', 7, 5000, 50),
  ('tenant-uuid', 'durable', 90, 100000, 1000);
```

---

## Deployment

### Prerequisites

1. **PostgreSQL 15+** with `pgvector` extension
2. **Redis 7+** (cluster mode supported)
3. **pgvector extension** - Install via:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

### Database Migration

Run Alembic migrations:
```bash
alembic upgrade head
```

Key migrations for memory:
- `0005_memory_system` - Creates tables, RLS policies, indexes
- `0006_outbox_events` - Creates outbox table for event publishing

### Vector Index Creation

After initial data load, create the ivfflat index:

```bash
# Via Python
from app.infrastructure.db.vector_index import create_vector_index
await create_vector_index(session, lists=100)

# Or via SQL
CREATE INDEX ix_memory_records_embedding 
ON memory_records USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Tune `lists` parameter:**
- < 10K rows: lists=10
- 10K-100K rows: lists=100
- 100K-1M rows: lists=1000
- > 1M rows: Consider HNSW index

---

## Monitoring & Observability

### Key Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `memory.write.latency` | Histogram | Write pipeline duration | p95 > 100ms |
| `memory.read.latency` | Histogram | Retrieval duration | p95 > 200ms |
| `memory.write.chunk_count` | Counter | Chunks per write | - |
| `memory.write.redacted` | Counter | Redacted writes | - |
| `memory.cleanup.deleted_count` | Counter | Expired records deleted | - |
| `memory.quota.exceeded` | Counter | Quota violations | > 0 |
| `memory.vector_index.size` | Gauge | Index size bytes | > 50% table size |
| `memory.storage.mb` | Gauge | Total storage per tenant | > 80% quota |

### Health Checks

```bash
# Check pgvector extension
psql -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# Check RLS policies
psql -c "SELECT * FROM pg_policy WHERE polrelid = 'memory_records'::regclass;"

# Check vector index
psql -c "SELECT * FROM pg_indexes WHERE indexname = 'ix_memory_records_embedding';"

# Check index stats
psql -c "SELECT * FROM pg_stat_user_indexes WHERE relname = 'memory_records';"
```

### Logs to Monitor

```json
{
  "event": "memory.write.completed",
  "tenant_id": "...",
  "chunk_count": 3,
  "was_redacted": true
}
{
  "event": "memory.retrieval.completed",
  "tenant_id": "...",
  "results_count": 8,
  "duration_ms": 45
}
{
  "event": "memory.cleanup.completed",
  "tenant_id": "...",
  "expired_deleted": 100,
  "freed_mb": 5.2
}
{
  "event": "memory.quota.exceeded",
  "tenant_id": "...",
  "scope": "durable",
  "reason": "Record count 10000 exceeds limit 10000"
}
```

---

## Operations

### Daily Cleanup Job

The cleanup service runs automatically via the worker scheduler:

```python
# Triggered daily at 2 AM UTC
result = await cleanup_service.run_full_cleanup(tenant_id)
```

Operations performed:
1. Delete expired records (all scopes)
2. Enforce retention policies
3. Check quota compliance
4. Emit `memory.cleanup` outbox events

### Manual Cleanup

```bash
# Via API
POST /api/v1/memory/cleanup
{
  "enforce_retention": true,
  "check_quotas": true
}

# Or via Python
from app.application.services.memory_cleanup_service import MemoryCleanupService
result = await cleanup_service.run_full_cleanup(tenant_id)
```

### Vector Index Maintenance

```bash
# Analyze index health
python -c "
from app.infrastructure.db.vector_index import analyze_vector_index
result = await analyze_vector_index(session)
print(result['recommendations'])
"

# Rebuild index if needed
python -c "
from app.infrastructure.db.vector_index import optimize_vector_index
await optimize_vector_index(session, lists=200)  # Increase lists
"

# Set ivfflat probes for query accuracy
SET ivfflat.probes = 10;  # Default 1, higher = more accurate
```

### Backup & Restore

```bash
# Backup memory tables
pg_dump -t memory_records -t session_summaries -t memory_retention_policies \
  -t outbox_events dbname > memory_backup.sql

# Restore
psql dbname < memory_backup.sql

# Note: pgvector indexes need rebuild after restore
```

---

## Troubleshooting

### Common Issues

#### 1. Vector Search Slow

**Symptoms:** `memory.read.latency` p95 > 500ms

**Causes:**
- No vector index created
- Index `lists` too low for data volume
- Table needs `ANALYZE`

**Fixes:**
```sql
-- Check if index exists
SELECT * FROM pg_indexes WHERE indexname = 'ix_memory_records_embedding';

-- Create index with appropriate lists
CREATE INDEX ix_memory_records_embedding 
ON memory_records USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 1000);

-- Update statistics
ANALYZE memory_records;
```

#### 2. Quota Exceeded Errors

**Symptoms:** `memory.quota.exceeded` counter increasing

**Causes:**
- Tenant hit `max_records_per_tenant` or `max_storage_mb`
- Retention policy not cleaning old data

**Fixes:**
```bash
# Check current usage
SELECT 
  scope,
  COUNT(*) as records,
  pg_size_pretty(SUM(length(content_ciphertext) + length(metadata::text))) as storage
FROM memory_records 
WHERE tenant_id = '...'
GROUP BY scope;

# Increase quota
UPDATE memory_retention_policies 
SET max_records_per_tenant = 20000, max_storage_mb = 2000
WHERE tenant_id = '...' AND scope = 'durable';

# Run cleanup
POST /api/v1/memory/cleanup
```

#### 3. Tenant Isolation Violations

**Symptoms:** Cross-tenant data access attempts in logs

**Causes:**
- Missing `tenant_id` in query
- RLS not enabled
- Application bug bypassing tenant filter

**Fixes:**
```sql
-- Verify RLS enabled
SELECT relname, relrowsecurity FROM pg_class 
WHERE relname IN ('memory_records', 'session_summaries', 'memory_retention_policies');

-- Enable if missing
ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY;

-- Check policy
SELECT * FROM pg_policy WHERE polrelid = 'memory_records'::regclass;
```

#### 4. Encryption/Decryption Failures

**Symptoms:** `EncryptionError` in logs

**Causes:**
- Wrong `ENCRYPTION_MASTER_SECRET`
- Corrupted ciphertext
- Tenant key derivation mismatch

**Fixes:**
```bash
# Verify secret is consistent across deployments
# Check key derivation
python -c "
from app.infrastructure.encryption.tenant_key import TenantKeyManager
mgr = TenantKeyManager.from_secret('your-secret')
key = mgr.derive_key('tenant-uuid')
print(key.hex())
"

# Rotate keys if compromised
python -c "
mgr = TenantKeyManager.from_secret('new-secret')
mgr.clear_cache()  # Forces re-derivation
"
```

#### 5. Redis Memory Pressure

**Symptoms:** Redis `used_memory` high, evictions occurring

**Fixes:**
```bash
# Check memory
redis-cli INFO memory

# Reduce TTLs
# EPHEMERAL: 24h -> 12h
# SESSION: 7d -> 3d

# Enable LRU eviction
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

## Performance Tuning

### Write Path Optimization

1. **Batch embeddings** - Use `generate_embeddings()` for multiple chunks
2. **Async encryption** - Already async, ensure connection pooling
3. **Chunk size** - 600 tokens optimal for text-embedding-3-small

### Read Path Optimization

1. **Vector index** - Critical for >10K records
2. **Result limit** - Default 8, max 50
3. **Similarity threshold** - Default 0.7, tune per use case
4. **Connection pooling** - Use PgBouncer for high concurrency

### Storage Optimization

1. **Compression** - Enable PostgreSQL compression on large tables
2. **Partitioning** - Consider partitioning `memory_records` by `created_at` for very large datasets
3. **Archival** - Move old durable memory to cold storage

---

## Security

### Data Classification

Content is automatically classified:
- **PUBLIC** - No sensitive data
- **INTERNAL** - IP addresses, internal refs
- **CONFIDENTIAL** - Emails, phone numbers
- **RESTRICTED** - SSN, credit cards, API keys, passwords

### Encryption

- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: HKDF-SHA256 from master secret + tenant_id
- **Nonce**: 96-bit random per encryption
- **Format**: Base64(nonce || ciphertext)

### Audit Logging

All memory operations emit audit events:
- `memory.written` - Record created
- `memory.deleted` - Record deleted (cleanup or manual)
- `memory.accessed` - Record retrieved (configurable)

---

## API Reference

### Write Memory
```
POST /api/v1/memory/write
{
  "content": "string",
  "scope": "ephemeral|session|durable",
  "namespace": "string",
  "metadata": {},
  "session_id": "optional"
}
```

### Search Memory
```
POST /api/v1/memory/search
{
  "query": "string",
  "scope": "ephemeral|session|durable",
  "namespace": "string",
  "limit": 8,
  "session_id": "optional",
  "metadata_filters": {},
  "similarity_threshold": 0.7
}
```

### Session Management
```
POST /api/v1/memory/session/start
POST /api/v1/memory/session/{session_id}/add
GET  /api/v1/memory/session/{session_id}
POST /api/v1/memory/session/{session_id}/end
GET  /api/v1/memory/sessions
```

### Cleanup & Stats
```
POST /api/v1/memory/cleanup
GET  /api/v1/memory/stats
```

---

## Capacity Planning

### Estimating Storage

| Scope | Avg Record Size | Records/Tenant | Est. Storage |
|-------|----------------|----------------|--------------|
| Ephemeral | 1 KB | 1,000 | 1 MB |
| Session | 5 KB | 10,000 | 50 MB |
| Durable | 10 KB | 100,000 | 1 GB |

### pgvector Index Sizing

| Records | Index Type | Lists | Est. Index Size |
|---------|-----------|-------|-----------------|
| 10K | ivfflat | 10 | 50 MB |
| 100K | ivfflat | 100 | 500 MB |
| 1M | HNSW | N/A | 2 GB |

---

## Incident Response

### Data Breach

1. Rotate `ENCRYPTION_MASTER_SECRET` immediately
2. Re-encrypt all tenant data: `key_manager.rotate_key(tenant_id)`
3. Audit all memory access logs
4. Notify affected tenants

### Accidental Deletion

1. Check `outbox_events` for `memory.deleted` events
2. Restore from latest backup
3. Rebuild vector indexes

### Performance Degradation

1. Check `pg_stat_user_indexes` for index usage
2. Run `ANALYZE` on memory tables
3. Increase vector index `lists` parameter
4. Consider read replicas for memory queries

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-08-23 | Initial release: 3-tier memory, vector search, tenant isolation, encryption |