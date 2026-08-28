# AIAgentX Memory System Documentation

## Overview

AIAgentX implements a sophisticated tiered memory system that provides AI agents with different levels of persistence and recall capabilities. The memory system supports three distinct scopes: ephemeral (per-run), session (conversational), and durable (long-term semantic memory), each optimized for specific use cases.

## Memory Architecture Diagram

```mermaid
graph TB
    subgraph "Memory System"
        MEM[Memory System]
    end
    
    subgraph "Ephemeral Memory"
        EPHEMERAL[Ephemeral Memory]
        REDIS[(Redis Cache)]
        RUN_SCOPE[Per-Run Scope]
        TEMP_DATA[Temporary Data]
    end
    
    subgraph "Session Memory"
        SESSION[Session Memory]
        REDIS_SESSION[(Redis Session Cache)]
        DB_SUMMARY[(PostgreSQL Summary)]
        CONVERSATION[Conversational Context]
        SESSION_ID[Session-Based]
    end
    
    subgraph "Durable Memory"
        DURABLE[Durable Memory]
        PG_VECTOR[(PostgreSQL + pgvector)]
        EMBEDDINGS[Embedding Vectors]
        SEMANTIC_SEARCH[Semantic Search]
        LONG_TERM[Long-Term Storage]
    end
    
    subgraph "Memory Services"
        WRITE[Memory Write Service]
        RETRIEVE[Memory Retrieval Service]
        CLEANUP[Memory Cleanup Service]
    end
    
    subgraph "Supporting Services"
        ENCRYPTION[Encryption Service]
        EMBEDDING_GEN[Embedding Generation]
        TEXT_PROCESSING[Text Processing]
    end
    
    MEM --> EPHEMERAL
    MEM --> SESSION
    MEM --> DURABLE
    EPHEMERAL --> REDIS
    EPHEMERAL --> RUN_SCOPE
    RUN_SCOPE --> TEMP_DATA
    SESSION --> REDIS_SESSION
    SESSION --> DB_SUMMARY
    DB_SUMMARY --> CONVERSATION
    CONVERSATION --> SESSION_ID
    DURABLE --> PG_VECTOR
    PG_VECTOR --> EMBEDDINGS
    EMBEDDINGS --> SEMANTIC_SEARCH
    SEMANTIC_SEARCH --> LONG_TERM
    
    WRITE --> ENCRYPTION
    WRITE --> EMBEDDING_GEN
    RETRIEVE --> EMBEDDING_GEN
    RETRIEVE --> TEXT_PROCESSING
    CLEANUP --> TEXT_PROCESSING
```

## Memory Scopes

### Memory Scope Comparison

| Scope | Duration | Storage | Use Case | Performance | Cost |
|-------|----------|---------|----------|-------------|------|
| **Ephemeral** | Single run | Redis | Temporary variables, intermediate results | Highest | Lowest |
| **Session** | Multiple runs | Redis + PostgreSQL | Conversation context, short-term memory | High | Low |
| **Durable** | Long-term | PostgreSQL + pgvector | Knowledge base, long-term learning | Medium | Medium |

### Memory Scope State Machine

```mermaid
stateDiagram-v2
    [*] --> EPHEMERAL: Run Starts
    EPHEMERAL --> SESSION: Run Completes (if session_id)
    EPHEMERAL --> [*]: Run Completes (no session)
    SESSION --> DURABLE: Significant Learning
    SESSION --> [*]: Session Expires
    DURABLE --> DURABLE: New Knowledge Added
    DURABLE --> [*]: Retention Policy Expires
```

## Ephemeral Memory

### Ephemeral Memory Architecture

