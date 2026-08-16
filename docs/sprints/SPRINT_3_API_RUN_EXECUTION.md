# Sprint 3: API Layer and Run Execution

**Sprint Goal:** Implement the HTTP API layer, run creation, queueing system, worker execution framework, and server-sent events for real-time progress updates.

**Duration:** 3 weeks  
**Priority:** Critical - Core API functionality and execution engine  
**Risk Level:** Medium-High - Complex distributed execution with state management

---

## Sprint Overview

This sprint implements the external API surface and the core run execution system. We will build the REST API endpoints for agent and run management, implement the run queueing system with Redis, create the worker execution framework with lease management, and establish server-sent events for real-time progress streaming. This sprint enables the core functionality of creating and executing agent runs.

---

## User Stories

### US-3.1: HTTP API Endpoints for Agent Management
**As a** developer  
**I want** REST API endpoints for agent management  
**So that** agents can be created, published, and managed programmatically

**Acceptance Criteria:**
- `POST /v1/agents` - Creates draft agent definition version 1
- `POST /v1/agents/{id}/publish` - Validates tool grants and publishes current draft version
- `GET /v1/agents` - Lists agent definitions with tenant filtering
- `GET /v1/agents/{id}` - Returns agent definition details
- `PUT /v1/agents/{id}` - Updates agent definition (creates new version)
- `DELETE /v1/agents/{id}` - Soft deletes agent definition
- All endpoints require `agents:write` or `agents:read` scope
- Proper authentication and authorization
- Input validation and error handling
- OpenAPI documentation for all endpoints

### US-3.2: Run Creation and Idempotency
**As a** developer  
**I want** to create runs with idempotency guarantees  
**So that** duplicate requests don't create duplicate runs

**Acceptance Criteria:**
- `POST /v1/agents/{id}/runs` - Creates a queued run
- Requires `Idempotency-Key` header (UUID or 32-128 char opaque string)
- Returns `202 Accepted` with run ID and events URL
- Duplicate idempotency keys return original run
- Input validation for run parameters
- Tenant-scoped run creation
- Proper error responses (RFC 7807 compatible)
- Run creation validates agent version is published

### US-3.3: Run Query and Status API
**As a** developer  
**I want** to query run status and results  
**So that** I can monitor execution progress and retrieve results

**Acceptance Criteria:**
- `GET /v1/runs/{id}` - Returns durable state, redacted output, usage summary
- Requires `runs:read` scope
- Returns run state, input/output (redacted), usage metrics
- Proper tenant isolation
- 404 response for non-existent runs
- Caching for frequently accessed runs
- Input validation for run ID format

### US-3.4: Server-Sent Events for Real-Time Updates
**As a** developer  
**I want** SSE streaming of run events  
**So that** I can monitor execution progress in real-time

**Acceptance Criteria:**
- `GET /v1/runs/{id}/events` - SSE stream with event updates
- Supports `Last-Event-ID` for reconnection resume
- Events include: `run.queued`, `step.started`, `model.delta`, `tool.approval_required`, `tool.completed`, `run.completed`, `run.failed`
- Numeric monotonic event IDs
- Typed event names
- Proper tenant isolation
- Connection timeout handling
- Event persistence before publishing

### US-3.5: Run Cancellation API
**As a** developer  
**I want** to request run cancellation  
**So that** I can stop runaway or unwanted executions

**Acceptance Criteria:**
- `POST /v1/runs/{id}/cancel` - Requests cancellation
- Requires `runs:write` scope
- Returns current run state
- Sets `cancel_requested_at` atomically
- Workers check cancellation before model calls and tool calls
- Cancellation is best-effort for in-progress operations
- Proper error handling for already completed runs

### US-3.6: Redis Queue and Worker Lease System
**As a** platform operator  
**I want** a Redis-backed queue with worker lease management  
**So that** runs are processed reliably by multiple workers

**Acceptance Criteria:**
- Redis queue for run processing
- Worker lease claim mechanism with `SELECT ... FOR UPDATE SKIP LOCKED` pattern
- Lease expiration and renewal logic
- Lease conflict detection and handling
- Queue age monitoring
- Worker registration and heartbeat
- Lease recovery sweeper for expired leases
- Proper Redis connection management

