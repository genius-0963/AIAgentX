# AIAgentX Security Architecture

## Overview

AIAgentX implements a comprehensive security architecture designed for multi-tenant enterprise environments. The system provides defense-in-depth security through multiple layers of protection, including authentication, authorization, data encryption, audit logging, and runtime security controls.

## Security Architecture Diagram

```mermaid
graph TB
    subgraph "External Layer"
        CLIENT[Client Applications]
        API[API Gateway]
    end
    
    subgraph "Authentication Layer"
        JWT[JWT Authentication]
        APIKEY[API Key Authentication]
        MFA[Multi-Factor Support]
    end
    
    subgraph "Authorization Layer"
        RBAC[Role-Based Access Control]
        ABAC[Attribute-Based Access Control]
        SCOPES[Scope-Based Permissions]
    end
    
    subgraph "Data Security Layer"
        RLS[Row-Level Security]
        ENCRYPTION[Encryption at Rest]
        TLS[Encryption in Transit]
        TENANT_ISOLATION[Tenant Isolation]
    end
    
    subgraph "Application Security"
        TOOL_SECURITY[Tool Security & Approvals]
        INPUT_VALIDATION[Input Validation]
        OUTPUT_ENCODING[Output Encoding]
        RATE_LIMITING[Rate Limiting]
    end
    
    subgraph "Monitoring & Audit"
        AUDIT_LOGGING[Audit Logging]
        SECURITY_MONITORING[Security Monitoring]
        ANOMALY_DETECTION[Anomaly Detection]
    end
    
    CLIENT --> API
    API --> JWT
    API --> APIKEY
    JWT --> RBAC
    APIKEY --> RBAC
    RBAC --> SCOPES
    SCOPES --> ABAC
    ABAC --> TOOL_SECURITY
    TOOL_SECURITY --> RATE_LIMITING
    SCOPES --> RLS
    RLS --> TENANT_ISOLATION
    TENANT_ISOLATION --> ENCRYPTION
    API --> TLS
    TOOL_SECURITY --> AUDIT_LOGGING
    AUDIT_LOGGING --> SECURITY_MONITORING
    SECURITY_MONITORING --> ANOMALY_DETECTION
```

## Authentication Mechanisms

### JWT Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthMiddleware
    participant JWTService
    participant UserRepo
    participant TenantRepo
    
    Client->>API: Request + Bearer Token
    API->>AuthMiddleware: authenticate()
    AuthMiddleware->>AuthMiddleware: Extract JWT from Authorization header
    AuthMiddleware->>JWTService: validate_and_decode(token)
    
    JWTService->>JWTService: Verify signature with secret key
    JWTService->>JWTService: Check token expiration
    JWTService->>JWTService: Validate token issuer and audience
    JWTService->>JWTService: Extract claims (user_id, tenant_id, scopes)
    
    alt Token Valid
        JWTService-->>AuthMiddleware: Claims
        AuthMiddleware->>UserRepo: get_user(user_id)
        UserRepo-->>AuthMiddleware: User Entity
        AuthMiddleware->>TenantRepo: get_tenant(tenant_id)
        TenantRepo-->>AuthMiddleware: Tenant Entity
        AuthMiddleware->>AuthMiddleware: Build AuthContext
        AuthMiddleware->>AuthMiddleware: Check required scopes
        AuthMiddleware-->>API: AuthContext
        API->>API: Process request
        API-->>Client: Response
    else Token Invalid
        JWTService-->>AuthMiddleware: ValidationError
        AuthMiddleware-->>Client: 401 Unauthorized
    end
```

### JWT Token Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-id-1"
  },
  "payload": {
    "iss": "aiagentx",
    "sub": "user-id",
    "aud": "aiagentx-api",
    "exp": 1735689600,
    "iat": 1735686000,
    "tenant_id": "tenant-uuid",
    "user_id": "user-uuid",
    "scopes": ["agents:read", "agents:write", "runs:execute"],
    "token_type": "access"
  }
}
```