```mermaid
sequenceDiagram
    participant Run as Run Executor
    participant EphemeralCache as Ephemeral Memory Cache
    participant Redis as Redis
    participant Validation as Validation Service
    
    Run->>EphemeralCache: set(run_id, key, value)
    EphemeralCache->>Validation: validate_input(key, value)
    Validation-->>EphemeralCache: Valid
    EphemeralCache->>Redis: SET run_id:key value
    Redis-->>EphemeralCache: Success
    EphemeralCache-->>Run: Success
    
    Run->>EphemeralCache: get(run_id, key)
    EphemeralCache->>Redis: GET run_id:key
    Redis-->>EphemeralCache: Value
    EphemeralCache-->>Run: Value
    
    Run->>EphemeralCache: get_all(run_id)
    EphemeralCache->>Redis: KEYS run_id:*
    Redis-->>EphemeralCache: All Keys
    EphemeralCache->>Redis: MGET run_id:key1 run_id:key2 ...
    Redis-->>EphemeralCache: All Values
    EphemeralCache-->>Run: All Key-Value Pairs
    
    Note over Run,Redis: Run Completes
    Run->>EphemeralCache: cleanup(run_id)
    EphemeralCache->>Redis: DEL run_id:*
    Redis-->>EphemeralCache: Deleted
    EphemeralCache-->>Run: Cleanup Complete
```

### Ephemeral Memory Characteristics

- **Storage:** Redis in-memory data store
- **Scope:** Individual run execution
- **TTL:** Configured to match run timeout
- **Data Types:** Strings, numbers, JSON objects
- **Capacity:** Limited by Redis memory
- **Performance:** Sub-millisecond access times
- **Persistence:** Optional Redis persistence
- **Cleanup:** Automatic on run completion

### Ephemeral Memory Usage Examples

```python
# During run execution
await ephemeral_cache.set(run_id, "intermediate_result", calculation_result)
await ephemeral_cache.set(run_id, "step_count", current_step)
await ephemeral_cache.set(run_id, "user_preferences", user_settings)

# Retrieval during execution
result = await ephemeral_cache.get(run_id, "intermediate_result")
all_data = await ephemeral_cache.get_all(run_id)
```

## Session Memory

### Session Memory Architecture

```mermaid
sequenceDiagram
    participant Run as Run Executor
    participant SessionService as Session Memory Service
    participant Redis as Redis Cache
    participant DB as PostgreSQL
    participant Embedding as Embedding Service
    participant Encryption as Encryption Service
    
    Run->>SessionService: write_session_memory(tenant_id, agent_id, session_id, content)
    SessionService->>Encryption: encrypt(content, tenant_key)
    Encryption-->>SessionService: ciphertext
    SessionService->>Embedding: generate_embedding(content)
    Embedding-->>SessionService: embedding_vector
    SessionService->>Redis: SET session:session_id:messages ciphertext
    Redis-->>SessionService: Success
    SessionService->>DB: INSERT INTO session_summaries
    DB-->>SessionService: Success
    SessionService-->>Run: Success
    
    Run->>SessionService: get_session_context(tenant_id, agent_id, session_id, limit)
    SessionService->>Redis: GET session:session_id:summary
    Redis-->>SessionService: Summary
    SessionService->>DB: SELECT * FROM memory_records WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
    DB-->>SessionService: Session Records
    SessionService->>Encryption: decrypt(records)
    Encryption-->>SessionService: plaintext
    SessionService-->>Run: Session Context
```

### Session Memory Components

#### Redis Session Cache
- **Key Pattern:** `session:{session_id}:{type}`
- **Data Types:** 
  - Messages: List of conversation messages
  - Summary: Compressed session summary
  - Metadata: Session metadata
- **TTL:** Configurable session timeout
- **Eviction:** LRU eviction when memory pressure

#### PostgreSQL Session Storage
- **Table:** `session_summaries`
- **Fields:** session_id, tenant_id, agent_id, summary_ciphertext, metadata
- **Indexing:** session_id, tenant_id, created_at
- **Retention:** Configurable retention policy

### Session Memory Lifecycle