### US-3.7: Worker Execution Framework
**As a** developer  
**I want** a worker framework for executing runs  
**So that** runs can be processed asynchronously

**Acceptance Criteria:**
- Dramatiq worker setup with Redis backend
- Worker bootstrapping and configuration
- Run executor with state machine implementation
- Lease renewal during execution
- Cancellation checking at appropriate points
- Error handling and recovery
- Worker shutdown graceful handling
- Worker health monitoring

### US-3.8: API Error Contract and Response Formatting
**As a** developer  
**I want** consistent error responses across all endpoints  
**So that** API consumers can handle errors predictably

**Acceptance Criteria:**
- RFC 7807 compatible error responses
- Error responses include: `type`, `title`, `status`, `detail`, `request_id`, `code`
- Stable error codes for different error scenarios
- Proper HTTP status codes
- Request ID propagation
- Error logging and monitoring
- Error documentation in OpenAPI spec

---

## Technical Tasks

### 3.1 Agent Management API
- [ ] Create API route handlers for agent endpoints
- [ ] Implement Pydantic schemas for request/response
- [ ] Add authentication and authorization middleware
- [ ] Implement input validation
- [ ] Create service layer for agent operations
- [ ] Add error handling and transformation
- [ ] Write unit tests for API endpoints
- [ ] Write integration tests for API endpoints
- [ ] Update OpenAPI documentation

### 3.2 Run Creation and Idempotency
- [ ] Create run creation API endpoint
- [ ] Implement idempotency key validation
- [ ] Add run validation logic
- [ ] Implement duplicate request handling
- [ ] Create run service layer
- [ ] Add database transaction management
- [ ] Write unit tests for idempotency
- [ ] Write integration tests for run creation
- [ ] Test idempotency scenarios

### 3.3 Run Query API
- [ ] Create run query endpoint
- [ ] Implement tenant isolation
- [ ] Add output redaction logic
- [ ] Implement usage summary calculation
- [ ] Add caching layer
- [ ] Write unit tests for query endpoint
- [ ] Write integration tests for query operations
- [ ] Test error scenarios

### 3.4 Server-Sent Events
- [ ] Create SSE endpoint implementation
- [ ] Implement event persistence
- [ ] Add `Last-Event-ID` resume support
- [ ] Create event publisher service
- [ ] Implement event types and formatting
- [ ] Add connection management
- [ ] Write unit tests for SSE logic
- [ ] Write integration tests for SSE streaming
- [ ] Test reconnection scenarios

### 3.5 Run Cancellation
- [ ] Create cancellation endpoint
- [ ] Implement atomic cancellation request
- [ ] Add cancellation signal propagation
- [ ] Implement worker cancellation checking
- [ ] Add cancellation validation
- [ ] Write unit tests for cancellation
- [ ] Write integration tests for cancellation flow
- [ ] Test cancellation at different execution stages

### 3.6 Redis Queue System
- [ ] Implement Redis queue setup
- [ ] Create lease claim mechanism
- [ ] Implement lease renewal logic
- [ ] Add lease expiration handling
- [ ] Create worker registration system
- [ ] Implement queue age monitoring
- [ ] Create lease recovery sweeper
- [ ] Write unit tests for queue operations
- [ ] Write integration tests with Redis
- [ ] Test lease conflict scenarios

### 3.7 Worker Framework
- [ ] Set up Dramatiq with Redis backend
- [ ] Create worker bootstrapping
- [ ] Implement run executor
- [ ] Add state machine execution logic
- [ ] Implement lease renewal
- [ ] Add cancellation checking
- [ ] Implement graceful shutdown
- [ ] Create worker health monitoring
- [ ] Write unit tests for worker logic
- [ ] Write integration tests for worker execution

### 3.8 Error Contract
- [ ] Define error response schema
- [ ] Create error code constants
- [ ] Implement error response builder
- [ ] Add request ID middleware
- [ ] Implement error logging
- [ ] Create error handler middleware
- [ ] Write unit tests for error responses
- [ ] Document error codes and scenarios
- [ ] Update OpenAPI spec with error responses

---

## API Contract Examples