### API Key Authentication

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthMiddleware
    participant APIKeyRepo
    participant HashService
    
    Client->>API: Request + X-API-Key header
    API->>AuthMiddleware: authenticate()
    AuthMiddleware->>AuthMiddleware: Extract API key from header
    AuthMiddleware->>HashService: hash_key(api_key)
    HashService-->>AuthMiddleware: key_hash
    AuthMiddleware->>APIKeyRepo: get_by_key_hash(key_hash)
    APIKeyRepo-->>AuthMiddleware: APIKey Entity
    
    alt API Key Valid
        AuthMiddleware->>AuthMiddleware: Check not expired
        AuthMiddleware->>AuthMiddleware: Check is_active
        AuthMiddleware->>AuthMiddleware: Extract tenant_id and scopes
        AuthMiddleware->>AuthMiddleware: Build AuthContext
        AuthMiddleware-->>API: AuthContext
        API->>API: Process request
        API-->>Client: Response
    else API Key Invalid
        AuthMiddleware-->>Client: 401 Unauthorized
    end
```

### API Key Security Features

- **Key Hashing:** API keys are hashed using SHA-256 before storage
- **Prefix-Based Identification:** Keys use prefixes (e.g., `aiak_`) for identification
- **Expiration:** Time-based expiration with configurable TTL
- **Scoping:** Keys can be restricted to specific scopes
- **Rate Limiting:** Per-key rate limiting to prevent abuse
- **Revocation:** Immediate revocation capability

## Authorization Model

### Scope-Based Access Control

AIAgentX implements a hierarchical scope system for fine-grained access control:

```mermaid
graph TD
    SCOPES[Scopes] --> AGENTS[agents:read]
    SCOPES --> AGENTS_WRITE[agents:write]
    SCOPES --> RUNS[runs:read]
    SCOPES --> RUNS_EXECUTE[runs:execute]
    SCOPES --> RUNS_CANCEL[runs:cancel]
    SCOPES --> TOOLS[tools:read]
    SCOPES --> TOOLS_APPROVE[tools:approve]
    SCOPES --> MEMORY[memory:read]
    SCOPES --> MEMORY_WRITE[memory:write]
    SCOPES --> AUDIT[audit:read]
    SCOPES --> ADMIN[admin:*]
    
    AGENTS_WRITE --> AGENTS
    RUNS_EXECUTE --> RUNS
    RUNS_CANCEL --> RUNS
    TOOLS_APPROVE --> TOOLS
    MEMORY_WRITE --> MEMORY
    ADMIN --> AGENTS_WRITE
    ADMIN --> RUNS_EXECUTE
    ADMIN --> TOOLS_APPROVE
    ADMIN --> MEMORY_WRITE
    ADMIN --> AUDIT
```

### Scope Definitions

| Scope | Description | Permissions |
|-------|-------------|-------------|
| `agents:read` | Read agent definitions | GET /agents, GET /agents/{id} |
| `agents:write` | Create/modify agents | POST /agents, PATCH /agents/{id}, DELETE /agents/{id} |
| `runs:read` | Read run information | GET /runs, GET /runs/{id} |
| `runs:execute` | Execute agent runs | POST /agents/{id}/runs |
| `runs:cancel` | Cancel running runs | POST /runs/{id}/cancel |
| `tools:read` | Read tool information | GET /tools |
| `tools:approve` | Approve tool executions | POST /approvals/{id}/approve |
| `memory:read` | Read memory data | GET /memory |
| `memory:write` | Write memory data | POST /memory |
| `audit:read` | Read audit logs | GET /audit |
| `admin:*` | Full administrative access | All permissions |

### Authorization Enforcement Points

```mermaid
graph TB
    subgraph "API Layer"
        ENDPOINT[API Endpoint]
        DECORATOR[Scope Decorator]
    end
    
    subgraph "Middleware Layer"
        AUTH_MIDDLEWARE[Auth Middleware]
        TENANT_CHECK[Tenant Check]
    end
    
    subgraph "Domain Layer"
        USE_CASE[Use Case]
        DOMAIN_LOGIC[Domain Logic]
    end
    
    subgraph "Infrastructure Layer"
        REPOSITORY[Repository]
        RLS[Row-Level Security]
    end
    
    ENDPOINT --> DECORATOR
    DECORATOR --> AUTH_MIDDLEWARE
    AUTH_MIDDLEWARE --> TENANT_CHECK
    TENANT_CHECK --> USE_CASE
    USE_CASE --> DOMAIN_LOGIC
    DOMAIN_LOGIC --> REPOSITORY
    REPOSITORY --> RLS
