# Sprint 4: Model Provider Integration

**Sprint Goal:** Implement the model provider adapter layer with support for multiple LLM providers, usage tracking, timeout management, and a deterministic fake provider for testing.

**Duration:** 2 weeks  
**Priority:** High - Core AI functionality  
**Risk Level:** Medium - Provider integration complexity and API compatibility

---

## Sprint Overview

This sprint implements the model provider abstraction layer that enables AIAgentX to work with different LLM providers (OpenAI, Anthropic, etc.) through a unified interface. We will create provider adapters, implement usage tracking and cost accounting, add timeout and retry logic, and build a deterministic fake provider for testing. This layer ensures that the core system is provider-agnostic and can support multiple models.

---

## User Stories

### US-4.1: Model Provider Protocol and Abstraction
**As a** developer  
**I want** a unified interface for different model providers  
**So that** the system can work with multiple LLM providers without changing core logic

**Acceptance Criteria:**
- Define `ModelProvider` protocol with standardized interface
- Implement provider adapter for OpenAI
- Implement provider adapter for Anthropic
- Normalize provider responses to internal models
- Support for different model configurations
- Provider-specific error handling
- Provider selection logic
- Unit tests for each provider adapter

### US-4.2: Usage Tracking and Cost Accounting
**As a** platform operator  
**I want** to track token usage and costs for each run  
**So that** we can monitor spending and enforce budget limits

**Acceptance Criteria:**
- Track prompt tokens, completion tokens, and total tokens
- Calculate costs based on model pricing
- Record usage per run step
- Aggregate usage at run level
- Support different pricing models per provider
- Usage persistence in database
- Cost calculation accuracy tests
- Usage reporting and queries

### US-4.3: Timeout and Retry Management
**As a** developer  
**I want** configurable timeouts and retry logic for provider calls  
**So that** transient failures don't cause permanent failures

**Acceptance Criteria:**
- Configurable connect timeout (default 3 seconds)
- Configurable total timeout (default 45 seconds)
- Retry logic for transport errors, 429, and 5xx errors
- Exponential backoff with full jitter
- Configurable retry budget (default 2 retries)
- Retry classification (transient vs permanent errors)
- Timeout enforcement at provider level
- Unit tests for timeout and retry scenarios

### US-4.4: Provider Health Monitoring and Circuit Breaking
**As a** platform operator  
**I want** to monitor provider health and implement circuit breaking  
**So that** failing providers don't degrade system performance

**Acceptance Criteria:**
- Track provider error rates and latency
- Implement circuit breaker pattern
- Configurable failure rate threshold
- Circuit breaker states (closed, open, half-open)
- Automatic circuit recovery with probe calls
- Provider health metrics
- Health check endpoints
- Integration tests for circuit breaking

### US-4.5: Provider Fallback Mechanism
**As a** developer  
**I want** controlled fallback between providers  
**So that** system remains available during provider outages

**Acceptance Criteria:**
- Configure primary and fallback providers
- Fallback only before irreversible tool effects
- Fallback within same data-residency and capability class
- Idempotency requirements for fallback scenarios
- Fallback event logging
- Fallback metrics tracking
- Configuration validation for fallback compatibility
- Tests for fallback scenarios

### US-4.6: Deterministic Fake Provider for Testing
**As a** developer  
**I want** a deterministic fake provider for testing  
**So that** tests are reliable and don't depend on external providers

**Acceptance Criteria:**
- Implement fake provider that follows `ModelProvider` protocol
- Support for predefined responses
- Configurable delays and errors
- Deterministic behavior for reproducible tests
- Support for tool call simulation
- Usage tracking simulation
- Easy test scenario setup
- Comprehensive test coverage using fake provider

### US-4.7: Model Request/Response Normalization
**As a** developer  
**I want** normalized request and response models  
**So that** provider-specific details are abstracted from core logic

**Acceptance Criteria:**
- Define internal `ModelRequest` model
- Define internal `ModelResponse` model
- Normalize provider-specific request formats
- Normalize provider-specific response formats
- Handle different response structures (text, tool calls, streaming)
- Safety stop handling
- Error response normalization
- Unit tests for normalization logic

