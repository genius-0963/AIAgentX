# Sprint 2: Core Domain and Database Layer

**Sprint Goal:** Implement the core domain model, database schema, and repository layer with tenant isolation and proper data relationships.

**Duration:** 3 weeks  
**Priority:** Critical - Core business logic foundation  
**Risk Level:** Medium - Complex domain modeling with data integrity requirements

---

## Sprint Overview

This sprint establishes the core domain model and database persistence layer. We will implement the domain entities, value objects, and aggregates that define the business logic of AIAgentX. The database schema will support multi-tenancy, proper relationships, and data integrity. Repository patterns will abstract database operations and provide clean interfaces for the application layer.

---

## User Stories

### US-2.1: Core Domain Entities and Aggregates
**As a** developer  
**I want** well-defined domain entities and aggregates with clear invariants  
**So that** business logic is encapsulated and data integrity is maintained

**Acceptance Criteria:**
- Tenant aggregate with proper invariants (suspended tenants cannot create runs)
- AgentDefinition aggregate with versioning support
- ToolGrant aggregate with policy validation
- Run aggregate with state machine invariants
- RunStep aggregate with sequence guarantees
- MemoryRecord aggregate with tenant filtering
- Domain events for state transitions
- Clear separation between entities and value objects

### US-2.2: Database Schema with Multi-Tenancy
**As a** platform operator  
**I want** a PostgreSQL schema with proper multi-tenancy support  
**So that** tenant data is isolated and secure

**Acceptance Criteria:**
- All tenant-owned tables include `tenant_id UUID NOT NULL`
- Composite indexes beginning with `tenant_id` for performance
- Foreign key relationships properly defined
- Check constraints for data validation
- Row-level security (RLS) policies for tenant isolation
- Proper indexing for query patterns
- Database migrations for schema changes

### US-2.3: Repository Pattern Implementation
**As a** developer  
**I want** repository interfaces that abstract database operations  
**So that** the application layer is decoupled from database implementation

**Acceptance Criteria:**
- Repository interfaces defined as protocols
- SQLAlchemy implementations of repositories
- Async repository methods for all operations
- Proper transaction management
- Error handling and transformation
- Unit tests for repository logic
- Integration tests with PostgreSQL

### US-2.4: Run State Machine Implementation
**As a** developer  
**I want** a robust state machine for run lifecycle management  
**So that** run state transitions are controlled and auditable

**Acceptance Criteria:**
- All defined states implemented (queued, running, awaiting_approval, retry_scheduled, succeeded, failed, cancelled, timed_out)
- State transition rules enforced
- State transition events emitted
- Terminal state immutability guaranteed
- Worker lease handling for running states
- Cancellation request handling
- State transition audit logging

### US-2.5: Authentication and Authorization Foundation
**As a** security architect  
**I want** basic authentication and authorization mechanisms  
**So that** API access is controlled and tenant-scoped

**Acceptance Criteria:**
- User entity with authentication credentials
- API key entity with scoped permissions
- JWT token validation for user authentication
- API key validation for service authentication
- Role-based access control (RBAC) foundation
- Permission checking middleware
- Tenant context propagation
- Authentication unit and integration tests

### US-2.6: Agent Definition CRUD Operations
**As a** developer  
**I want** full CRUD operations for agent definitions  
**So that** agents can be created, updated, and managed through the API

**Acceptance Criteria:**
- Create agent definition with validation
- Update agent definition (creates new version)
- Publish agent definition (immutable published version)
- Delete agent definition (soft delete)
- List agent definitions with tenant filtering
- Get agent definition by ID
- Version history tracking
- Input validation and sanitization

---

## Technical Tasks

### 2.1 Domain Model Implementation
- [ ] Define domain entities (Tenant, AgentDefinition, ToolGrant, Run, RunStep, MemoryRecord)
- [ ] Implement value objects (Money, TokenUsage, State)
- [ ] Create aggregate roots with invariants
- [ ] Implement domain events system
- [ ] Create domain service interfaces
- [ ] Write unit tests for domain logic
- [ ] Document domain model decisions

### 2.2 Database Schema
- [ ] Create PostgreSQL migration for core tables
- [ ] Implement tenant_id in all tenant-owned tables
- [ ] Create composite indexes with tenant_id
- [ ] Define foreign key relationships
- [ ] Add check constraints for data validation
- [ ] Implement row-level security policies
- [ ] Create database migration scripts
- [ ] Test schema with sample data

### 2.3 Repository Implementation
- [ ] Define repository protocols (TenantRepository, AgentRepository, RunRepository, etc.)
- [ ] Implement SQLAlchemy repository classes
- [ ] Create async database session management
- [ ] Implement transaction context managers
- [ ] Add error handling and transformation
- [ ] Write unit tests for repositories
- [ ] Write integration tests with PostgreSQL
- [ ] Test repository performance

### 2.4 State Machine Implementation
- [ ] Define run state enum and transitions
- [ ] Implement state transition validator
- [ ] Create state transition event system
- [ ] Implement worker lease logic
- [ ] Add cancellation request handling
- [ ] Create state transition audit logging
- [ ] Write unit tests for state transitions
- [ ] Test edge cases and error conditions