```

## Multi-Tenant Data Isolation

### Row-Level Security (RLS) Implementation

PostgreSQL Row-Level Security ensures tenant isolation at the database level:

```sql
-- Enable RLS on agents table
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;

-- Create tenant isolation policy
CREATE POLICY tenant_isolation_agents ON agents
    FOR ALL
    TO aiagentx_app
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
    );

-- Apply similar policies to all tenant-scoped tables
CREATE POLICY tenant_isolation_runs ON runs
    FOR ALL
    TO aiagentx_app
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
    );

CREATE POLICY tenant_isolation_memory ON memory_records
    FOR ALL
    TO aiagentx_app
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
    );
```

### Tenant Context Propagation

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Auth
    participant TenantContext
    participant DBConnection
    participant Database
    
    Client->>API: Request + JWT
    API->>Auth: authenticate()
    Auth->>Auth: Extract tenant_id from JWT
    Auth->>TenantContext: set_current_tenant(tenant_id)
    TenantContext->>DBConnection: set_session_variable('app.current_tenant_id', tenant_id)
    DBConnection->>Database: SET app.current_tenant_id = 'tenant-uuid'
    Database-->>DBConnection: Success
    DBConnection-->>API: Connection with tenant context
    API->>Database: Execute Query
    Database->>Database: Apply RLS Policy
    Database->>Database: Filter by tenant_id
    Database-->>API: Tenant-scoped results
    API-->>Client: Response
```

### Tenant Data Separation Strategy

```mermaid
graph TB
    subgraph "Shared Database"
        DB[(PostgreSQL)]
    end
    
    subgraph "Tenant 1 Data"
        T1_AGENTS[agents: tenant_id = t1]
        T1_RUNS[runs: tenant_id = t1]
        T1_MEMORY[memory: tenant_id = t1]
    end
    
    subgraph "Tenant 2 Data"
        T2_AGENTS[agents: tenant_id = t2]
        T2_RUNS[runs: tenant_id = t2]
        T2_MEMORY[memory: tenant_id = t2]
    end
    
    subgraph "System Data"
        SYS_AGENTS[system agents]
        SYS_CONFIG[configuration]
    end
    
    DB --> T1_AGENTS
    DB --> T1_RUNS
    DB --> T1_MEMORY
    DB --> T2_AGENTS
    DB --> T2_RUNS
    DB --> T2_MEMORY
    DB --> SYS_AGENTS
    DB --> SYS_CONFIG
```

## Tool Security System

### Tool Policy Evaluation

```mermaid
graph TB
    subgraph "Tool Execution Request"
        REQUEST[Tool Execution Request]
    end
    
    subgraph "Policy Evaluation"
        POLICY[Tool Policy]
        RULES[Policy Rules]
        CONDITIONS[Policy Conditions]
        EFFECTS[Policy Effects]
    end
    
    subgraph "Decision Making"
        EVALUATOR[Policy Evaluator]
        DECISION[Policy Decision]
    end
    
    subgraph "Enforcement"
        ALLOW[Allow Execution]
        DENY[Deny Execution]
        APPROVE[Require Approval]
    end
    
    REQUEST --> EVALUATOR
    EVALUATOR --> POLICY
    POLICY --> RULES
    RULES --> CONDITIONS
    CONDITIONS --> EFFECTS
    EFFECTS --> EVALUATOR
    EVALUATOR --> DECISION
    DECISION --> ALLOW
    DECISION --> DENY
    DECISION --> APPROVE
```

### Tool Approval Workflow

