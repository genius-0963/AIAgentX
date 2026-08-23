# Sprint 6: Memory and Retrieval System - Detailed Implementation Plan

**Status**: Planning Phase  
**Sprint Goal**: Implement complete memory system with ephemeral, session, and durable modes, vector embeddings, semantic search, and tenant isolation  
**Duration**: 3 weeks  
**Current State**: Domain layer, write pipeline, encryption, embeddings, text processing, and DB migrations are implemented. Need retrieval service, cleanup service, Redis integration, API endpoints, tests, and worker integration.

---

## Executive Summary

### What's Already Implemented ✅
| Component | Status | Location |
|-----------|--------|----------|
| Domain Entities (MemoryRecord, SessionSummary, MemoryRetentionPolicy, MemoryAggregate) | ✅ Complete | `app/domain/entities/memory.py` |
| Repository Protocols | ✅ Complete | `app/domain/repositories/memory.py` |
| SQLAlchemy Models | ✅ Complete | `app/infrastructure/db/models/memory.py` |
| Alembic Migration (pgvector, RLS, indexes) | ✅ Complete | `app/infrastructure/db/migrations/versions/0005_memory_system.py` |
| SQL Repository Implementations | ✅ Complete | `app/infrastructure/db/repositories/memory.py` |
| Memory Write Service (validation, redaction, chunking, embedding, encryption) | ✅ Complete | `app/application/services/memory_write_service.py` |
| Embedding Service (OpenAI + Fake) | ✅ Complete | `app/infrastructure/embeddings/` |
| Encryption Service (AES-256-GCM + HKDF tenant keys) | ✅ Complete | `app/infrastructure/encryption/` |
| Text Processing (Normalizer, Chunker, Classifier, Redactor) | ✅ Complete | `app/infrastructure/text/` |

### What Remains to Implement 🔄
| Component | Priority | Complexity |
|-----------|----------|------------|
| Memory Retrieval Service (read path) | **Critical** | Medium |
| Memory Management/Cleanup Service | **Critical** | Medium |
| Redis Integration (Ephemeral/Session cache) | **Critical** | High |
| Session Memory Management | **High** | Medium |
| Memory API Endpoints (REST) | **High** | Medium |
| Vector Index Creation (ivfflat) | **High** | Low |
| Outbox Event Publishing | **Medium** | Medium |
| Unit Tests (Memory System) | **Critical** | High |
| Integration Tests (DB, Redis, Vector) | **Critical** | High |
| Worker/Executor Integration | **High** | Medium |

---

## Phase 1: Core Retrieval & Management Services (Week 1)

### 1.1 Memory Retrieval Service
**File**: `app/application/services/memory_retrieval_service.py` (NEW)

```python
# Required Methods:
# - retrieve_memory(): Main semantic search with filters
# - retrieve_by_metadata(): Metadata-based filtering
# - retrieve_by_session(): Session-scoped retrieval
# - get_memory_record(): Single record by ID
# - list_memory_records(): Paginated listing
# - decrypt_and_redact_results(): Post-retrieval processing
```

**Dependencies**: 
- `MemoryRepository` (existing)
- `EncryptionService` (existing)
- `TextRedactor` (existing)
- `EmbeddingService` (existing)

**Key Features**:
- Mandatory tenant_id filter (enforced at service layer)
- Vector similarity search using pgvector `<=>` operator
- Namespace, scope, session_id, expiration filtering
- Result limit (default 8, configurable max 50)
- Content decryption + policy-based redaction
- Similarity scores in results
- Query performance logging

### 1.2 Memory Cleanup Service
**File**: `app/application/services/memory_cleanup_service.py` (NEW)

```python
# Required Methods:
# - cleanup_expired(): Delete expired records per tenant
# - enforce_retention_policies(): Apply retention rules
# - enforce_quotas(): Check and enforce storage/record limits
# - generate_cleanup_report(): Metrics for monitoring
# - backup_memory(): Export before deletion (optional)
```

**Scheduled Job**: Daily cron via existing cleanup actors pattern
- Use `app/workers/executor.py` pattern
- Leverage `MemoryRepository.delete_expired()`
- Emit events for audit trail

### 1.3 Vector Index Management
**File**: `app/infrastructure/db/vector_index.py` (NEW)

