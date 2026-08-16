# Sprint 6: Memory and Retrieval System

**Sprint Goal:** Implement the memory system with ephemeral, session, and durable modes, including vector embeddings, semantic search, and proper tenant isolation for memory data.

**Duration:** 3 weeks  
**Priority:** High - Core AI capability for context-aware agents  
**Risk Level:** Medium-High - Complex data management with security implications

---

## Sprint Overview

This sprint implements the memory and retrieval system that enables agents to maintain context across interactions. We will create three memory modes (ephemeral, session, durable), implement vector embeddings for semantic search, add data classification and redaction, and ensure proper tenant isolation for all memory operations. This system is critical for building context-aware AI agents while maintaining security and privacy.

---

## User Stories

### US-6.1: Ephemeral Memory Mode
**As a** developer  
**I want** ephemeral in-memory storage for single-run context  
**So that** agents can maintain context during a single execution

**Acceptance Criteria:**
- In-memory storage per run
- Redis session cache for reliability
- TTL configuration (default 24 hours)
- Automatic expiration
- Memory isolation between runs
- Context retrieval within run
- Memory persistence during worker execution
- Unit tests for ephemeral memory
- Integration tests with Redis

### US-6.2: Session Memory Mode
**As a** developer  
**I want** session-based memory that persists across multiple runs  
**So that** agents can maintain conversational continuity

**Acceptance Criteria:**
- Redis and PostgreSQL hybrid storage
- Session-based memory organization
- Configurable TTL per tenant
- Session management and cleanup
- Cross-run context retrieval
- Session summarization for efficiency
- Encrypted storage for sensitive data
- Unit tests for session memory
- Integration tests for session continuity

### US-6.3: Durable Memory Mode with Vector Search
**As a** developer  
**I want** durable memory with semantic search capabilities  
**So that** agents can access long-term knowledge and preferences

**Acceptance Criteria:**
- PostgreSQL with pgvector for storage
- Vector embeddings for semantic search
- Tenant isolation for all memory operations
- Retention policy enforcement
- Namespace and metadata support
- Semantic search with similarity ranking
- Encryption for sensitive content
- Index optimization for performance
- Unit tests for durable memory
- Integration tests with pgvector

### US-6.4: Memory Write Pipeline
**As a** developer  
**I want** a robust memory write pipeline with validation and redaction  
**So that** memory data is clean, classified, and secure

**Acceptance Criteria:**
- Input normalization (UTF-8, size limits)
- Sensitive data classification
- Tenant-configured redaction
- Text chunking (400-800 tokens with overlap)
- Source and metadata preservation
- Embedding generation through provider adapter
- Content encryption before storage
- Outbox event for write operations
- Unit tests for write pipeline
- Integration tests for redaction

### US-6.5: Memory Retrieval Query System
**As a** developer  
**I want** a flexible memory retrieval system with filtering  
**So that** agents can access relevant context efficiently

**Acceptance Criteria:**
- Vector similarity search
- Tenant, agent, and namespace filtering
- Expiration predicate filtering
- Session-based retrieval
- Maximum result limit (default 8 for v1)
- Distance and source ID in results
- Content redaction based on policy
- Query performance optimization
- Unit tests for retrieval queries
- Integration tests for search accuracy

### US-6.6: Memory Security and Tenant Isolation
**As a** security architect  
**I want** strict tenant isolation for all memory operations  
**So that** tenants cannot access each other's memory data

**Acceptance Criteria:**
- Mandatory tenant filter in all queries
- Row-level security for memory tables
- Encryption at application layer
- Tenant-specific encryption keys
- Audit logging for memory access
- Memory access authorization checks
- Data residency compliance
- Negative tests for isolation violations
- Security review completed
- Penetration testing for memory access

### US-6.7: Memory Management and Cleanup
**As a** platform operator  
**I want** automated memory management and cleanup  
**So that** memory storage doesn't grow unbounded

**Acceptance Criteria:**
- Configurable retention policies per tenant
- Scheduled cleanup jobs for expired memory
- Memory usage monitoring and alerting
- Storage optimization and compaction
- Backup and restore procedures
- Memory deletion with audit trail
- Cleanup failure handling
- Storage quota enforcement
- Unit tests for cleanup logic
- Integration tests for retention policies

---

## Technical Tasks

### 6.1 Ephemeral Memory Implementation
- [ ] Define ephemeral memory data structures
- [ ] Implement in-memory storage per run
- [ ] Add Redis session cache integration
- [ ] Implement TTL configuration
- [ ] Create memory isolation logic
- [ ] Add context retrieval methods
- [ ] Implement worker execution memory persistence
- [ ] Write unit tests for ephemeral memory
- [ ] Write integration tests with Redis
- [ ] Test memory isolation between runs

### 6.2 Session Memory Implementation
- [ ] Define session memory data structures
- [ ] Implement Redis session storage
- [ ] Add PostgreSQL session summary storage
- [ ] Create session management logic
- [ ] Implement session cleanup
- [ ] Add cross-run context retrieval
- [ ] Implement session summarization
- [ ] Add encryption for sensitive session data
- [ ] Write unit tests for session memory
- [ ] Write integration tests for session continuity

