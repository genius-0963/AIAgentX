# AIAgentX API Reference Documentation

## Overview

AIAgentX provides a comprehensive REST API for managing AI agents, executing runs, and accessing system resources. The API follows RESTful principles and includes features like authentication, authorization, rate limiting, idempotency, and real-time streaming.

## API Architecture

### API Endpoint Organization

```mermaid
graph TB
    subgraph "API Gateway"
        BASE[https://api.aiagentx.com]
    end
    
    subgraph "Health Endpoints"
        HEALTHZ[/healthz]
        READYZ[/readyz]
        METRICS[/metrics]
    end
    
    subgraph "Agent Management"
        AGENTS[/v1/agents]
        AGENT_ID[/v1/agents/{id}]
        AGENT_VERSIONS[/v1/agents/{id}/versions]
        AGENT_VERSION[/v1/agents/{id}/versions/{version}]
        AGENT_PUBLISH[/v1/agents/{id}/versions/{version}/publish]
        TOOL_GRANTS[/v1/agents/{id}/versions/{version}/tool-grants]
    end
    
    subgraph "Run Execution"
        RUNS[/v1/runs]
        RUN_ID[/v1/runs/{id}]
        RUN_EVENTS[/v1/runs/{id}/events]
        RUN_CANCEL[/v1/runs/{id}/cancel]
    end
    
    subgraph "Memory Operations"
        MEMORY[/v1/memory]
        MEMORY_RETRIEVE[/v1/memory/retrieve]
        MEMORY_WRITE[/v1/memory/write]
    end
    
    subgraph "Approval System"
        APPROVALS[/v1/approvals]
        APPROVAL_ID[/v1/approvals/{id}]
        APPROVAL_ACTION[/v1/approvals/{id}/approve]
        APPROVAL_DENY[/v1/approvals/{id}/deny]
    end
    
    subgraph "Audit and Monitoring"
        AUDIT[/v1/audit]
        USAGE[/v1/usage]
    end
    
    BASE --> HEALTHZ
    BASE --> READYZ
    BASE --> METRICS
    BASE --> AGENTS
    BASE --> RUNS
    BASE --> MEMORY
    BASE --> APPROVALS
    BASE --> AUDIT
    BASE --> USAGE
    
    AGENTS --> AGENT_ID
    AGENTS --> AGENT_VERSIONS
    AGENT_VERSIONS --> AGENT_VERSION
    AGENT_VERSION --> AGENT_PUBLISH
    AGENT_VERSION --> TOOL_GRANTS
    
    RUNS --> RUN_ID
    RUN_ID --> RUN_EVENTS
    RUN_ID --> RUN_CANCEL
    
    MEMORY --> MEMORY_RETRIEVE
    MEMORY --> MEMORY_WRITE
    
    APPROVALS --> APPROVAL_ID
    APPROVAL_ID --> APPROVAL_ACTION
    APPROVAL_ID --> APPROVAL_DENY
```

## Authentication

### Authentication Methods

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthMiddleware
    participant JWTService
    participant APIKeyService
    
    alt JWT Authentication
        Client->>API: Request + Authorization: Bearer {token}
        API->>AuthMiddleware: authenticate()
        AuthMiddleware->>JWTService: validate_token(token)
        JWTService-->>AuthMiddleware: Claims
        AuthMiddleware-->>API: AuthContext
    else API Key Authentication
        Client->>API: Request + X-API-Key: {key}
        API->>AuthMiddleware: authenticate()
        AuthMiddleware->>APIKeyService: validate_key(key)
        APIKeyService-->>AuthMiddleware: Claims
        AuthMiddleware-->>API: AuthContext
    end
```

### Authentication Headers

#### JWT Authentication
```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### API Key Authentication
```http
X-API-Key: aiak_live_1234567890abcdef
```

### Authentication Response