```mermaid
stateDiagram-v2
    [*] --> PENDING: Approval Request Created
    PENDING --> APPROVED: Human Approves
    PENDING --> DENIED: Human Denies
    PENDING --> EXPIRED: Timeout Reached
    APPROVED --> [*]: Execute Tool
    DENIED --> [*]: Block Execution
    EXPIRED --> [*]: Block Execution
```

### Tool Classification System

Tools are classified based on their potential impact:

| Classification | Description | Default Behavior | Approval Required |
|---------------|-------------|------------------|-------------------|
| **Safe** | Read-only operations, no side effects | Auto-approve | No |
| **Destructive** | Write/delete operations with side effects | Manual review | Yes |
| **External** | Calls to external systems/APIs | Policy-based | Conditional |
| **Sensitive** | Access to sensitive data or systems | Strict policy | Always |
| **Financial** | Operations with financial impact | Strict policy | Always |

### Tool Policy Example

```json
{
  "tool_name": "database_delete",
  "classification": "destructive",
  "rules": [
    {
      "type": "allow",
      "condition": {
        "action": "delete",
        "resource": "temp_tables"
      },
      "effect": {
        "allow": true
      },
      "priority": 10
    },
    {
      "type": "deny",
      "condition": {
        "action": "delete",
        "resource": "production_tables"
      },
      "effect": {
        "allow": false
      },
      "priority": 100
    }
  ],
  "default_effect": {
    "allow": false,
    "require_approval": true
  },
  "metadata": {
    "description": "Database deletion tool",
    "risk_level": "high",
    "approval_timeout_seconds": 300
  }
}
```

## Data Encryption

### Encryption at Rest

```mermaid
graph TB
    subgraph "Application Layer"
        APP[Application]
    end
    
    subgraph "Encryption Service"
        KEY_MANAGEMENT[Tenant Key Management]
        ENCRYPTION[Encryption Engine]
        DECRYPTION[Decryption Engine]
    end
    
    subgraph "Key Storage"
        KMS[Key Management Service]
        HSM[Hardware Security Module]
    end
    
    subgraph "Database Layer"
        DB[(PostgreSQL)]
    end
    
    APP --> ENCRYPTION
    ENCRYPTION --> KEY_MANAGEMENT
    KEY_MANAGEMENT --> KMS
    KEY_MANAGEMENT --> HSM
    ENCRYPTION --> DB
    DB --> DECRYPTION
    DECRYPTION --> KEY_MANAGEMENT
```

### Encryption Implementation

- **Algorithm:** AES-256-GCM for data encryption
- **Key Management:** Tenant-specific encryption keys
- **Key Storage:** Hardware Security Module (HSM) or KMS
- **Key Rotation:** Automatic key rotation policies
- **Data Classification:** Encrypt based on sensitivity level

### Encryption in Transit

```mermaid
graph TB
    subgraph "Client"
        CLIENT_APP[Client Application]
    end
    
    subgraph "Network"
        TLS1[TLS 1.3]
        MUTUAL_TLS[Mutual TLS]
    end
    
    subgraph "API Gateway"
        API[API Server]
    end
    
    subgraph "Internal Services"
        WORKER[Worker Services]
        DB[(Database)]
    end
    
    CLIENT_APP --> TLS1
    TLS1 --> API
    API --> MUTUAL_TLS
    MUTUAL_TLS --> WORKER
    WORKER --> DB
```

### TLS Configuration

- **Protocol:** TLS 1.3 minimum
- **Cipher Suites:** Modern, secure cipher suites only
- **Certificate Validation:** Strict certificate validation
- **HSTS:** HTTP Strict Transport Security enabled
- **Certificate Rotation:** Automated certificate management

## Audit Logging

### Audit Event Schema

```json
{
  "event_id": "uuid",
  "event_type": "tool_execution",
  "timestamp": "2024-01-01T00:00:00Z",
  "tenant_id": "tenant-uuid",
  "user_id": "user-uuid",
  "actor": {
    "type": "user",
    "id": "user-uuid",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  },
  "resource": {
    "type": "tool",
    "id": "tool-name",
    "details": {...}
  },
  "action": "execute",
  "outcome": "success",
  "metadata": {
    "run_id": "run-uuid",
    "agent_id": "agent-uuid",
    "execution_time_ms": 150
  }
}
```