---

## Technical Tasks

### 4.1 Provider Protocol Implementation
- [ ] Define `ModelProvider` protocol
- [ ] Create base provider adapter class
- [ ] Implement OpenAI provider adapter
- [ ] Implement Anthropic provider adapter
- [ ] Create provider registry
- [ ] Implement provider selection logic
- [ ] Add provider-specific error mapping
- [ ] Write unit tests for each adapter
- [ ] Write integration tests with real providers (optional)

### 4.2 Usage Tracking Implementation
- [ ] Define usage data models
- [ ] Create pricing configuration per provider/model
- [ ] Implement token counting logic
- [ ] Create cost calculation service
- [ ] Add usage recording to run steps
- [ ] Implement usage aggregation
- [ ] Create usage persistence layer
- [ ] Write unit tests for usage tracking
- [ ] Test cost calculation accuracy

### 4.3 Timeout and Retry Logic
- [ ] Implement timeout configuration
- [ ] Create retry policy configuration
- [ ] Implement error classification logic
- [ ] Add exponential backoff with jitter
- [ ] Implement retry budget enforcement
- [ ] Add timeout enforcement
- [ ] Create retry context tracking
- [ ] Write unit tests for retry scenarios
- [ ] Write integration tests for timeout handling

### 4.4 Provider Health Monitoring
- [ ] Define health metrics structure
- [ ] Implement error rate tracking
- [ ] Add latency monitoring
- [ ] Create circuit breaker implementation
- [ ] Implement circuit state transitions
- [ ] Add health probe logic
- [ ] Create health check endpoints
- [ ] Implement health metrics
- [ ] Write tests for circuit breaking scenarios

### 4.5 Fallback Mechanism
- [ ] Define fallback configuration schema
- [ ] Implement fallback decision logic
- [ ] Add provider compatibility validation
- [ ] Implement fallback trigger conditions
- [ ] Add fallback event logging
- [ ] Create fallback metrics
- [ ] Implement fallback before irreversible effects
- [ ] Write unit tests for fallback logic
- [ ] Test fallback scenarios

### 4.6 Fake Provider Implementation
- [ ] Create fake provider class
- [ ] Implement response configuration
- [ ] Add delay simulation
- [ ] Implement error simulation
- [ ] Add tool call simulation
- [ ] Create test scenario helpers
- [ ] Implement deterministic behavior
- [ ] Write comprehensive tests using fake provider
- [ ] Document fake provider usage

### 4.7 Request/Response Normalization
- [ ] Define internal request/response models
- [ ] Implement request normalization
- [ ] Implement response normalization
- [ ] Handle different response types
- [ ] Add safety stop handling
- [ ] Implement error normalization
- [ ] Create transformation tests
- [ ] Test with various provider responses
- [ ] Document normalization rules

---

## Provider Protocol Definition

```python
from typing import Protocol, Optional
from dataclasses import dataclass

@dataclass
class ModelRequest:
    """Internal model request representation"""
    messages: list[dict]
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[list[dict]] = None
    request_id: str
    tenant_id_hash: str
    timeout_seconds: int = 45
    trace_context: Optional[dict] = None

@dataclass
class ModelResponse:
    """Internal model response representation"""
    content: Optional[str]
    tool_calls: Optional[list[dict]]
    usage: dict  # {prompt_tokens, completion_tokens, total_tokens}
    model: str
    finish_reason: str
    request_id: str
    provider: str
    latency_ms: float
    safety_stop: bool = False

@dataclass
class ProviderError:
    """Provider error classification"""
    is_retryable: bool
    error_type: str  # timeout, rate_limit, server_error, auth_error, etc.
    original_error: Exception
    provider: str

class ModelProvider(Protocol):
    """Protocol for model provider adapters"""
    
    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Execute a model completion request"""
        ...
    
    @property
    def provider_name(self) -> str:
        """Return provider identifier"""
        ...
    
    async def health_check(self) -> bool:
        """Check if provider is healthy"""
        ...
```

---

## Configuration Example