```python
# Required Functions:
# - create_vector_index(): Create ivfflat index after data load
# - optimize_vector_index(): REINDEX or adjust lists parameter
# - get_index_stats(): Monitor index health
```

**Note**: Migration 0005 has this commented out - needs post-deployment creation.

---

## Phase 2: Redis Integration & Session Memory (Week 1-2)

### 2.1 Redis Memory Cache
**File**: `app/infrastructure/cache/memory_cache.py` (NEW)

```python
# Ephemeral Memory (per run)
class EphemeralMemoryCache:
    - set(run_id, key, value, ttl=24h)
    - get(run_id, key)
    - delete(run_id, key)
    - clear_run(run_id)
    - exists(run_id, key)

# Session Memory (cross-run)
class SessionMemoryCache:
    - set(session_id, key, value, ttl=configurable)
    - get(session_id, key)
    - append(session_id, key, value)  # For conversation history
    - get_recent(session_id, limit)
    - summarize_and_persist(session_id)  # Trigger durable write
```

**Integration Points**:
- Worker executor stores ephemeral memory during run
- Session cache bridges runs for continuity
- Background job syncs session → durable (PostgreSQL)
- TTL from tenant retention policy

### 2.2 Session Memory Manager
**File**: `app/application/services/session_memory_service.py` (NEW)

```python
# Required Methods:
# - create_session(tenant_id, agent_id, session_id)
# - add_to_session(session_id, content, metadata)
# - get_session_context(session_id, limit=10)
# - summarize_session(session_id) -> SessionSummary
# - end_session(session_id)  # Triggers durable persistence
# - get_session_summaries(tenant_id, agent_id)
```

**Flow**:
1. Run starts → check/create session in Redis
2. Each interaction → append to Redis session cache
3. On session end or threshold → summarize → write to PostgreSQL (durable)
4. SessionSummary stored for quick retrieval

---

## Phase 3: API Layer & Integration (Week 2)

### 3.1 Memory API Endpoints
**File**: `app/api/v1/memory/` (NEW directory)

```
app/api/v1/memory/
├── __init__.py
├── router.py          # FastAPI router
├── schemas.py         # Pydantic request/response models
└── dependencies.py    # Auth, tenant resolution
```

**Endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| POST | `/memory/write` | Write memory (uses write pipeline) |
| POST | `/memory/search` | Semantic search retrieval |
| GET | `/memory/{record_id}` | Get single record |
| GET | `/memory` | List with pagination/filters |
| DELETE | `/memory/{record_id}` | Delete record |
| POST | `/memory/session/start` | Start session |
| POST | `/memory/session/{session_id}/add` | Add to session |
| GET | `/memory/session/{session_id}` | Get session context |
| POST | `/memory/session/{session_id}/end` | End session & persist |
| GET | `/memory/stats` | Usage stats for tenant |

**Request/Response Models**:
```python
# Write Request
class MemoryWriteRequest:
    content: str
    scope: MemoryScope
    namespace: str
    metadata: dict = {}
    session_id: str | None = None

# Search Request
class MemorySearchRequest:
    query: str
    scope: MemoryScope
    namespace: str
    limit: int = 8
    session_id: str | None = None
    metadata_filters: dict = {}

# Search Response
class MemorySearchResult:
    id: UUID
    content: str
    metadata: dict
    similarity: float
    scope: MemoryScope
    namespace: str
    created_at: datetime
```

### 3.2 Worker/Executor Integration
**File**: `app/workers/executor.py` (MODIFY)

Add memory context to run execution:
```python
# In RunExecutor:
async def _execute_with_memory(self, run: Run, agent: Agent) -> RunResult:
    # 1. Load ephemeral memory from Redis (if run.resume)
    # 2. Load session memory from Redis
    # 3. Load relevant durable memory via semantic search
    # 4. Execute agent with memory context
    # 5. Write new memories via MemoryWriteService
    # 6. Update session cache
    # 7. Return result with memory IDs
```

**Memory Context Object**:
```python
@dataclass
class MemoryContext:
    ephemeral: dict[str, Any]      # Run-scoped
    session: list[MemoryRecord]    # Session-scoped
    durable: list[MemoryRecord]    # Semantic search results
```

---

## Phase 4: Testing & Hardening (Week 2-3)

