# AIAgentX Architecture Documentation

## Overview

AIAgentX follows **Clean Architecture** and **Domain-Driven Design (DDD)** principles to create a maintainable, testable, and scalable AI agent orchestration platform. The architecture enforces strict dependency inversion, keeping business logic independent of frameworks and external concerns.

## Architectural Principles

### Clean Architecture Layers

```mermaid
graph TB
    subgraph "API Layer"
        A1[FastAPI Routers]
        A2[Middleware]
        A3[Error Handlers]
        A4[SSE Streaming]
    end
    
    subgraph "Application Layer"
        B1[Use Cases]
        B2[Services]
        B3[Orchestration]
    end
    
    subgraph "Domain Layer"
        C1[Entities]
        C2[Value Objects]
        C3[Domain Events]
        C4[Repository Ports]
        C5[Domain Services]
    end
    
    subgraph "Infrastructure Layer"
        D1[PostgreSQL + RLS]
        D2[Redis Cache]
        D3[LLM Providers]
        D4[Auth JWT/API Key]
        D5[Observability]
    end
    
    A1 --> B1
    A2 --> B1
    B1 --> C1
    B2 --> C1
    C4 --> D1
    C4 --> D2
    B2 --> D3
    A2 --> D4
    B1 --> D5
```

### Dependency Rule

**Dependencies must only point inward.** The outer layers can depend on inner layers, but inner layers must never depend on outer layers.

- **Domain Layer:** Zero dependencies on other layers
- **Application Layer:** Depends only on Domain Layer
- **API Layer:** Depends on Application and Domain Layers
- **Infrastructure Layer:** Implements interfaces defined in Domain Layer

## Domain-Driven Design Implementation

### Aggregates and Aggregate Roots

```mermaid
classDiagram
    class AggregateRoot {
        +UUID id
        +datetime created_at
        +datetime updated_at
        +List~DomainEvent~ _events
        +touch()
        +add_event()
        +clear_events()
    }
    
    class Entity {
        +UUID id
        +datetime created_at
        +datetime updated_at
        +touch()
    }
    
    class ValueObject {
        +equals()
        +hashCode()
    }
    
    class DomainEvent {
        +datetime occurred_at
        +aggregate_id
        +aggregate_type
    }
    
    AggregateRoot <|-- Entity
    Entity <|-- Agent
    Entity <|-- Run
    ValueObject <|-- Money
    ValueObject <|-- RunState
    DomainEvent <|-- AgentCreated
    DomainEvent <|-- RunCompleted
```

### Core Aggregates

#### Agent Aggregate
- **Aggregate Root:** `Agent`
- **Entities:** `AgentVersion`, `ToolGrant`
- **Value Objects:** `AgentStatus`, `ModelPolicy`
- **Domain Events:** `AgentCreated`, `AgentVersionCreated`, `AgentPublished`, `AgentDeleted`

#### Run Aggregate
- **Aggregate Root:** `Run`
- **Entities:** `RunStep`
- **Value Objects:** `RunState`, `Money`, `TokenUsage`
- **Domain Events:** `RunCreated`, `RunStateChanged`, `RunCompleted`, `RunFailed`, `RunCancelled`

#### Memory Aggregate
- **Aggregate Root:** `MemoryAggregate`
- **Entities:** `MemoryRecord`, `SessionSummary`, `MemoryRetentionPolicy`
- **Value Objects:** `MemoryScope`, `AllowedUseLabel`
- **Domain Events:** `MemoryWritten`, `MemoryRetrieved`

## Component Architecture

### System Component Diagram