```mermaid
stateDiagram-v2
    [*] --> ACTIVE: Session Created
    ACTIVE --> ACTIVE: Messages Added
    ACTIVE --> IDLE: No Activity (timeout)
    IDLE --> ACTIVE: New Activity
    ACTIVE --> ARCHIVED: Session Expiration
    ARCHIVED --> [*]: Cleanup
    ACTIVE --> SUMMARIZED: Summary Generated
    SUMMARIZED --> ACTIVE: Continue Session
```

### Session Memory Features

- **Conversation Context:** Maintains conversation history
- **Summarization:** Automatic summarization of long sessions
- **Context Window:** Configurable context window size
- **Memory Consolidation:** Consolidates similar information
- **Session Management:** Session creation, retrieval, cleanup
- **Cross-Run Persistence:** Maintains context across multiple runs

## Durable Memory

### Durable Memory Architecture

```mermaid
graph TB
    subgraph "Durable Memory Pipeline"
        INPUT[Input Content]
        PREPROCESS[Text Preprocessing]
        CHUNK[Text Chunking]
        EMBED[Embedding Generation]
        ENCRYPT[Encryption]
        STORE[(PostgreSQL + pgvector)]
        INDEX[Vector Index]
    end
    
    subgraph "Retrieval Pipeline"
        QUERY[User Query]
        QUERY_EMBED[Query Embedding]
        SIMILARITY[Similarity Search]
        RANK[Relevance Ranking]
        DECRYPT[Decryption]
        OUTPUT[Retrieved Context]
    end
    
    INPUT --> PREPROCESS
    PREPROCESS --> CHUNK
    CHUNK --> EMBED
    EMBED --> ENCRYPT
    ENCRYPT --> STORE
    STORE --> INDEX
    
    QUERY --> QUERY_EMBED
    QUERY_EMBED --> SIMILARITY
    SIMILARITY --> INDEX
    INDEX --> RANK
    RANK --> DECRYPT
    DECRYPT --> OUTPUT
```

### Durable Memory Schema

```sql
CREATE TABLE memory_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    scope VARCHAR(20) NOT NULL,
    namespace VARCHAR(100) NOT NULL,
    content_ciphertext TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    allowed_use_label VARCHAR(20) DEFAULT 'public',
    session_id VARCHAR(100),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector index for similarity search
CREATE INDEX memory_records_embedding_idx ON memory_records 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Tenant and scope indexes
CREATE INDEX memory_records_tenant_scope_idx ON memory_records (tenant_id, scope);
CREATE INDEX memory_records_agent_idx ON memory_records (agent_id);
CREATE INDEX memory_records_session_idx ON memory_records (session_id) WHERE session_id IS NOT NULL;
CREATE INDEX memory_records_expires_at_idx ON memory_records (expires_at) WHERE expires_at IS NOT NULL;
```

### Embedding Generation

```mermaid
sequenceDiagram
    participant MemoryService as Memory Service
    participant EmbeddingService as Embedding Service
    participant OpenAI as OpenAI API
    participant Cache as Embedding Cache
    
    MemoryService->>EmbeddingService: generate_embedding(text)
    EmbeddingService->>Cache: check_cache(text_hash)
    Cache-->>EmbeddingService: Cache Miss
    EmbeddingService->>EmbeddingService: preprocess_text(text)
    EmbeddingService->>OpenAI: POST /v1/embeddings
    OpenAI-->>EmbeddingService: embedding_vector
    EmbeddingService->>Cache: store_cache(text_hash, embedding_vector)
    Cache-->>EmbeddingService: Success
    EmbeddingService-->>MemoryService: embedding_vector
```

### Semantic Search Implementation