### Audit Event Types

| Event Type | Description | Criticality |
|------------|-------------|-------------|
| `authentication` | Login/logout events | High |
| `authorization` | Permission checks | Medium |
| `agent_creation` | Agent creation/modification | Medium |
| `agent_execution` | Agent run execution | High |
| `tool_execution` | Tool execution attempts | Critical |
| `data_access` | Data read/write operations | High |
| `configuration_change` | System configuration changes | Critical |
| `security_event` | Security-related events | Critical |

### Audit Data Flow

```mermaid
sequenceDiagram
    participant Component
    participant AuditLogger
    participant Outbox
    participant DB
    participant Flusher
    participant EventBus
    participant AuditStorage
    participant SIEM[SIEM System]
    
    Component->>AuditLogger: log_audit_event(event)
    AuditLogger->>AuditLogger: Validate schema
    AuditLogger->>AuditLogger: Add correlation ID
    AuditLogger->>Outbox: insert_event(event)
    Outbox->>DB: INSERT INTO outbox_events
    DB-->>Outbox: Success
    AuditLogger-->>Component: Success
    
    loop Polling
        Flusher->>Outbox: get_pending_events()
        Outbox->>DB: SELECT undelivered events
        DB-->>Outbox: Events
        Outbox-->>Flusher: Events
        Flusher->>EventBus: publish(events)
        EventBus->>AuditStorage: store_event(event)
        AuditStorage-->>EventBus: Success
        EventBus->>SIEM: forward_event(event)
        SIEM-->>EventBus: Success
        EventBus-->>Flusher: Success
        Flusher->>Outbox: mark_delivered(event_ids)
        Outbox->>DB: UPDATE outbox_events
    end
```

## Rate Limiting and Abuse Prevention

### Rate Limiting Strategy

```mermaid
graph TB
    subgraph "Rate Limiting Layers"
        GLOBAL[Global Rate Limit]
        TENANT[Tenant Rate Limit]
        USER[User Rate Limit]
        APIKEY[API Key Rate Limit]
        ENDPOINT[Endpoint Rate Limit]
    end
    
    subgraph "Rate Limiting Algorithms"
        TOKEN[Token Bucket]
        SLIDING[Sliding Window]
        FIXED[Fixed Window]
    end
    
    subgraph "Enforcement"
        ALLOW[Allow Request]
        THROTTLE[Throttle Request]
        BLOCK[Block Request]
    end
    
    GLOBAL --> TOKEN
    TENANT --> SLIDING
    USER --> SLIDING
    APIKEY --> SLIDING
    ENDPOINT --> FIXED
    TOKEN --> ALLOW
    SLIDING --> THROTTLE
    FIXED --> BLOCK
```

### Rate Limiting Configuration

| Scope | Limit | Window | Algorithm |
|-------|-------|--------|-----------|
| Global | 10,000 req/min | 1 minute | Token Bucket |
| Per Tenant | 1,000 req/min | 1 minute | Sliding Window |
| Per User | 100 req/min | 1 minute | Sliding Window |
| Per API Key | 200 req/min | 1 minute | Sliding Window |
| Per Endpoint | 50 req/min | 1 minute | Fixed Window |

### Abuse Detection

- **Pattern Recognition:** Detect unusual usage patterns
- **Geolocation Analysis:** Monitor geographic distribution
- **Behavioral Analysis:** Detect anomalous behavior
- **Velocity Checks:** Detect rapid-fire requests
- **IP Reputation:** Check IP reputation scores

## Input Validation and Output Encoding

### Input Validation Layers