### 6.3 Durable Memory with Vector Search
- [ ] Set up PostgreSQL with pgvector extension
- [ ] Create memory tables with vector columns
- [ ] Implement vector embedding generation
- [ ] Create vector similarity search
- [ ] Add tenant isolation enforcement
- [ ] Implement retention policy logic
- [ ] Add namespace and metadata support
- [ ] Create vector indexes for performance
- [ ] Write unit tests for durable memory
- [ ] Write integration tests with pgvector

### 6.4 Memory Write Pipeline
- [ ] Implement input normalization
- [ ] Create sensitive data classifier
- [ ] Implement redaction logic
- [ ] Add text chunking algorithm
- [ ] Implement metadata preservation
- [ ] Create embedding generation service
- [ ] Add content encryption
- [ ] Implement outbox event publishing
- [ ] Write unit tests for write pipeline
- [ ] Write integration tests for redaction

### 6.5 Memory Retrieval System
- [ ] Implement vector similarity search
- [ ] Add tenant and agent filtering
- [ ] Create namespace filtering
- [ ] Implement expiration predicate
- [ ] Add session-based retrieval
- [ ] Implement result limiting
- [ ] Add content redaction for results
- [ ] Optimize query performance
- [ ] Write unit tests for retrieval
- [ ] Write integration tests for search accuracy

### 6.6 Memory Security Implementation
- [ ] Implement mandatory tenant filtering
- [ ] Add row-level security policies
- [ ] Create application-layer encryption
- [ ] Implement tenant-specific encryption keys
- [ ] Add audit logging for memory access
- [ ] Create memory authorization checks
- [ ] Implement data residency compliance
- [ ] Write negative tests for isolation
- [ ] Conduct security review
- [ ] Perform penetration testing

### 6.7 Memory Management Implementation
- [ ] Define retention policy configuration
- [ ] Implement scheduled cleanup jobs
- [ ] Add memory usage monitoring
- [ ] Create storage optimization logic
- [ ] Implement backup and restore procedures
- [ ] Add memory deletion with audit trail
- [ ] Create cleanup failure handling
- [ ] Implement storage quota enforcement
- [ ] Write unit tests for cleanup
- [ ] Write integration tests for retention

---

## Database Schema for Memory

```sql
-- Memory Records (Durable Mode)
CREATE TABLE memory_records (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  agent_id UUID NOT NULL,
  scope TEXT NOT NULL, -- 'durable', 'session', 'ephemeral'
  namespace TEXT NOT NULL,
  content_ciphertext TEXT NOT NULL,
  embedding vector(1536), -- OpenAI embedding dimension
  metadata JSONB NOT NULL,
  allowed_use_label TEXT NOT NULL,
  session_id TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for vector search and filtering
CREATE INDEX memory_records_tenant_agent_idx ON memory_records (tenant_id, agent_id);
CREATE INDEX memory_records_namespace_idx ON memory_records (namespace);
CREATE INDEX memory_records_expires_at_idx ON memory_records (expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX memory_records_embedding_idx ON memory_records USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Session Summaries
CREATE TABLE session_summaries (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  agent_id UUID NOT NULL,
  session_id TEXT NOT NULL,
  summary_ciphertext TEXT NOT NULL,
  metadata JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, agent_id, session_id)
);

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Memory Write Pipeline

```python
async def write_memory(
    tenant_id: str,
    agent_id: str,
    content: str,
    scope: MemoryScope,
    namespace: str,
    metadata: dict,
    session_id: Optional[str] = None
) -> MemoryRecord:
    """Memory write pipeline with validation and redaction"""
    
    # 1. Normalize input
    normalized_content = normalize_text(content)
    if len(normalized_content) > MAX_MEMORY_SIZE:
        raise MemorySizeExceededError()
    
    # 2. Classify and redact sensitive data
    classification = await classifier.classify(normalized_content, tenant_id)
    redacted_content = await redactor.redact(normalized_content, classification, tenant_id)
    
    # 3. Chunk content
    chunks = chunk_text(redacted_content, chunk_size=600, overlap=0.1)
    
    records = []
    for chunk in chunks:
        # 4. Generate embedding
        embedding = await embedding_service.generate(chunk, tenant_id)
        
        # 5. Encrypt content
        ciphertext = await encryption_service.encrypt(chunk, tenant_id)
        
        # 6. Create record
        record = MemoryRecord(
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=scope,
            namespace=namespace,
            content_ciphertext=ciphertext,
            embedding=embedding,
            metadata=metadata,
            allowed_use_label=classification.allowed_use,
            session_id=session_id,
            expires_at=calculate_expiry(scope, tenant_id)
        )
        
        # 7. Persist and enqueue event
        saved_record = await memory_repository.save(record)
        await outbox.enqueue("memory.written", saved_record.id)
        records.append(saved_record)
    
    return records