```mermaid
sequenceDiagram
    participant Run as Run Executor
    participant RetrievalService as Memory Retrieval Service
    participant EmbeddingService as Embedding Service
    participant DB as PostgreSQL
    participant Encryption as Encryption Service
    
    Run->>RetrievalService: retrieve_memory(tenant_id, agent_id, query, scope, limit)
    RetrievalService->>EmbeddingService: generate_embedding(query)
    EmbeddingService-->>RetrievalService: query_embedding
    RetrievalService->>DB: SELECT id, content_ciphertext, embedding, metadata FROM memory_records WHERE tenant_id = ? AND agent_id = ? AND scope = ? ORDER BY embedding <=> query_embedding LIMIT ?
    DB-->>RetrievalService: Similar Records with Similarity Scores
    RetrievalService->>Encryption: decrypt_batch(content_ciphertexts)
    Encryption-->>RetrievalService: plaintext_contents
    RetrievalService->>RetrievalService: rank_by_relevance(similarity_scores, metadata)
    RetrievalService-->>Run: Ranked Memory Records
```

### Text Processing Pipeline

```mermaid
graph TB
    subgraph "Text Processing"
        RAW[Raw Text]
        NORMALIZE[Normalization]
        CLEAN[Cleaning]
        CHUNK[Chunking]
        FILTER[Filtering]
        PROCESSED[Processed Chunks]
    end
    
    subgraph "Processing Steps"
        LOWER[Lowercasing]
        TRIM[Whitespace Trimming]
        REMOVE_SPECIAL[Special Character Removal]
        SPLIT[Split into Chunks]
        OVERLAP[Add Overlap]
        DEDUP[Duplicate Removal]
        QUALITY[Quality Filtering]
    end
    
    RAW --> NORMALIZE
    NORMALIZE --> LOWER
    LOWER --> TRIM
    TRIM --> REMOVE_SPECIAL
    REMOVE_SPECIAL --> CLEAN
    CLEAN --> CHUNK
    CHUNK --> SPLIT
    SPLIT --> OVERLAP
    OVERLAP --> FILTER
    FILTER --> DEDUP
    DEDUP --> QUALITY
    QUALITY --> PROCESSED
```

### Memory Retrieval Strategies

| Strategy | Description | Use Case | Performance |
|----------|-------------|----------|-------------|
| **Semantic Search** | Vector similarity search | Conceptual queries | Medium |
| **Keyword Search** | Full-text search | Specific terms | Fast |
| **Hybrid Search** | Combined semantic + keyword | Balanced approach | Medium |
| **Temporal Search** | Time-based retrieval | Recent information | Fast |
| **Namespace Search** | Namespace-specific | Organized retrieval | Fast |

## Memory Security

### Data Classification

```mermaid
graph TB
    subgraph "Data Classification"
        PUBLIC[Public]
        INTERNAL[Internal]
        CONFIDENTIAL[Confidential]
        RESTRICTED[Restricted]
    end
    
    subgraph "Classification Rules"
        RULE1[User-Generated Content]
        RULE2[System Information]
        RULE3[Business Data]
        RULE4[PII/Sensitive Data]
    end
    
    subgraph "Protection Levels"
        LEVEL1[Basic Encryption]
        LEVEL2[Strong Encryption]
        LEVEL3[Strong Encryption + Access Controls]
        LEVEL4[Maximum Security + Audit Trail]
    end
    
    RULE1 --> PUBLIC
    RULE2 --> INTERNAL
    RULE3 --> CONFIDENTIAL
    RULE4 --> RESTRICTED
    
    PUBLIC --> LEVEL1
    INTERNAL --> LEVEL2
    CONFIDENTIAL --> LEVEL3
    RESTRICTED --> LEVEL4
```

### Encryption Strategy

- **Algorithm:** AES-256-GCM for content encryption
- **Key Management:** Tenant-specific encryption keys
- **Key Rotation:** Automatic key rotation (90 days)
- **Scope:** All sensitive memory content encrypted
- **Performance:** Optimized encryption operations

### Access Control

```mermaid
sequenceDiagram
    participant Run as Run Executor
    participant MemoryService as Memory Service
    participant Auth as Authorization Service
    participant Repo as Memory Repository
    
    Run->>MemoryService: access_memory(tenant_id, memory_id)
    MemoryService->>Auth: check_access(tenant_id, memory_id, 'read')
    Auth->>Repo: get_memory_record(memory_id)
    Repo-->>Auth: Memory Record
    Auth->>Auth: check_tenant_match(tenant_id, record.tenant_id)
    Auth->>Auth: check_data_classification(record.allowed_use_label)
    
    alt Access Granted
        Auth-->>MemoryService: Access Granted
        MemoryService-->>Run: Memory Content
    else Access Denied
        Auth-->>MemoryService: Access Denied
        MemoryService-->>Run: Access Denied Error
    end
```