```mermaid
graph TB
    subgraph "API Gateway"
        GW[FastAPI Application]
        MW[Middleware Stack]
        RT[API Routers]
    end
    
    subgraph "Application Services"
        UC[Use Cases]
        AS[Application Services]
        CO[Approval Coordinator]
    end
    
    subgraph "Domain Core"
        RE[Repository Interfaces]
        DE[Domain Entities]
        DS[Domain Services]
        VO[Value Objects]
    end
    
    subgraph "Infrastructure"
        DB[(PostgreSQL)]
        RD[(Redis)]
        PR[Provider Adapters]
        AU[Auth Service]
        LO[Logging & Metrics]
    end
    
    subgraph "External Services"
        OAI[OpenAI API]
        ANT[Anthropic API]
        GGL[Google API]
    end
    
    GW --> MW
    MW --> RT
    RT --> UC
    UC --> AS
    UC --> DE
    AS --> DS
    AS --> CO
    UC --> RE
    RE --> DB
    RE --> RD
    AS --> PR
    PR --> OAI
    PR --> ANT
    PR --> GGL
    MW --> AU
    UC --> LO
```

### Repository Pattern Implementation

```mermaid
classDiagram
    class AgentRepository {
        <<interface>>
        +create(Agent) Agent
        +get(UUID) Agent|None
        +get_by_name(UUID, str) Agent|None
        +list(UUID, int, int) List~Agent~
        +update(Agent) Agent
        +soft_delete(UUID) bool
    }
    
    class SQLAgentRepository {
        -AsyncSession _session
        +create(Agent) Agent
        +get(UUID) Agent|None
        +get_by_name(UUID, str) Agent|None
        +list(UUID, int, int) List~Agent~
        +update(Agent) Agent
        +soft_delete(UUID) bool
    }
    
    class RunRepository {
        <<interface>>
        +create(Run) Run
        +get(UUID) Run|None
        +get_by_idempotency_key(UUID, str) Run|None
        +list(UUID, RunState, UUID, int, int) List~Run~
        +update(Run) Run
        +update_step(UUID, RunStep) void
    }
    
    class SQLRunRepository {
        -AsyncSession _session
        +create(Run) Run
        +get(UUID) Run|None
        +get_by_idempotency_key(UUID, str) Run|None
        +list(UUID, RunState, UUID, int, int) List~Run~
        +update(Run) Run
        +update_step(UUID, RunStep) void
    }
    
    AgentRepository <|.. SQLAgentRepository
    RunRepository <|.. SQLRunRepository
```

## Event-Driven Architecture

### Outbox Pattern

```mermaid
sequenceDiagram
    participant Entity as Domain Entity
    participant Repository as Repository
    participant Outbox as Outbox Table
    participant Flusher as Outbox Flusher
    participant EventBus as Event Bus
    
    Entity->>Entity: add_event(DomainEvent)
    Entity->>Repository: save()
    Repository->>Repository: Begin Transaction
    Repository->>Outbox: insert(event)
    Repository->>Repository: Commit Transaction
    Repository-->>Entity: success
    
    loop Polling
        Flusher->>Outbox: fetch_pending_events()
        Outbox-->>Flusher: events
        Flusher->>EventBus: publish(events)
        EventBus-->>Flusher: success
        Flusher->>Outbox: mark_as_delivered()
    end
```

### Domain Events Flow

```mermaid
graph LR
    A[Domain Event] --> B[Outbox Table]
    B --> C[Outbox Flusher]
    C --> D[Event Bus]
    D --> E[Event Handlers]
    E --> F[Side Effects]
    
    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#e8f5e9
    style D fill:#f3e5f5
    style E fill:#fce4ec
    style F fill:#e0f2f1
```

## Multi-Tenant Architecture

### Tenant Isolation Strategy

```mermaid
graph TB
    subgraph "Request Processing"
        R[Incoming Request]
        A[Authentication]
        T[Tenant Resolution]
    end
    
    subgraph "Data Access Layer"
        RL[Row-Level Security]
        Q[Tenant-Scoped Queries]
        V[Tenant Validation]
    end
    
    subgraph "Data Storage"
        PG[(PostgreSQL with RLS)]
        RD[(Redis Namespaced)]
    end
    
    R --> A
    A --> T
    T --> RL
    RL --> Q
    Q --> V
    V --> PG
    T --> RD
```