**Success (200 OK)**
```json
{
  "authenticated": true,
  "user_id": "uuid",
  "tenant_id": "uuid",
  "scopes": ["agents:read", "agents:write", "runs:execute"]
}
```

**Failure (401 Unauthorized)**
```json
{
  "error": "authentication_failed",
  "message": "Invalid or expired token",
  "code": "AUTH_FAILED"
}
```

## Health Endpoints

### Health Check

**Endpoint:** `GET /healthz`

**Description:** Liveness probe - checks if the API server is running without external dependencies.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0"
}
```

### Readiness Check

**Endpoint:** `GET /readyz`

**Description:** Readiness probe - checks if the API server is ready to accept requests, including database and cache connectivity.

**Response:**
```json
{
  "status": "ready",
  "timestamp": "2024-01-01T00:00:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "providers": "healthy"
  }
}
```

## Agent Management

### Create Agent

**Endpoint:** `POST /v1/agents`

**Authentication:** Requires `agents:write` scope

**Request Body:**
```json
{
  "name": "research-assistant",
  "description": "An AI research assistant with web search capabilities"
}
```

**Response (201 Created):**
```json
{
  "id": "agent-uuid",
  "tenant_id": "tenant-uuid",
  "name": "research-assistant",
  "description": "An AI research assistant with web search capabilities",
  "versions": [],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### List Agents

**Endpoint:** `GET /v1/agents`

**Authentication:** Requires `agents:read` scope

**Query Parameters:**
- `limit` (optional, default: 50, max: 100)
- `offset` (optional, default: 0)

**Response (200 OK):**
```json
{
  "agents": [
    {
      "id": "agent-uuid",
      "tenant_id": "tenant-uuid",
      "name": "research-assistant",
      "description": "An AI research assistant",
      "versions": [],
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### Get Agent

**Endpoint:** `GET /v1/agents/{id}`

**Authentication:** Requires `agents:read` scope

**Response (200 OK):**
```json
{
  "id": "agent-uuid",
  "tenant_id": "tenant-uuid",
  "name": "research-assistant",
  "description": "An AI research assistant",
  "versions": [
    {
      "id": "version-uuid",
      "agent_id": "agent-uuid",
      "version": 1,
      "system_prompt": "You are a helpful research assistant...",
      "model_policy": {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 4096
      },
      "memory_mode": "session",
      "status": "published",
      "tool_grants": [],
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Update Agent

**Endpoint:** `PATCH /v1/agents/{id}`

**Authentication:** Requires `agents:write` scope

**Request Body:**
```json
{
  "name": "updated-name",
  "description": "Updated description"
}
```

**Response (200 OK):**
```json
{
  "id": "agent-uuid",
  "tenant_id": "tenant-uuid",
  "name": "updated-name",
  "description": "Updated description",
  "versions": [],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T01:00:00Z"
}
```

### Delete Agent

**Endpoint:** `DELETE /v1/agents/{id}`

**Authentication:** Requires `agents:write` scope

**Response (204 No Content)**

## Agent Version Management

### Create Agent Version

**Endpoint:** `POST /v1/agents/{id}/versions`

**Authentication:** Requires `agents:write` scope

**Request Body:**
```json
{
  "version": 2,
  "system_prompt": "You are a helpful research assistant. Use web search to find accurate information.",
  "model_policy": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "memory_mode": "session"
}
```

**Response (201 Created):**
```json
{
  "id": "version-uuid",
  "agent_id": "agent-uuid",
  "tenant_id": "tenant-uuid",
  "version": 2,
  "system_prompt": "You are a helpful research assistant...",
  "model_policy": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "memory_mode": "session",
  "status": "draft",
  "tool_grants": [],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### List Agent Versions

**Endpoint:** `GET /v1/agents/{id}/versions`

**Authentication:** Requires `agents:read` scope

**Response (200 OK):**
```json
{
  "versions": [
    {
      "id": "version-uuid",
      "agent_id": "agent-uuid",
      "version": 1,
      "system_prompt": "You are a helpful research assistant...",
      "model_policy": {
        "provider": "openai",
        "model": "gpt-4o"
      },
      "memory_mode": "session",
      "status": "published",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Get Agent Version

**Endpoint:** `GET /v1/agents/{id}/versions/{version}`

**Authentication:** Requires `agents:read` scope

**Response (200 OK):**
```json
{
  "id": "version-uuid",
  "agent_id": "agent-uuid",
  "version": 1,
  "system_prompt": "You are a helpful research assistant...",
  "model_policy": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "memory_mode": "session",
  "status": "published",
  "tool_grants": [
    {
      "id": "grant-uuid",
      "agent_version_id": "version-uuid",
      "tool_name": "web_search",
      "policy": {
        "allowed_actions": ["search"],
        "allow_by_default": false
      },
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Update Agent Version

**Endpoint:** `PATCH /v1/agents/{id}/versions/{version}`

**Authentication:** Requires `agents:write` scope

**Request Body:**
```json
{
  "system_prompt": "Updated system prompt",
  "model_policy": {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet",
    "temperature": 0.8,
    "max_tokens": 8192
  }
}
```

**Response (200 OK):**
```json
{
  "id": "version-uuid",
  "agent_id": "agent-uuid",
  "version": 1,
  "system_prompt": "Updated system prompt",
  "model_policy": {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet",
    "temperature": 0.8,
    "max_tokens": 8192
  },
  "memory_mode": "session",
  "status": "draft",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T01:00:00Z"
}
```

### Publish Agent Version

**Endpoint:** `POST /v1/agents/{id}/versions/{version}/publish`

**Authentication:** Requires `agents:write` scope

**Response (200 OK):**
```json
{
  "id": "version-uuid",
  "agent_id": "agent-uuid",
  "version": 1,
  "system_prompt": "You are a helpful research assistant...",
  "model_policy": {
    "provider": "openai",
    "model": "gpt-4o"
  },
  "memory_mode": "session",
  "status": "published",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T01:00:00Z"
}
```

### Add Tool Grant

**Endpoint:** `POST /v1/agents/{id}/versions/{version}/tool-grants`

**Authentication:** Requires `agents:write` scope

**Request Body:**
```json
{
  "tool_name": "web_search",
  "policy": {
    "allowed_actions": ["search"],
    "allow_by_default": false
  }
}
```

**Response (201 Created):**
```json
{
  "id": "grant-uuid",
  "agent_version_id": "version-uuid",
  "tool_name": "web_search",
  "policy": {
    "allowed_actions": ["search"],
    "allow_by_default": false
  },
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

## Run Execution

### Create Run

**Endpoint:** `POST /v1/agents/{id}/runs`

**Authentication:** Requires `runs:execute` scope

**Headers:**
- `Idempotency-Key` (required): Unique identifier for idempotency

**Request Body:**
```json
{
  "input_data": {
    "query": "What are the latest developments in AI?"
  },
  "max_steps": 100,
  "max_cost_usd": 10.0,
  "session_id": "session-uuid",
  "metadata": {
    "source": "web_interface"
  }
}
```

**Response (202 Accepted):**
```json
{
  "id": "run-uuid",
  "tenant_id": "tenant-uuid",
  "agent_version_id": "version-uuid",
  "state": "queued",
  "input_data": {
    "query": "What are the latest developments in AI?"
  },
  "idempotency_key": "unique-key-123",
  "max_steps": 100,
  "max_cost_usd": 10.0,
  "spent_cost_usd": 0.0,
  "attempt": 0,
  "session_id": "session-uuid",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Get Run

**Endpoint:** `GET /v1/runs/{id}`

**Authentication:** Requires `runs:read` scope

**Response (200 OK):**
```json
{
  "id": "run-uuid",
  "tenant_id": "tenant-uuid",
  "agent_version_id": "version-uuid",
  "state": "succeeded",
  "input_data": {
    "query": "What are the latest developments in AI?"
  },
  "output_data": {
    "result": "The latest developments in AI include..."
  },
  "idempotency_key": "unique-key-123",
  "max_steps": 100,
  "max_cost_usd": 10.0,
  "spent_cost_usd": 0.15,
  "attempt": 1,
  "steps": [
    {
      "id": "step-uuid",
      "sequence": 1,
      "kind": "model_call",
      "state": "succeeded",
      "input_data": {
        "prompt": "What are the latest developments in AI?"
      },
      "output_data": {
        "response": "Based on my research..."
      },
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:01:00Z"
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:01:00Z"
}
```

### List Runs

**Endpoint:** `GET /v1/runs`

**Authentication:** Requires `runs:read` scope

**Query Parameters:**
- `state` (optional): Filter by state (queued, running, succeeded, failed, cancelled)
- `agent_version_id` (optional): Filter by agent version
- `limit` (optional, default: 50, max: 100)
- `offset` (optional, default: 0)

**Response (200 OK):**
```json
{
  "runs": [
    {
      "id": "run-uuid",
      "tenant_id": "tenant-uuid",
      "agent_version_id": "version-uuid",
      "state": "succeeded",
      "input_data": {},
      "output_data": {},
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:01:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### Stream Run Events (SSE)

**Endpoint:** `GET /v1/runs/{id}/events`

**Authentication:** Requires `runs:read` scope

**Headers:**
- `Last-Event-ID` (optional): Resume from specific event ID

**Response:** Server-Sent Events stream

```
data: {"type":"run_started","run_id":"run-uuid","timestamp":"2024-01-01T00:00:00Z"}

data: {"type":"step_created","step_id":"step-uuid","sequence":1,"kind":"model_call","timestamp":"2024-01-01T00:00:01Z"}

data: {"type":"step_completed","step_id":"step-uuid","sequence":1,"output":"...","timestamp":"2024-01-01T00:00:05Z"}

data: {"type":"run_completed","run_id":"run-uuid","output":"...","timestamp":"2024-01-01T00:00:10Z"}
```

### Cancel Run

**Endpoint:** `POST /v1/runs/{id}/cancel`

**Authentication:** Requires `runs:cancel` scope

**Request Body:**
```json
{
  "reason": "User requested cancellation"
}
```

**Response (200 OK):**
```json
{
  "id": "run-uuid",
  "tenant_id": "tenant-uuid",
  "agent_version_id": "version-uuid",
  "state": "cancelled",
  "cancel_requested_at": "2024-01-01T00:00:15Z",
  "updated_at": "2024-01-01T00:00:15Z"
}
```

## Memory Operations

### Write Memory

**Endpoint:** `POST /v1/memory/write`

**Authentication:** Requires `memory:write` scope

**Request Body:**
```json
{
  "agent_id": "agent-uuid",
  "content": "Important information to remember",
  "scope": "durable",
  "namespace": "knowledge_base",
  "metadata": {
    "category": "technical",
    "importance": "high"
  },
  "session_id": "session-uuid"
}
```

**Response (201 Created):**
```json
{
  "records": [
    {
      "id": "memory-uuid",
      "tenant_id": "tenant-uuid",
      "agent_id": "agent-uuid",
      "scope": "durable",
      "namespace": "knowledge_base",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Retrieve Memory

**Endpoint:** `POST /v1/memory/retrieve`

**Authentication:** Requires `memory:read` scope

**Request Body:**
```json
{
  "agent_id": "agent-uuid",
  "query": "What do you know about AI developments?",
  "scope": "durable",
  "namespace": "knowledge_base",
  "limit": 5
}
```

**Response (200 OK):**
```json
{
  "results": [
    {
      "id": "memory-uuid",
      "content": "The latest developments in AI include...",
      "similarity": 0.95,
      "metadata": {
        "category": "technical",
        "importance": "high"
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

## Approval System

### Get Approval Request

**Endpoint:** `GET /v1/approvals/{id}`

**Authentication:** Requires `tools:read` scope

**Response (200 OK):**
```json
{
  "id": "approval-uuid",
  "tenant_id": "tenant-uuid",
  "run_id": "run-uuid",
  "tool_name": "database_delete",
  "input_data": {
    "table": "users",
    "condition": "id = 1"
  },
  "state": "pending",
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2024-01-01T00:05:00Z"
}
```

### Approve Request

**Endpoint:** `POST /v1/approvals/{id}/approve`

**Authentication:** Requires `tools:approve` scope

**Request Body:**
```json
{
  "response_data": {
    "approved": true,
    "modified_input": {
      "table": "users_archive",
      "condition": "id = 1"
    }
  }
}
```

**Response (200 OK):**
```json
{
  "id": "approval-uuid",
  "state": "approved",
  "response_data": {
    "approved": true,
    "modified_input": {
      "table": "users_archive",
      "condition": "id = 1"
    }
  },
  "approved_at": "2024-01-01T00:02:00Z",
  "updated_at": "2024-01-01T00:02:00Z"
}
```

### Deny Request

**Endpoint:** `POST /v1/approvals/{id}/deny`

**Authentication:** Requires `tools:approve` scope

**Request Body:**
```json
{
  "denial_reason": "Unsafe operation - production data"
}
```

**Response (200 OK):**
```json
{
  "id": "approval-uuid",
  "state": "denied",
  "denial_reason": "Unsafe operation - production data",
  "denied_at": "2024-01-01T00:02:00Z",
  "updated_at": "2024-01-01T00:02:00Z"
}
```

## Error Handling

### Error Response Format

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details"
  },
  "request_id": "request-uuid",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Common Error Codes

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | `validation_error` | Request validation failed |
| 401 | `authentication_failed` | Authentication failed |
| 403 | `forbidden` | Insufficient permissions |
| 404 | `not_found` | Resource not found |
| 409 | `conflict` | Resource conflict |
| 422 | `unprocessable_entity` | Invalid request data |
| 429 | `rate_limit_exceeded` | Rate limit exceeded |
| 500 | `internal_error` | Internal server error |
| 503 | `service_unavailable` | Service temporarily unavailable |

### Rate Limiting

**Rate Limit Headers:**
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
```

**Rate Limit Error (429):**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Try again in 60 seconds.",
  "retry_after": 60
}
```

## Rate Limiting

### Rate Limit Strategy

```mermaid
graph TB
    subgraph "Rate Limiting"
        GLOBAL[Global Rate Limit]
        TENANT[Tenant Rate Limit]
        USER[User Rate Limit]
        ENDPOINT[Endpoint Rate Limit]
    end
    
    subgraph "Rate Limit Algorithms"
        TOKEN_BUCKET[Token Bucket]
        SLIDING_WINDOW[Sliding Window]
        FIXED_WINDOW[Fixed Window]
    end
    
    subgraph "Enforcement"
        ALLOW[Allow Request]
        THROTTLE[Throttle Request]
        BLOCK[Block Request]
    end
    
    GLOBAL --> TOKEN_BUCKET
    TENANT --> SLIDING_WINDOW
    USER --> SLIDING_WINDOW
    ENDPOINT --> FIXED_WINDOW
    TOKEN_BUCKET --> ALLOW
    SLIDING_WINDOW --> THROTTLE
    FIXED_WINDOW --> BLOCK
```

### Rate Limit Configuration

| Scope | Limit | Window | Algorithm |
|-------|-------|--------|-----------|
| Global | 10,000 req/min | 1 minute | Token Bucket |
| Per Tenant | 1,000 req/min | 1 minute | Sliding Window |
| Per User | 100 req/min | 1 minute | Sliding Window |
| Per Endpoint | 50 req/min | 1 minute | Fixed Window |

## Idempotency

### Idempotency Implementation

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant IdempotencyService
    participant Cache
    participant BusinessLogic
    
    Client->>API: POST /v1/agents/{id}/runs<br/>Idempotency-Key: unique-key
    API->>IdempotencyService: check_idempotency(key)
    IdempotencyService->>Cache: get(key)
    
    alt Cache Miss
        Cache-->>IdempotencyService: None
        IdempotencyService-->>API: Proceed
        API->>BusinessLogic: execute_request()
        BusinessLogic-->>API: result
        API->>IdempotencyService: store_result(key, result)
        IdempotencyService->>Cache: set(key, result, ttl)
        API-->>Client: 202 Accepted + result
    else Cache Hit
        Cache-->>IdempotencyService: cached_result
        IdempotencyService-->>API: Return cached
        API-->>Client: 202 Accepted + cached_result
    end
```

### Idempotency Headers

**Request:**
```http
Idempotency-Key: unique-request-identifier-123
```

**Response:**
```http
Idempotency-Replayed: false
Idempotency-Key: unique-request-identifier-123
```

## SSE Streaming

### SSE Connection Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant SSEHandler
    participant RunExecutor
    participant EventPublisher
    
    Client->>API: GET /v1/runs/{id}/events
    API->>SSEHandler: setup_streaming(run_id)
    SSEHandler->>SSEHandler: Validate access
    SSEHandler-->>Client: SSE Connection Established
    
    loop Event Streaming
        RunExecutor->>EventPublisher: publish_event(event)
        EventPublisher->>SSEHandler: receive_event(event)
        SSEHandler->>SSEHandler: format_sse_event(event)
        SSEHandler-->>Client: data: {event_json}
    end
    
    RunExecutor->>EventPublisher: publish_completion()
    EventPublisher->>SSEHandler: receive_event(completion)
    SSEHandler-->>Client: data: {completion_json}
    SSEHandler->>Client: Close SSE stream
```

### SSE Event Types

| Event Type | Description | Data |
|------------|-------------|------|
| `run_started` | Run execution started | run_id, timestamp |
| `step_created` | Step created | step_id, sequence, kind |
| `step_started` | Step execution started | step_id, timestamp |
| `step_completed` | Step completed | step_id, output, timestamp |
| `step_failed` | Step failed | step_id, error, timestamp |
| `tool_call` | Tool call initiated | tool_name, input, timestamp |
| `tool_result` | Tool result received | tool_name, output, timestamp |
| `run_completed` | Run completed | run_id, output, timestamp |
| `run_failed` | Run failed | run_id, error, timestamp |
| `run_cancelled` | Run cancelled | run_id, reason, timestamp |

## API Versioning

### Versioning Strategy

```mermaid
graph TB
    subgraph "API Versions"
        V1[v1 - Current]
        V2[v2 - Future]
        V3[v3 - Future]
    end
    
    subgraph "Version Lifecycle"
        STABLE[Stable]
        DEPRECATED[Deprecated]
        SUNSET[Sunset]
    end
    
    subgraph "Migration Path"
        MIGRATION[Migration Guide]
        COMPATIBILITY[Backward Compatibility]
        BREAKING[Breaking Changes]
    end
    
    V1 --> STABLE
    V2 --> DEPRECATED
    V3 --> SUNSET
    STABLE --> MIGRATION
    DEPRECATED --> COMPATIBILITY
    SUNSET --> BREAKING
```

### Version URL Structure

- Current version: `https://api.aiagentx.com/v1/`
- Version-specific: `https://api.aiagentx.com/v2/`
- Latest version: `https://api.aiagentx.com/latest/`

This API reference documentation provides comprehensive coverage of all AIAgentX API endpoints, including authentication, request/response formats, error handling, rate limiting, idempotency, and real-time streaming capabilities.