### 4.1 Unit Tests
**Files** (NEW):
```
tests/unit/
├── test_memory_entities.py
├── test_memory_write_service.py
├── test_memory_retrieval_service.py
├── test_memory_cleanup_service.py
├── test_session_memory_service.py
├── test_memory_cache.py
├── test_text_normalizer.py
├── test_text_chunker.py
├── test_sensitive_classifier.py
├── test_text_redactor.py
├── test_embedding_service.py
└── test_encryption_service.py
```

**Coverage Targets**:
- Write pipeline: 95%+
- Retrieval service: 90%+
- Cleanup service: 85%+
- Text processing: 90%+
- Encryption: 95%+

### 4.2 Integration Tests
**Files** (NEW):
```
tests/integration/
├── test_memory_db.py           # Repository + PostgreSQL
├── test_memory_redis.py        # Cache operations
├── test_memory_vector_search.py # pgvector accuracy
├── test_memory_api.py          # Full API flow
├── test_memory_isolation.py    # Tenant isolation (negative tests)
├── test_memory_retention.py    # Cleanup & quotas
└── test_session_continuity.py  # Cross-run session
```

**Test Infrastructure**:
- Testcontainers for PostgreSQL + pgvector
- Testcontainers for Redis
- Fixtures for tenant, agent, memory records
- FakeEmbeddingProvider for deterministic tests

### 4.3 Security Tests (Negative)
```python
# test_memory_isolation.py
async def test_cannot_access_other_tenant_memory():
    # Create tenant A and B
    # Write memory as tenant A
    # Attempt read as tenant B → Should return empty/raise

async def test_rls_enforced_at_db_level():
    # Direct SQL with wrong tenant_id → 0 rows

async def test_encryption_key_isolation():
    # Encrypt with tenant A key
    # Decrypt with tenant B key → Should fail
```

### 4.4 Performance Tests
```python
# Benchmarks (using pytest-benchmark)
async def test_write_latency_p95_under_100ms():
    # Write 1000 records, measure p95

async def test_retrieval_latency_p95_under_200ms():
    # Search 10000 records, measure p95

async def test_vector_search_accuracy():
    # Known query/result pairs, measure recall@8
```

---

## Phase 5: Documentation & Observability (Week 3)

### 5.1 API Documentation
- OpenAPI schemas in `app/api/v1/memory/schemas.py`
- Example requests/responses in docstrings
- Postman collection export (optional)

### 5.2 Operational Documentation
**File**: `docs/operations/memory-system.md` (NEW)

Topics:
- Deployment (pgvector extension, RLS setup)
- Configuration (retention policies, TTLs, chunk sizes)
- Monitoring (key metrics, alerts)
- Troubleshooting (common issues, debugging)
- Backup/Restore procedures
- Capacity planning

### 5.3 Observability
**Metrics to Emit** (via existing logging):
- `memory.write.latency` (histogram)
- `memory.write.chunk_count` (counter)
- `memory.write.redacted` (counter)
- `memory.read.latency` (histogram)
- `memory.read.result_count` (histogram)
- `memory.cleanup.deleted_count` (counter)
- `memory.quota.exceeded` (counter)
- `memory.vector_index.size` (gauge)

---

## Detailed Task Breakdown

### Task 6.1: Memory Retrieval Service [8 pts]
- [ ] Create `memory_retrieval_service.py` with full retrieval logic
- [ ] Implement `retrieve_memory()` with vector search
- [ ] Implement `retrieve_by_metadata()` 
- [ ] Implement `retrieve_by_session()`
- [ ] Add decryption + redaction post-processing
- [ ] Add mandatory tenant filtering
- [ ] Add query performance logging
- [ ] Write unit tests

### Task 6.2: Memory Cleanup Service [5 pts]
- [ ] Create `memory_cleanup_service.py`
- [ ] Implement `cleanup_expired()` using repository
- [ ] Implement `enforce_retention_policies()`
- [ ] Implement `enforce_quotas()`
- [ ] Create scheduled job (daily cron)
- [ ] Add audit event emission
- [ ] Write unit tests

### Task 6.3: Vector Index Management [3 pts]
- [ ] Create `vector_index.py` utility
- [ ] Implement `create_vector_index()` (ivfflat, lists=100)
- [ ] Add `optimize_vector_index()` for maintenance
- [ ] Document when to run (after bulk load)
- [ ] Add index health monitoring query