### Run Creation
```http
POST /v1/agents/ag_123/runs
Idempotency-Key: 8940a0e0-3fc2-481d-8b81-23aa7865fc31
Authorization: Bearer <api_key>

{
  "input": {"question": "Summarize this release"},
  "session_id": "s_456",
  "metadata": {"source": "web"},
  "limits": {
    "max_steps": 12,
    "max_cost_usd": 0.25,
    "timeout_seconds": 90
  }
}

202 Accepted
{
  "id": "run_01J...",
  "state": "queued",
  "agent_version": 3,
  "events_url": "/v1/runs/run_01J.../events"
}
```

### Error Response
```http
400 Bad Request
Content-Type: application/problem+json

{
  "type": "https://api.aiagentx.com/errors/validation-error",
  "title": "Validation Error",
  "status": 400,
  "detail": "max_steps must be between 1 and 50",
  "request_id": "req_abc123",
  "code": "VALIDATION_ERROR"
}
```

### SSE Event Stream
```
data: {"id": 1, "event": "run.queued", "data": {"run_id": "run_01J...", "timestamp": "2024-01-15T10:00:00Z"}}

data: {"id": 2, "event": "step.started", "data": {"step_id": "step_01J...", "kind": "model", "timestamp": "2024-01-15T10:00:01Z"}}

data: {"id": 3, "event": "model.delta", "data": {"content": "I'll analyze", "timestamp": "2024-01-15T10:00:02Z"}}
```

---

## Definition of Done

**For each user story:**
- [ ] All acceptance criteria are met
- [ ] API endpoints are fully functional
- [ ] Authentication and authorization work correctly
- [ ] Input validation is comprehensive
- [ ] Error handling is consistent
- [ ] OpenAPI documentation is complete
- [ ] Unit tests pass with good coverage
- [ ] Integration tests pass
- [ ] Code is reviewed and approved

**For the sprint:**
- [ ] All user stories completed
- [ ] API contract tests pass
- [ ] Worker execution framework works end-to-end
- [ ] Redis queue operations are reliable
- [ ] SSE streaming works correctly
- [ ] Cancellation mechanism works as expected
- [ ] Error responses are consistent
- [ ] Performance meets requirements
- [ ] Security review completed
- [ ] Sprint retrospective completed

---

## Risks and Dependencies

**Risks:**
- **Medium-High Risk:** Distributed execution complexity
- **State Management:** Concurrent access to run state requires careful handling
- **Performance:** SSE streaming under high load may need optimization
- **Redis Reliability:** Queue system depends on Redis availability
- **Worker Coordination:** Multiple workers need proper coordination

**Dependencies:**
- Sprint 1 and 2 must be completed
- PostgreSQL database must be available
- Redis must be available and configured
- Authentication system must be working
- Domain model must be stable

---

## Success Metrics

- API endpoints respond within 200ms (p95)
- Run creation completes within 500ms
- SSE events are delivered within 100ms of occurrence
- Worker lease claims complete within 50ms
- Queue age stays below 60 seconds under normal load
- Cancellation requests are processed within 1 second
- Error responses are consistent and well-documented
- API contract tests pass 100%
- Integration tests pass consistently
- System can handle 100 concurrent API requests

---

## Notes

**Senior Tech Lead Guidance:**
- Focus on API consistency and contract stability
- Implement proper idempotency from the start - it's critical for distributed systems
- SSE implementation should be robust to network interruptions
- Worker lease management must handle edge cases (network partitions, worker crashes)
- Error responses should be informative but not expose internal details
- Monitor queue age and worker health closely

**Engineering Considerations:**
- Use async/await throughout the API layer
- Implement proper connection pooling for database and Redis
- Use background tasks for non-blocking operations
- Consider rate limiting for API endpoints
- Implement proper timeout handling for all external calls
- Use structured logging for API operations
- Monitor API performance and error rates

**Security Considerations:**
- Validate all input parameters strictly
- Never expose internal state in error messages
- Implement proper authentication for all endpoints
- Use tenant isolation consistently
- Rate limit authentication endpoints
- Audit all API access attempts
- Implement proper CORS policies
- Never expose sensitive data in API responses

**Performance Considerations:**
- Cache frequently accessed data
- Use database connection pooling
- Implement proper indexing for query patterns
- Monitor API response times
- Optimize SSE event delivery
- Consider pagination for list endpoints
- Use compression for large responses