## Memory Cleanup and Retention

### Retention Policy

```mermaid
graph TB
    subgraph "Retention Policies"
        EPHEMERAL_POLICY[Ephemeral: Run Duration]
        SESSION_POLICY[Session: 24-72 hours]
        DURABLE_POLICY[Durable: Configurable]
    end
    
    subgraph "Cleanup Triggers"
        TRIGGER1[Run Completion]
        TRIGGER2[Session Expiration]
        TRIGGER3[Retention Limit]
        TRIGGER4[Manual Cleanup]
    end
    
    subgraph "Cleanup Actions"
        ACTION1[Redis Key Deletion]
        ACTION2[Database Record Deletion]
        ACTION3[Vector Index Cleanup]
        ACTION4[Audit Logging]
    end
    
    EPHEMERAL_POLICY --> TRIGGER1
    SESSION_POLICY --> TRIGGER2
    DURABLE_POLICY --> TRIGGER3
    TRIGGER4 --> ACTION1
    TRIGGER1 --> ACTION1
    TRIGGER2 --> ACTION2
    TRIGGER3 --> ACTION3
    ACTION3 --> ACTION4
```

### Retention Configuration

| Scope | Default Retention | Maximum Retention | Cleanup Strategy |
|-------|------------------|-------------------|------------------|
| Ephemeral | Run duration | 24 hours | Immediate on completion |
| Session | 24 hours | 72 hours | Scheduled cleanup |
| Durable | 90 days | 365 days | Scheduled cleanup |

### Memory Quotas

```python
# Memory quota configuration
class MemoryQuota:
    max_records_per_tenant: int = 10000
    max_storage_mb_per_tenant: int = 1000
    max_embeddings_per_tenant: int = 100000
    max_session_duration_hours: int = 72
```

## Memory Performance Optimization

### Caching Strategy

```mermaid
graph TB
    subgraph "Cache Layers"
        L1[In-Memory Cache]
        L2[Redis Cache]
        L3[Database Cache]
    end
    
    subgraph "Cache Policies"
        POLICY1[LRU Eviction]
        POLICY2[TTL Expiration]
        POLICY3[Size-Based Eviction]
    end
    
    subgraph "Cache Invalidation"
        INVALID1[Time-Based]
        INVALID2[Event-Based]
        INVALID3[Manual Invalidation]
    end
    
    L1 --> POLICY1
    L2 --> POLICY2
    L3 --> POLICY3
    POLICY1 --> INVALID1
    POLICY2 --> INVALID2
    POLICY3 --> INVALID3
```

### Performance Characteristics

| Operation | Ephemeral | Session | Durable |
|-----------|-----------|---------|---------|
| Write | <1ms | 5-10ms | 50-100ms |
| Read | <1ms | 2-5ms | 20-50ms |
| Search | N/A | 10-20ms | 50-200ms |
| Delete | <1ms | 5-10ms | 20-50ms |

## Memory Usage Patterns

### Common Usage Patterns

#### Pattern 1: Conversation Memory
```python
# Store conversation in session memory
await memory_write_service.write_memory(
    tenant_id=tenant_id,
    agent_id=agent_id,
    content=user_message,
    scope=MemoryScope.SESSION,
    namespace="conversation",
    metadata={"role": "user", "timestamp": now()},
    session_id=session_id
)
```

#### Pattern 2: Knowledge Storage
```python
# Store knowledge in durable memory
await memory_write_service.write_memory(
    tenant_id=tenant_id,
    agent_id=agent_id,
    content=knowledge_text,
    scope=MemoryScope.DURABLE,
    namespace="knowledge_base",
    metadata={"category": "technical", "importance": "high"}
)
```