### Task 6.4: Redis Memory Cache [8 pts]
- [ ] Create `memory_cache.py` with Ephemeral/Session classes
- [ ] Implement Redis key schema: `memory:ephemeral:{run_id}:{key}`
- [ ] Implement Redis key schema: `memory:session:{session_id}:{key}`
- [ ] Add TTL from retention policy
- [ ] Implement session append/get_recent
- [ ] Add `summarize_and_persist()` trigger
- [ ] Write unit tests with fakeredis
- [ ] Write integration tests with Testcontainers Redis

### Task 6.5: Session Memory Service [5 pts]
- [ ] Create `session_memory_service.py`
- [ ] Implement session CRUD
- [ ] Implement summarization (LLM-based or extractive)
- [ ] Implement session → durable persistence
- [ ] Add session listing for agent
- [ ] Write unit tests
- [ ] Write integration tests

### Task 6.6: Memory API Endpoints [8 pts]
- [ ] Create `app/api/v1/memory/` module
- [ ] Define Pydantic schemas
- [ ] Implement all 10 endpoints
- [ ] Add authentication/tenant dependencies
- [ ] Add request validation
- [ ] Add response serialization
- [ ] Write API integration tests

### Task 6.7: Worker Integration [5 pts]
- [ ] Modify `RunExecutor` to load memory context
- [ ] Add ephemeral memory load/save
- [ ] Add session memory load/save
- [ ] Add durable memory retrieval (semantic)
- [ ] Write memory IDs to run result
- [ ] Write integration tests

### Task 6.8: Outbox Event Publishing [3 pts]
- [ ] Add outbox table/model (if not exists)
- [ ] Publish `memory.written` event in write service
- [ ] Publish `memory.deleted` event in cleanup
- [ ] Add event handlers for downstream consumers

### Task 6.9: Comprehensive Testing [13 pts]
- [ ] Unit tests for all new services (target 90%+ coverage)
- [ ] Integration tests with Testcontainers
- [ ] Negative security tests (tenant isolation)
- [ ] Performance benchmarks
- [ ] Vector search accuracy tests
- [ ] Session continuity tests
- [ ] Retention/cleanup tests

### Task 6.10: Documentation & Observability [3 pts]
- [ ] Operational documentation
- [ ] API documentation
- [ ] Metrics emission
- [ ] Alerting rules (optional)

---

## Technical Decisions & Architecture Notes

### 1. Memory Scopes & Storage Strategy
| Scope | Primary Storage | TTL | Use Case |
|-------|----------------|-----|----------|
| Ephemeral | Redis (in-memory) | 24h default | Single run context |
| Session | Redis + PostgreSQL (summary) | Configurable (7d default) | Cross-run conversation |
| Durable | PostgreSQL + pgvector | Configurable (no default) | Long-term knowledge |

### 2. Tenant Isolation Layers
1. **Application Layer**: Mandatory `tenant_id` in all service methods
2. **Repository Layer**: All queries include `tenant_id` filter
3. **Database Layer**: Row Level Security (RLS) policies
4. **Encryption Layer**: Per-tenant keys via HKDF
5. **Cache Layer**: Redis keys prefixed with `tenant:{tenant_id}:`

### 3. Vector Search Configuration
- **Embedding Model**: text-embedding-3-small (1536 dims)
- **Index Type**: ivfflat with `lists=100` (adjust based on data volume)
- **Distance Metric**: Cosine (`vector_cosine_ops`)
- **Similarity Threshold**: Configurable (default 0.7)
- **Max Results**: 8 default, 50 max

### 4. Chunking Strategy
- **Target Size**: 600 tokens (~2400 chars)
- **Overlap**: 10% (60 tokens)
- **Min Chunk**: 100 tokens
- **Max Chunk**: 1000 tokens
- **Tokenizer**: tiktoken cl100k_base (fallback: char-based)

### 5. Encryption Strategy
- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: HKDF-SHA256 from master secret + tenant_id
- **Nonce**: 96-bit random per encryption
- **Format**: Base64(nonce + ciphertext)
- **Key Rotation**: Supported via `TenantKeyManager.rotate_key()`

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| pgvector performance at scale | Medium | High | Monitor, tune ivfflat lists, consider HNSW later |
| Tenant isolation bypass | Low | Critical | RLS + app-layer + negative tests |
| Encryption key management | Low | High | HKDF derivation, rotation support, audit logs |
| Memory growth unbounded | Medium | High | Retention policies, quotas, daily cleanup job |
| Vector search accuracy | Medium | Medium | Tune chunk size, overlap, similarity threshold |
| Redis memory pressure | Medium | Medium | TTL enforcement, LRU eviction config |