### Row-Level Security (RLS) Implementation

AIAgentX uses PostgreSQL's Row-Level Security to enforce tenant isolation at the database level:

```sql
-- Example RLS Policy
CREATE POLICY tenant_isolation ON agents
    FOR ALL
    TO aiagentx_app
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

## CQRS Implementation

### Command Query Separation

```mermaid
classDiagram
    class Command {
        <<interface>>
        +execute() Result
    }
    
    class Query {
        <<interface>>
        +execute() Result
    }
    
    class CreateAgentCommand {
        +tenant_id: UUID
        +name: str
        +description: str
        +execute() Agent
    }
    
    class GetAgentQuery {
        +agent_id: UUID
        +tenant_id: UUID
        +execute() Agent|None
    }
    
    class ListAgentsQuery {
        +tenant_id: UUID
        +limit: int
        +offset: int
        +execute() List~Agent~
    }
    
    Command <|.. CreateAgentCommand
    Query <|.. GetAgentQuery
    Query <|.. ListAgentsQuery
```

## Service Layer Architecture

### Application Services

```mermaid
graph TB
    subgraph "Application Services"
        BS[Budget Service]
        CS[Cancellation Service]
        FS[Fallback Service]
        MS[Memory Services]
        TS[Tool Execution Service]
        AS[Audit Logger Service]
    end
    
    subgraph "Domain Services"
        AC[Approval Coordinator]
    end
    
    subgraph "Infrastructure Services"
        RC[Redis Client]
        EC[Encryption Service]
        HS[Health Monitor]
    end
    
    BS --> RC
    CS --> RC
    FS --> RC
    MS --> RC
    TS --> AC
    AS --> RC
    MS --> EC
    FS --> HS
```

## Dependency Injection

### Service Composition

```mermaid
graph LR
    subgraph "API Layer"
        R1[Agent Router]
        R2[Run Router]
    end
    
    subgraph "Application Layer"
        UC1[Agent Use Cases]
        UC2[Run Use Cases]
        S1[Budget Service]
        S2[Cancellation Service]
    end
    
    subgraph "Domain Layer"
        REP1[Agent Repository]
        REP2[Run Repository]
        DS[Approval Coordinator]
    end
    
    subgraph "Infrastructure Layer"
        DB1[SQL Agent Repository]
        DB2[SQL Run Repository]
        RC[Redis Client]
    end
    
    R1 --> UC1
    R2 --> UC2
    UC1 --> REP1
    UC2 --> REP2
    UC1 --> S1
    UC2 --> S2
    S2 --> DS
    REP1 --> DB1
    REP2 --> DB2
    S1 --> RC
    S2 --> RC
```

## Performance Architecture

### Caching Strategy

```mermaid
graph TB
    subgraph "Multi-Level Cache"
        L1[In-Memory Cache]
        L2[Redis Cache]
        L3[Database Cache]
    end
    
    subgraph "Cache Invalidation"
        CI[Cache Invalidation]
        TTL[Time-Based Expiration]
        EV[Event-Based Invalidation]
    end
    
    subgraph "Cache Patterns"
        CP1[Cache-Aside]
        CP2[Write-Through]
        CP3[Write-Behind]
    end
    
    L1 --> L2
    L2 --> L3
    CI --> L1
    CI --> L2
    TTL --> L1
    TTL --> L2
    EV --> L1
    EV --> L2
    CP1 --> L1
    CP2 --> L2
    CP3 --> L3
```

## Scalability Architecture

### Horizontal Scaling Strategy

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Load Balancer]
    end
    
    subgraph "API Servers"
        API1[API Server 1]
        API2[API Server 2]
        API3[API Server N]
    end
    
    subgraph "Worker Servers"
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker N]
    end
    
    subgraph "Shared Storage"
        PG[(PostgreSQL)]
        RD[(Redis)]
    end
    
    subgraph "Message Queue"
        MQ[Redis Queue]
    end
    
    LB --> API1
    LB --> API2
    LB --> API3
    API1 --> PG
    API2 --> PG
    API3 --> PG
    API1 --> RD
    API2 --> RD
    API3 --> RD
    API1 --> MQ
    API2 --> MQ
    API3 --> MQ
    W1 --> MQ
    W2 --> MQ
    W3 --> MQ
    W1 --> PG
    W2 --> PG
    W3 --> PG
    W1 --> RD
    W2 --> RD
    W3 --> RD
```