#### Pattern 3: Temporary State
```python
# Store temporary state in ephemeral memory
await ephemeral_cache.set(run_id, "processing_state", "intermediate_result")
```

#### Pattern 4: Context Retrieval
```python
# Retrieve relevant context for query
relevant_memory = await memory_retrieval_service.retrieve_memory(
    tenant_id=tenant_id,
    agent_id=agent_id,
    query=user_query,
    scope=MemoryScope.DURABLE,
    namespace="knowledge_base",
    limit=5
)
```

## Memory Monitoring and Observability

### Memory Metrics

```mermaid
graph TB
    subgraph "Memory Metrics"
        STORAGE[Storage Metrics]
        PERFORMANCE[Performance Metrics]
        QUALITY[Quality Metrics]
        USAGE[Usage Metrics]
    end
    
    subgraph "Storage Metrics"
        TOTAL_STORAGE[Total Storage Used]
        STORAGE_PER_TENANT[Storage per Tenant]
        STORAGE_PER_SCOPE[Storage per Scope]
    end
    
    subgraph "Performance Metrics"
        WRITE_LATENCY[Write Latency]
        READ_LATENCY[Read Latency]
        SEARCH_LATENCY[Search Latency]
        CACHE_HIT_RATIO[Cache Hit Ratio]
    end
    
    subgraph "Quality Metrics"
        EMBEDDING_QUALITY[Embedding Quality]
        RETRIEVAL_PRECISION[Retrieval Precision]
        RETRIEVAL_RECALL[Retrieval Recall]
    end
    
    subgraph "Usage Metrics"
        MEMORY_OPERATIONS[Memory Operations]
        UNIQUE_USERS[Unique Users]
        ACTIVE_SESSIONS[Active Sessions]
    end
    
    STORAGE --> TOTAL_STORAGE
    STORAGE --> STORAGE_PER_TENANT
    STORAGE --> STORAGE_PER_SCOPE
    PERFORMANCE --> WRITE_LATENCY
    PERFORMANCE --> READ_LATENCY
    PERFORMANCE --> SEARCH_LATENCY
    PERFORMANCE --> CACHE_HIT_RATIO
    QUALITY --> EMBEDDING_QUALITY
    QUALITY --> RETRIEVAL_PRECISION
    QUALITY --> RETRIEVAL_RECALL
    USAGE --> MEMORY_OPERATIONS
    USAGE --> UNIQUE_USERS
    USAGE --> ACTIVE_SESSIONS
```

### Monitoring Dashboards

- **Storage Overview:** Total storage, tenant breakdown, scope distribution
- **Performance Dashboard:** Latency metrics, cache performance, query patterns
- **Quality Metrics:** Embedding quality, retrieval effectiveness
- **Usage Analytics:** Active sessions, popular namespaces, access patterns

## Memory Configuration

### Environment Configuration

```env
# Memory Configuration
MEMORY_ENABLED=true
EPHEMERAL_MEMORY_ENABLED=true
SESSION_MEMORY_ENABLED=true
DURABLE_MEMORY_ENABLED=true

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_MEMORY_DB=1
REDIS_SESSION_DB=2

# Embedding Configuration
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
EMBEDDING_CACHE_ENABLED=true

# Durable Memory Configuration
DURABLE_MEMORY_RETENTION_DAYS=90
DURABLE_MEMORY_MAX_RECORDS_PER_TENANT=10000
DURABLE_MEMORY_MAX_STORAGE_MB_PER_TENANT=1000

# Vector Search Configuration
VECTOR_INDEX_TYPE=ivfflat
VECTOR_INDEX_LISTS=100
SIMILARITY_THRESHOLD=0.7
MAX_RETRIEVAL_RESULTS=10
```

This memory system documentation provides comprehensive coverage of the tiered memory architecture, including detailed implementation details, security considerations, performance characteristics, and usage patterns for all memory scopes in AIAgentX.