```

---

## Memory Retrieval Query

```python
async def retrieve_memory(
    tenant_id: str,
    agent_id: str,
    query: str,
    namespace: str,
    scope: MemoryScope,
    limit: int = 8,
    session_id: Optional[str] = None
) -> list[MemoryRecord]:
    """Retrieve memory with semantic search and filtering"""
    
    # 1. Generate query embedding
    query_embedding = await embedding_service.generate(query, tenant_id)
    
    # 2. Build query with filters
    where_clauses = [
        "tenant_id = $1",
        "agent_id = $2",
        "scope = $3",
        "namespace = $4"
    ]
    
    params = [tenant_id, agent_id, scope, namespace]
    
    # 3. Add session filter if provided
    if session_id:
        where_clauses.append("session_id = $5")
        params.append(session_id)
    
    # 4. Add expiration filter
    where_clauses.append("(expires_at IS NULL OR expires_at > NOW())")
    
    # 5. Execute vector similarity search
    query_sql = f"""
        SELECT id, content_ciphertext, metadata, 
               1 - (embedding <=> $6) as similarity
        FROM memory_records
        WHERE {' AND '.join(where_clauses)}
        ORDER BY embedding <=> $6
        LIMIT $7
    """
    
    params.extend([query_embedding, limit])
    
    results = await db.execute(query_sql, *params)
    
    # 6. Decrypt and redact based on policy
    decrypted_results = []
    for result in results:
        decrypted = await encryption_service.decrypt(
            result.content_ciphertext, 
            tenant_id
        )
        
        # Apply policy-based redaction
        if not policy.allow_raw_content(tenant_id, namespace):
            decrypted = "[REDACTED]"
        
        decrypted_results.append({
            "id": result.id,
            "content": decrypted,
            "metadata": result.metadata,
            "similarity": result.similarity
        })
    
    return decrypted_results
```

---

## Definition of Done

**For each user story:**
- [ ] All acceptance criteria are met
- [ ] Ephemeral memory works for single runs
- [ ] Session memory maintains continuity
- [ ] Durable memory supports semantic search
- [ ] Write pipeline validates and redacts data
- [ ] Retrieval system is accurate and efficient
- [ ] Security and isolation are enforced
- [ ] Memory management keeps storage bounded
- [ ] Unit tests pass with good coverage
- [ ] Integration tests pass
- [ ] Security review completed
- [ ] Code is reviewed and approved

**For the sprint:**
- [ ] All user stories completed
- [ ] All three memory modes work correctly
- [ ] Vector search provides accurate results
- [ ] Tenant isolation is enforced in all operations
- [ ] Memory data is properly encrypted
- [ ] Cleanup jobs maintain storage bounds
- [ ] Performance meets requirements
- [ ] Security review and penetration testing completed
- [ ] Documentation is updated
- [ ] Sprint retrospective completed

---

## Risks and Dependencies

**Risks:**
- **Medium-High Risk:** Memory security and tenant isolation are critical
- **Vector Search Performance:** May need optimization for large datasets
- **Data Classification:** Sensitive data detection may have false positives/negatives
- **Encryption Overhead:** May impact performance
- **pgvector Extension:** Requires PostgreSQL extension installation

**Dependencies:**
- Sprint 1-5 must be completed
- PostgreSQL with pgvector extension must be available
- Encryption service must be implemented
- Tenant isolation infrastructure must be in place
- Provider adapter must support embedding generation

---

## Success Metrics

- Memory write latency under 100ms (p95)
- Memory retrieval latency under 200ms (p95)
- Vector search accuracy exceeds 90% for relevant queries
- Tenant isolation prevents 100% of cross-tenant access
- Encryption protects 100% of sensitive memory data
- Cleanup jobs keep storage within 10% of quota
- Memory data classification accuracy exceeds 95%
- System can handle 10,000 memory records per tenant
- Security review passes with no critical findings
- Penetration testing shows no memory access vulnerabilities

---

## Notes

**Senior Tech Lead Guidance:**
- Memory security is critical - invest heavily in tenant isolation
- Vector search performance may need tuning based on data volume
- Start with conservative retention policies and expand based on usage
- Memory encryption adds overhead - monitor performance impact
- Data classification should be configurable per tenant
- Monitor memory usage patterns to optimize storage and retrieval

**Engineering Considerations:**
- Use pgvector for efficient similarity search
- Implement proper indexing for query patterns
- Consider caching for frequently accessed memory
- Use connection pooling for database operations
- Monitor memory growth and optimize storage
- Implement proper backup procedures for memory data
- Test with realistic data volumes

**Security Considerations:**
- Tenant isolation must be enforced at multiple layers
- Encrypt all sensitive memory data at rest
- Never log raw memory content
- Implement proper key management for encryption
- Audit all memory access operations
- Test tenant isolation with negative tests
- Comply with data residency requirements

**Performance Considerations:**
- Vector search can be expensive - optimize indexes
- Consider materialized views for common queries
- Implement proper caching strategies
- Monitor memory operation latency
- Optimize chunk size for embeddings
- Use connection pooling for database operations
- Consider read replicas for memory queries