## Observability Architecture

### Monitoring and Tracing

```mermaid
graph TB
    subgraph "Application"
        APP[FastAPI App]
        WRK[Workers]
    end
    
    subgraph "Observability Stack"
        LOG[Structured Logging]
        TRC[OpenTelemetry Tracing]
        MET[Prometheus Metrics]
    end
    
    subgraph "Exporters"
        OTEL[OTLP Exporter]
        PROM[Prometheus Exporter]
    end
    
    subgraph "Backends"
        COL[OTLP Collector]
        GRAF[Grafana]
        PROMS[Prometheus Server]
    end
    
    APP --> LOG
    APP --> TRC
    APP --> MET
    WRK --> LOG
    WRK --> TRC
    WRK --> MET
    TRC --> OTEL
    MET --> PROM
    OTEL --> COL
    PROM --> PROMS
    COL --> GRAF
    PROMS --> GRAF
```

## Error Handling Architecture

### Error Propagation Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant UseCase
    participant Domain
    participant Infra
    participant ErrorHandler
    
    Client->>API: Request
    API->>UseCase: Execute
    UseCase->>Domain: Business Logic
    Domain-->>UseCase: Domain Error
    UseCase->>Infra: External Call
    Infra-->>UseCase: Infrastructure Error
    UseCase-->>API: Application Error
    API->>ErrorHandler: Handle Error
    ErrorHandler-->>Client: Error Response
```

### Exception Hierarchy

```mermaid
classDiagram
    class Exception {
        <<base>>
    }
    
    class DomainException {
        <<base>>
        +message: str
    }
    
    class InfrastructureException {
        <<base>>
        +message: str
    }
    
    class ValidationException {
        +field: str
        +value: Any
    }
    
    class NotFoundException {
        +resource_type: str
        +resource_id: str
    }
    
    class ProviderException {
        +provider: str
        +is_retryable: bool
    }
    
    Exception <|-- DomainException
    Exception <|-- InfrastructureException
    DomainException <|-- ValidationException
    DomainException <|-- NotFoundException
    InfrastructureException <|-- ProviderException
```

## Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthMiddleware
    participant JWTService
    participant Repository
    
    Client->>API: Request + JWT/API Key
    API->>AuthMiddleware: Authenticate
    AuthMiddleware->>JWTService: Validate Token
    JWTService-->>AuthMiddleware: Claims
    AuthMiddleware->>Repository: Load User/Tenant
    Repository-->>AuthMiddleware: User/Tenant
    AuthMiddleware-->>API: AuthContext
    API->>API: Process Request
    API-->>Client: Response
```

### Authorization Model

```mermaid
graph TB
    subgraph "Authorization Layers"
        L1[Authentication]
        L2[Tenant Isolation]
        L3[Scope-Based Access]
        L4[Resource-Level Authorization]
    end
    
    subgraph "Enforcement Points"
        E1[API Middleware]
        E2[Repository Layer]
        E3[Domain Logic]
        E4[Tool Execution]
    end
    
    L1 --> E1
    L2 --> E1
    L2 --> E2
    L3 --> E1
    L3 --> E3
    L4 --> E3
    L4 --> E4
```

## Technology Stack