---

## Dependencies & Prerequisites

### Internal Dependencies
- ✅ Sprint 1-5 completed (infrastructure, domain, API, providers, reliability)
- ✅ PostgreSQL with pgvector extension
- ✅ Redis cluster
- ✅ Encryption master secret in settings
- ✅ OpenAI API key (or fake provider for tests)

### External Dependencies
- `pgvector` PostgreSQL extension
- `tiktoken` for tokenization (optional, has fallback)
- `cryptography` for AES-GCM/HKDF
- `redis` async client
- `presidio-analyzer/anonymizer` (optional, for advanced PII)

---

## Definition of Done Checklist

### Per User Story
- [ ] All acceptance criteria met
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration tests pass
- [ ] Security review (for US-6.6)
- [ ] Code review approved

### Sprint Level
- [ ] All 7 user stories completed
- [ ] Ephemeral memory works for single runs
- [ ] Session memory maintains continuity across runs
- [ ] Durable memory supports semantic search with pgvector
- [ ] Write pipeline validates, classifies, redacts, chunks, embeds, encrypts
- [ ] Retrieval system filters by tenant/agent/namespace/session/expiry
- [ ] Tenant isolation enforced at 3+ layers
- [ ] Cleanup jobs maintain storage bounds
- [ ] Performance: write p95 <100ms, read p95 <200ms
- [ ] Vector search accuracy >90% recall@8
- [ ] Documentation updated
- [ ] Sprint retrospective completed

---

## File Creation Summary

### New Files to Create (~15)
```
app/application/services/
├── memory_retrieval_service.py
├── memory_cleanup_service.py
├── session_memory_service.py

app/infrastructure/cache/
├── memory_cache.py

app/infrastructure/db/
├── vector_index.py

app/api/v1/memory/
├── __init__.py
├── router.py
├── schemas.py
├── dependencies.py

tests/unit/
├── test_memory_entities.py
├── test_memory_write_service.py
├── test_memory_retrieval_service.py
├── test_memory_cleanup_service.py
├── test_session_memory_service.py
├── test_memory_cache.py
├── test_text_normalizer.py
├── test_text_chunker.py
├── test_sensitive_classifier.py
├── test_text_redactor.py
├── test_embedding_service.py
├── test_encryption_service.py

tests/integration/
├── test_memory_db.py
├── test_memory_redis.py
├── test_memory_vector_search.py
├── test_memory_api.py
├── test_memory_isolation.py
├── test_memory_retention.py
├── test_session_continuity.py

docs/operations/
├── memory-system.md
```

### Files to Modify (~5)
```
app/workers/executor.py              # Add memory context loading
app/application/services/memory_write_service.py  # Add outbox events
app/infrastructure/db/migrations/versions/0005_memory_system.py  # Uncomment ivfflat index
app/settings.py                      # Add memory config options
app/main.py                          # Register memory router
```

---

## Effort Estimation

| Phase | Tasks | Story Points | Duration |
|-------|-------|--------------|----------|
| Phase 1: Retrieval & Cleanup | 6.1, 6.2, 6.3 | 16 | 3 days |
| Phase 2: Redis & Session | 6.4, 6.5 | 13 | 3 days |
| Phase 3: API & Integration | 6.6, 6.7, 6.8 | 16 | 4 days |
| Phase 4: Testing | 6.9 | 13 | 4 days |
| Phase 5: Docs & Observability | 6.10 | 3 | 1 day |
| **Total** | | **61** | **15 days (3 weeks)** |

---

## Next Steps

1. **Immediate**: Start Task 6.1 (Memory Retrieval Service) - unblocks API and worker integration
2. **Parallel**: Task 6.3 (Vector Index) - can be done by DB engineer
3. **After 6.1**: Task 6.6 (API) and Task 6.7 (Worker) in parallel
4. **After 6.4**: Task 6.5 (Session Service) depends on Redis cache
5. **Continuous**: Task 6.9 (Testing) - write tests alongside implementation
6. **Final**: Task 6.10 (Documentation)

---

*This plan assumes a team of 2-3 engineers. Adjust task assignments based on team capacity.*