```python
# Provider configuration
MODEL_PROVIDERS = {
    "primary": {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key": "${OPENAI_API_KEY}",
        "timeout_seconds": 45,
        "connect_timeout_seconds": 3,
        "max_retries": 2
    },
    "fallback": {
        "provider": "anthropic",
        "model": "claude-3-opus",
        "api_key": "${ANTHROPIC_API_KEY}",
        "timeout_seconds": 45,
        "connect_timeout_seconds": 3,
        "max_retries": 2
    }
}

# Circuit breaker configuration
CIRCUIT_BREAKER = {
    "failure_rate_threshold": 0.5,
    "minimum_requests": 10,
    "open_timeout_seconds": 60,
    "half_open_max_calls": 3
}

# Pricing configuration (per 1M tokens)
PRICING = {
    "openai:gpt-4o": {
        "prompt_price_usd": 2.50,
        "completion_price_usd": 10.00
    },
    "anthropic:claude-3-opus": {
        "prompt_price_usd": 15.00,
        "completion_price_usd": 75.00
    }
}
```

---

## Definition of Done

**For each user story:**
- [ ] All acceptance criteria are met
- [ ] Provider adapters work correctly
- [ ] Usage tracking is accurate
- [ ] Timeout and retry logic works as expected
- [ ] Circuit breaking functions properly
- [ ] Fallback mechanism is safe
- [ ] Fake provider is reliable for testing
- [ ] Normalization handles all cases
- [ ] Unit tests pass with good coverage
- [ ] Integration tests pass
- [ ] Code is reviewed and approved

**For the sprint:**
- [ ] All user stories completed
- [ ] Provider adapters support at least 2 providers
- [ ] Usage tracking is accurate across providers
- [ ] Circuit breaking prevents cascade failures
- [ ] Fallback mechanism is safe and controlled
- [ ] Fake provider enables reliable testing
- [ ] All provider tests pass
- [ ] Performance meets requirements
- [ ] Security review completed
- [ ] Sprint retrospective completed

---

## Risks and Dependencies

**Risks:**
- **Medium Risk:** Provider API changes may break adapters
- **Pricing Complexity:** Cost calculation may have edge cases
- **Circuit Breaking:** May be too aggressive or too permissive
- **Fallback Safety:** Incorrect fallback could cause issues
- **Testing:** Real provider integration tests may be flaky

**Dependencies:**
- Sprint 1-3 must be completed
- Domain model must support usage tracking
- Configuration management must be available
- Error handling infrastructure must be in place
- Database schema must support usage data

---

## Success Metrics

- Provider adapters respond within configured timeouts
- Usage tracking is 99.9% accurate
- Circuit breaking prevents cascade failures
- Fallback mechanism activates correctly when needed
- Fake provider tests are 100% reliable
- Normalization handles all provider response types
- Provider health checks complete within 5 seconds
- Unit test coverage exceeds 90%
- Integration tests pass consistently
- System can handle provider failures gracefully

---

## Notes

**Senior Tech Lead Guidance:**
- Focus on provider abstraction - keep core logic provider-agnostic
- Implement proper error classification for retry logic
- Circuit breaking should be tunable based on production metrics
- Fallback should be conservative - safety over availability
- Fake provider should be easy to configure for different test scenarios
- Monitor provider costs and usage closely from the start

**Engineering Considerations:**
- Use async/await for all provider calls
- Implement proper timeout handling at multiple layers
- Use structured logging for provider interactions
- Consider streaming responses for future optimization
- Provider credentials should be stored securely
- Implement proper rate limiting per provider
- Monitor provider API quota usage

**Security Considerations:**
- Never log provider API keys or sensitive data
- Validate all provider responses
- Implement proper credential management
- Use tenant-specific provider credentials when needed
- Audit all provider API calls
- Implement data residency compliance
- Never expose provider-specific errors to clients

**Performance Considerations:**
- Implement connection pooling for provider APIs
- Cache provider client instances
- Monitor provider latency and optimize
- Consider batch requests for efficiency
- Implement proper timeout handling
- Use circuit breaking to prevent cascade failures
- Monitor provider quota usage