### Core Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Framework** | FastAPI 0.115+ | High-performance async web framework |
| **Database** | PostgreSQL 16+ | Primary data storage with RLS |
| **Cache** | Redis 7+ | Caching and session storage |
| **ORM** | SQLAlchemy 2.0+ | Database abstraction |
| **Async Driver** | AsyncPG | PostgreSQL async driver |
| **Task Queue** | Dramatiq | Background job processing |
| **LLM Providers** | OpenAI, Anthropic, Google | AI model integration |
| **Authentication** | JWT, PyJWT | Token-based authentication |
| **Logging** | Structlog | Structured JSON logging |
| **Tracing** | OpenTelemetry | Distributed tracing |
| **Metrics** | Prometheus | Metrics collection |
| **Testing** | Pytest | Testing framework |
| **Type Checking** | MyPy | Static type analysis |

### Infrastructure Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Containerization** | Docker | Application containerization |
| **Orchestration** | Kubernetes | Container orchestration |
| **Proxy** | Nginx/Ingress | Reverse proxy and load balancing |
| **Monitoring** | Grafana | Visualization and dashboards |
| **Alerting** | Prometheus Alertmanager | Alert management |
| **Log Aggregation** | Loki/Elasticsearch | Log collection and analysis |

## Deployment Architecture

### Container Architecture

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        subgraph "API Deployment"
            POD1[API Pod 1]
            POD2[API Pod 2]
            POD3[API Pod N]
        end
        
        subgraph "Worker Deployment"
            WPOD1[Worker Pod 1]
            WPOD2[Worker Pod 2]
            WPOD3[Worker Pod N]
        end
        
        subgraph "Infrastructure"
            PG[(PostgreSQL)]
            RD[(Redis)]
        end
        
        subgraph "Observability"
            PROM[Prometheus]
            GRAF[Grafana]
            OTEL[OTLP Collector]
        end
    end
    
    ING[Ingress] --> POD1
    ING --> POD2
    ING --> POD3
    POD1 --> PG
    POD2 --> PG
    POD3 --> PG
    POD1 --> RD
    POD2 --> RD
    POD3 --> RD
    WPOD1 --> PG
    WPOD2 --> PG
    WPOD3 --> PG
    WPOD1 --> RD
    WPOD2 --> RD
    WPOD3 --> RD
    POD1 --> PROM
    POD2 --> PROM
    POD3 --> PROM
    WPOD1 --> PROM
    WPOD2 --> PROM
    WPOD3 --> PROM
    PROM --> GRAF
    POD1 --> OTEL
    POD2 --> OTEL
    POD3 --> OTEL
```

## Architecture Decision Records

### Key Architectural Decisions

1. **Clean Architecture over Layered Architecture**
   - **Reason:** Better testability and maintainability
   - **Trade-off:** More boilerplate code initially

2. **PostgreSQL RLS over Application-Level Isolation**
   - **Reason:** Database-level security guarantees
   - **Trade-off:** Vendor lock-in to PostgreSQL

3. **Redis over In-Memory Caching**
   - **Reason:** Distributed caching and persistence
   - **Trade-off:** Additional infrastructure dependency

4. **SSE over WebSocket for Streaming**
   - **Reason:** Simpler implementation, HTTP-friendly
   - **Trade-off:** One-way communication only

5. **Outbox Pattern over Direct Event Publishing**
   - **Reason:** Reliable event delivery
   - **Trade-off:** Eventual consistency

6. **Multi-Provider Abstraction over Single Provider**
   - **Reason:** Vendor independence and fallback capability
   - **Trade-off:** Increased complexity

## Future Architecture Considerations

### Scalability Enhancements
- **Read Replicas:** For scaling read operations
- **Connection Pooling:** Advanced pooling strategies
- **Database Sharding:** For multi-tenant scaling at scale

### Performance Optimizations
- **Query Optimization:** Advanced indexing strategies
- **Materialized Views:** For complex queries
- **Edge Computing:** CDN integration for static assets

### Architecture Evolution
- **Microservices:** Potential split into focused services
- **Event Sourcing:** For complex domain requirements
- **CQRS Enhancement:** Separate read/write models

This architecture documentation provides a comprehensive view of the AIAgentX system architecture, emphasizing clean design principles, domain-driven modeling, and enterprise-grade patterns.