```mermaid
graph TB
    subgraph "Validation Layers"
        SCHEMA[Schema Validation]
        TYPE[Type Validation]
        RANGE[Range Validation]
        BUSINESS[Business Rule Validation]
        SECURITY[Security Validation]
    end
    
    subgraph "Validation Types"
        PYDANTIC[Pydantic Models]
        CUSTOM[Custom Validators]
        SANITIZATION[Input Sanitization]
    end
    
    subgraph "Security Checks"
        XSS[Cross-Site Scripting]
        SQLI[SQL Injection]
        RCE[Remote Code Execution]
        PATH_TRAVERSAL[Path Traversal]
    end
    
    SCHEMA --> PYDANTIC
    TYPE --> PYDANTIC
    RANGE --> CUSTOM
    BUSINESS --> CUSTOM
    SECURITY --> SANITIZATION
    SANITIZATION --> XSS
    SANITIZATION --> SQLI
    SANITIZATION --> RCE
    SANITIZATION --> PATH_TRAVERSAL
```

### Output Encoding

- **HTML Encoding:** Prevent XSS in HTML responses
- **JSON Encoding:** Proper JSON serialization
- **URL Encoding:** Safe URL parameter handling
- **SQL Parameterization:** Prevent SQL injection
- **Command Sanitization:** Prevent command injection

## Security Monitoring

### Security Metrics

```mermaid
graph TB
    subgraph "Security Metrics"
        AUTH_METRICS[Authentication Metrics]
        AUTHZ_METRICS[Authorization Metrics]
        TOOL_METRICS[Tool Security Metrics]
        DATA_METRICS[Data Access Metrics]
        ANOMALY_METRICS[Anomaly Detection Metrics]
    end
    
    subgraph "Key Metrics"
        FAILED_LOGINS[Failed Login Attempts]
        UNAUTHORIZED_ACCESS[Unauthorized Access Attempts]
        TOOL_DENIALS[Tool Execution Denials]
        DATA_EXFILTRATION[Data Exfiltration Attempts]
        ANOMALY_SCORES[Anomaly Scores]
    end
    
    AUTH_METRICS --> FAILED_LOGINS
    AUTHZ_METRICS --> UNAUTHORIZED_ACCESS
    TOOL_METRICS --> TOOL_DENIALS
    DATA_METRICS --> DATA_EXFILTRATION
    ANOMALY_METRICS --> ANOMALY_SCORES
```

### Security Alerting

| Alert Type | Threshold | Response Time |
|------------|-----------|---------------|
| Failed Login Attempts | > 10 per minute | Immediate |
| Unauthorized Access | > 5 per minute | 5 minutes |
| Tool Execution Denials | > 3 per minute | 10 minutes |
| Data Exfiltration Attempts | Any | Immediate |
| Anomaly Score High | > 0.8 | 5 minutes |
| Rate Limit Exceeded | > 90% of limit | 1 minute |

## Compliance and Governance

### Data Protection Compliance

- **GDPR:** Data subject rights, consent management, data portability
- **SOC 2:** Security controls, access management, monitoring
- **HIPAA:** Healthcare data protection, audit trails
- **PCI DSS:** Payment card data handling, encryption

### Security Best Practices

1. **Principle of Least Privilege:** Minimal required permissions
2. **Defense in Depth:** Multiple security layers
3. **Fail Securely:** Secure by default, deny by default
4. **Secure by Design:** Security built into architecture
5. **Continuous Monitoring:** Real-time security monitoring
6. **Regular Audits:** Periodic security assessments
7. **Incident Response:** Established incident response procedures
8. **Security Training:** Regular security awareness training

## Security Configuration

### Environment Variables

```env
# Security Configuration
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=RS256
JWT_EXPIRATION_MINUTES=60

# Encryption
ENCRYPTION_KEY_ID=key-id-1
KMS_ENDPOINT=https://kms.example.com
HSM_ENABLED=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_GLOBAL=10000
RATE_LIMIT_TENANT=1000
RATE_LIMIT_USER=100

# Security Headers
SECURE_HEADERS_ENABLED=true
HSTS_ENABLED=true
CSP_ENABLED=true

# Audit Logging
AUDIT_LOGGING_ENABLED=true
AUDIT_RETENTION_DAYS=90
AUDIT_FORWARD_TO_SIEM=true
```

This security architecture documentation provides a comprehensive overview of all security mechanisms in AIAgentX, ensuring enterprise-grade security for multi-tenant AI agent orchestration.