### 2.5 Authentication Foundation
- [ ] Create User entity with password hashing
- [ ] Implement API key entity with scopes
- [ ] Add JWT token generation and validation
- [ ] Create API key validation middleware
- [ ] Implement RBAC permission system
- [ ] Add tenant context propagation
- [ ] Write authentication unit tests
- [ ] Write authentication integration tests

### 2.6 Agent Definition CRUD
- [ ] Create agent definition repository
- [ ] Implement create operation with validation
- [ ] Implement update operation with versioning
- [ ] Implement publish operation with immutability
- [ ] Implement soft delete operation
- [ ] Create list and get operations
- [ ] Add input validation and sanitization
- [ ] Write CRUD operation tests
- [ ] Test version history tracking

---

## Database Schema

### Core Tables

```sql
-- Tenants
CREATE TABLE tenants (
  id UUID PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  plan TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'deleted')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  email TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, email)
);

-- API Keys
CREATE TABLE api_keys (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  key_hash TEXT NOT NULL,
  scopes JSONB NOT NULL,
  name TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agents
CREATE TABLE agents (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

-- Agent Versions
CREATE TABLE agent_versions (
  id UUID PRIMARY KEY,
  agent_id UUID NOT NULL REFERENCES agents(id),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  version INTEGER NOT NULL,
  system_prompt TEXT NOT NULL,
  model_policy JSONB NOT NULL,
  memory_mode TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (agent_id, version)
);

-- Tool Grants
CREATE TABLE tool_grants (
  id UUID PRIMARY KEY,
  agent_version_id UUID NOT NULL REFERENCES agent_versions(id),
  tool_name TEXT NOT NULL,
  policy_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (agent_version_id, tool_name)
);

-- Runs
CREATE TABLE runs (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  agent_version_id UUID NOT NULL REFERENCES agent_versions(id),
  state TEXT NOT NULL CHECK (state IN ('queued','running','awaiting_approval','retry_scheduled','succeeded','failed','cancelled','timed_out')),
  input_json JSONB NOT NULL,
  output_json JSONB,
  idempotency_key TEXT NOT NULL,
  attempt SMALLINT NOT NULL DEFAULT 0,
  max_steps SMALLINT NOT NULL,
  max_cost_microunits BIGINT NOT NULL,
  spent_cost_microunits BIGINT NOT NULL DEFAULT 0,
  lease_owner TEXT,
  lease_expires_at TIMESTAMPTZ,
  cancel_requested_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);

-- Run Steps
CREATE TABLE run_steps (
  id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES runs(id),
  sequence INTEGER NOT NULL,
  kind TEXT NOT NULL,
  state TEXT NOT NULL,
  input_redacted JSONB,
  output_redacted JSONB,
  error_redacted TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_id, sequence)
);
```

---

## Definition of Done

**For each user story:**
- [ ] All acceptance criteria are met
- [ ] Domain model is well-structured and tested
- [ ] Database schema is normalized and properly indexed
- [ ] Repository pattern is correctly implemented
- [ ] State machine handles all edge cases
- [ ] Authentication is secure and tested
- [ ] CRUD operations are complete and validated
- [ ] Code is reviewed and approved
- [ ] Documentation is updated

**For the sprint:**
- [ ] All user stories completed
- [ ] Domain model unit tests pass (95%+ coverage)
- [ ] Database integration tests pass
- [ ] Repository tests pass
- [ ] State machine tests cover all transitions
- [ ] Authentication tests pass
- [ ] Performance benchmarks meet requirements
- [ ] Database migrations tested in all environments
- [ ] Sprint retrospective completed

---

## Risks and Dependencies

**Risks:**
- **Medium Risk:** Complex domain modeling may require iteration
- **Data Migration:** Schema changes may be needed as understanding deepens
- **Performance:** Complex queries may require optimization
- **Multi-tenancy:** Tenant isolation must be thoroughly tested

**Dependencies:**
- Sprint 1 must be completed (foundation and scaffolding)
- PostgreSQL database must be available
- Database migration framework must be working
- Team must understand domain-driven design principles

---

## Success Metrics

- Domain model covers all business requirements
- Database schema supports multi-tenancy with proper isolation
- Repository operations complete within performance SLAs
- State machine handles all defined transitions correctly
- Authentication and authorization work securely
- CRUD operations function correctly with proper validation
- Unit test coverage for domain layer exceeds 90%
- Integration tests with PostgreSQL pass consistently
- Database queries perform within acceptable timeframes

---

## Notes

**Senior Tech Lead Guidance:**
- Invest time in proper domain modeling - it's the foundation of the entire system
- Ensure multi-tenancy is implemented correctly from the start - retrofitting is expensive
- Use domain events to decouple aggregates and improve maintainability
- Implement proper indexing strategies based on query patterns
- Test database performance with realistic data volumes
- Document all domain invariants and business rules clearly

**Engineering Considerations:**
- Use SQLAlchemy 2 with async support throughout
- Implement proper connection pooling for database performance
- Use database transactions appropriately for data consistency
- Consider using UUIDs for all primary keys
- Implement proper error handling for database operations
- Use database-level constraints where appropriate for data integrity
- Plan for data migration strategies from the start

**Security Considerations:**
- Implement row-level security for tenant isolation
- Never expose tenant_id in API responses
- Use parameterized queries to prevent SQL injection
- Implement proper password hashing for user credentials
- API keys should be hashed before storage
- Audit all authentication and authorization events