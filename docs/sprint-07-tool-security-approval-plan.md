# Sprint 7: Tool Security and Approval System - Implementation Plan

## Executive Summary

This sprint implements a comprehensive **Tool Security and Approval System** for the AIAgentX platform. The system provides fine-grained access control for tool execution, human-in-the-loop approval workflows, policy-based authorization, and comprehensive audit logging.

---

## Current State Analysis

### Existing Components
| Component | Location | Description |
|-----------|----------|-------------|
| `ToolGrant` | `app/domain/entities/tool_grant.py` | Basic tool grant with simple policy dict |
| `ToolGrantModel` | `app/infrastructure/db/models/agent.py` | SQLAlchemy model for tool grants |
| `AgentUseCases.add_tool_grant` | `app/application/use_cases/agent.py` | Use case for adding tool grants |
| `RunExecutor` | `app/workers/executor.py` | Run execution engine with step processing |
| `RunStepKind.TOOL_CALL` | `app/domain/value_objects/state.py` | Step kind for tool executions |
| `RunState.AWAITING_APPROVAL` | State machine supports approval transitions |

### Gaps Identified
1. **No policy evaluation engine** - `ToolGrant.allows()` is basic, lacks complex policies
2. **No approval request entity** - Missing domain object for approval workflows
3. **No audit logging** - Tool executions not tracked for compliance
4. **No integration in RunExecutor** - Tool calls don't check grants or request approval
5. **No API for approval management** - Humans can't approve/deny pending requests
6. **No rate limiting per tool** - Missing execution quotas

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TOOL SECURITY ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐    │
│  │  RunExecutor │────▶│ PolicyEvaluator  │────▶│  ToolGrant Registry  │    │
│  │  (worker)    │     │   (domain svc)   │     │  (domain entity)     │    │
│  └──────┬───────┘     └────────┬─────────┘     └──────────────────────┘    │
│         │                      │                                            │
│         │              ┌───────▼───────┐                                    │
│         │              │ Approval      │                                    │
│         │              │ Coordinator   │                                    │
│         │              │ (domain svc)  │                                    │
│         │              └───────┬───────┘                                    │
│         │                      │                                            │
│         ▼                      ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AUDIT LOGGING (cross-cutting)                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Domain Layer Implementation

### 1. Enhanced Policy System

#### New Value Objects: `app/domain/value_objects/policy.py`

```python
# Policy types and evaluation
class PolicyType(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMIT = "rate_limit"
    CONDITIONAL = "conditional"

@dataclass(frozen=True, slots=True)
class PolicyRule:
    """Single policy rule with condition and effect."""
    type: PolicyType
    condition: "PolicyCondition"
    effect: "PolicyEffect"
    priority: int = 0

@dataclass(frozen=True, slots=True)
class PolicyCondition:
    """Condition for policy evaluation."""
    action: str | None = None           # Tool action (e.g., "search", "write")
    resource: str | None = None         # Resource pattern (e.g., "*.pdf")
    context: dict[str, Any] | None = None  # Runtime context (user, time, etc.)
    expression: str | None = None       # CEL expression for complex conditions

@dataclass(frozen=True, slots=True)
class PolicyEffect:
    """Effect when condition matches."""
    allow: bool = True
    require_approval: bool = False
    max_calls_per_minute: int | None = None
    max_calls_per_hour: int | None = None
    max_calls_per_day: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Complete policy for a tool."""
    tool_name: str
    version: int = 1
    rules: list[PolicyRule] = field(default_factory=list)
    default_effect: PolicyEffect = field(default_factory=lambda: PolicyEffect(allow=True))
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 2. Approval Request Domain Entity

#### New Entity: `app/domain/entities/approval_request.py`

```python
from enum import StrEnum
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime, UTC
from typing import Any

class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class ApprovalType(StrEnum):
    TOOL_EXECUTION = "tool_execution"
    SENSITIVE_ACTION = "sensitive_action"
    BUDGET_EXCEED = "budget_exceed"
    POLICY_VIOLATION = "policy_violation"

@dataclass(slots=True, kw_only=True)
class ApprovalRequest(Entity):
    """Human-in-the-loop approval request."""
    run_id: UUID
    step_sequence: int
    approval_type: ApprovalType
    state: ApprovalState = ApprovalState.PENDING
    
    # Request details
    tool_name: str
    action: str
    resource: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    policy_reason: str = ""  # Why approval is needed
    
    # Approval tracking
    requested_by: str = "system"  # worker_id or "system"
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_by: str | None = None
    approved_at: datetime | None = None
    denial_reason: str | None = None
    
    # Expiry
    expires_at: datetime | None = None
    ttl_seconds: int = 3600  # 1 hour default
    
    # Response
    response_data: dict[str, Any] | None = None
    
    def __post_init__(self) -> None:
        if self.expires_at is None:
            self.expires_at = datetime.now(UTC).replace(
                second=datetime.now(UTC).second + self.ttl_seconds
            )
    
    def approve(self, approved_by: str, response_data: dict[str, Any] | None = None) -> None:
        if self.state != ApprovalState.PENDING:
            raise ValueError(f"Cannot approve request in state {self.state}")
        if self.is_expired():
            raise ValueError("Approval request has expired")
        
        self.state = ApprovalState.APPROVED
        self.approved_by = approved_by
        self.approved_at = datetime.now(UTC)
        self.response_data = response_data
        self.touch()
        self.add_event(ApprovalGranted(...))
    
    def deny(self, denied_by: str, reason: str) -> None:
        if self.state != ApprovalState.PENDING:
            raise ValueError(f"Cannot deny request in state {self.state}")
        
        self.state = ApprovalState.DENIED
        self.approved_by = denied_by
        self.approved_at = datetime.now(UTC)
        self.denial_reason = reason
        self.touch()
        self.add_event(ApprovalDenied(...))
    
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at if self.expires_at else False
    
    def cancel(self, reason: str) -> None:
        if self.state not in {ApprovalState.PENDING, ApprovalState.APPROVED}:
            return
        self.state = ApprovalState.CANCELLED
        self.denial_reason = reason
        self.touch()
        self.add_event(ApprovalCancelled(...))
```

### 3. Enhanced ToolGrant Entity

#### Modified: `app/domain/entities/tool_grant.py`

```python
@dataclass(slots=True, kw_only=True)
class ToolGrant(Entity):
    """Tool grant entity with enhanced policy support."""
    agent_version_id: UUID
    tool_name: str
    policy: ToolPolicy  # Changed from dict to ToolPolicy
    is_active: bool = True
    
    def __post_init__(self) -> None:
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("Tool name cannot be empty")
        if not isinstance(self.policy, ToolPolicy):
            raise ValueError("Policy must be a ToolPolicy instance")
    
    def evaluate(self, action: str, resource: str | None = None, 
                 context: dict[str, Any] | None = None) -> "PolicyDecision":
        """Evaluate policy for a tool action."""
        if not self.is_active:
            return PolicyDecision.deny("Grant is inactive")
        
        return PolicyEvaluator.evaluate(self.policy, action, resource, context)
    
    def allows(self, action: str, resource: str | None = None, 
               context: dict[str, Any] | None = None) -> bool:
        """Backward compatible simple check."""
        return self.evaluate(action, resource, context).allowed
```

### 4. Policy Decision Value Object

#### New: `app/domain/value_objects/policy.py`

```python
@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Result of policy evaluation."""
    allowed: bool
    require_approval: bool = False
    reason: str = ""
    matched_rule: PolicyRule | None = None
    rate_limit: RateLimitInfo | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def allow(cls, reason: str = "", **kwargs) -> "PolicyDecision":
        return cls(allowed=True, reason=reason, **kwargs)
    
    @classmethod
    def deny(cls, reason: str, **kwargs) -> "PolicyDecision":
        return cls(allowed=False, reason=reason, **kwargs)
    
    @classmethod
    def require_approval(cls, reason: str, **kwargs) -> "PolicyDecision":
        return cls(allowed=False, require_approval=True, reason=reason, **kwargs)

@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    """Rate limit information."""
    limit: int
    remaining: int
    reset_at: datetime
    scope: str  # "minute", "hour", "day"
```

### 5. Policy Evaluator Domain Service

#### New: `app/domain/services/policy_evaluator.py`

```python
from celpy import Environment  # For CEL expression evaluation

class PolicyEvaluator:
    """Evaluates tool policies against requests."""
    
    def __init__(self) -> None:
        self._cel_env = Environment()
    
    @classmethod
    def evaluate(cls, policy: ToolPolicy, action: str, 
                 resource: str | None = None,
                 context: dict[str, Any] | None = None) -> PolicyDecision:
        """Evaluate policy rules in priority order."""
        context = context or {}
        
        # Sort rules by priority (highest first)
        sorted_rules = sorted(policy.rules, key=lambda r: -r.priority)
        
        for rule in sorted_rules:
            if cls._matches_condition(rule.condition, action, resource, context):
                return cls._apply_effect(rule.effect, rule, context)
        
        # No rules matched - use default
        return cls._apply_effect(policy.default_effect, None, context)
    
    @classmethod
    def _matches_condition(cls, condition: PolicyCondition, action: str,
                          resource: str | None, context: dict[str, Any]) -> bool:
        """Check if condition matches request."""
        if condition.action and condition.action != action:
            return False
        if condition.resource and resource:
            if not cls._match_pattern(condition.resource, resource):
                return False
        if condition.expression:
            try:
                result = cls._cel_env.evaluate(condition.expression, context)
                return bool(result)
            except Exception:
                return False
        return True
    
    @classmethod
    def _apply_effect(cls, effect: PolicyEffect, rule: PolicyRule | None,
                     context: dict[str, Any]) -> PolicyDecision:
        """Apply policy effect."""
        if effect.require_approval:
            return PolicyDecision.require_approval(
                reason="Policy requires approval",
                matched_rule=rule,
                rate_limit=cls._build_rate_limit(effect)
            )
        
        if not effect.allow:
            return PolicyDecision.deny(
                reason="Policy denies access",
                matched_rule=rule
            )
        
        return PolicyDecision.allow(
            reason="Policy allows access",
            matched_rule=rule,
            rate_limit=cls._build_rate_limit(effect)
        )
    
    @staticmethod
    def _match_pattern(pattern: str, value: str) -> bool:
        """Simple glob-style pattern matching."""
        import fnmatch
        return fnmatch.fnmatch(value, pattern)
    
    @staticmethod
    def _build_rate_limit(effect: PolicyEffect) -> RateLimitInfo | None:
        if effect.max_calls_per_minute:
            return RateLimitInfo(
                limit=effect.max_calls_per_minute,
                remaining=effect.max_calls_per_minute,
                reset_at=datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1),
                scope="minute"
            )
        # Similar for hour/day...
        return None
```

### 6. Approval Coordinator Domain Service

#### New: `app/domain/services/approval_coordinator.py`

```python
class ApprovalCoordinator:
    """Coordinates approval requests and responses."""
    
    def __init__(
        self,
        approval_repo: ApprovalRequestRepository,
        notification_service: NotificationService,
    ) -> None:
        self._repo = approval_repo
        self._notifications = notification_service
    
    async def request_approval(
        self,
        run_id: UUID,
        step_sequence: int,
        tool_name: str,
        action: str,
        resource: str | None,
        input_data: dict[str, Any],
        policy_reason: str,
        requested_by: str,
        ttl_seconds: int = 3600,
    ) -> ApprovalRequest:
        """Create and store approval request."""
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=step_sequence,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name=tool_name,
            action=action,
            resource=resource,
            input_data=input_data,
            policy_reason=policy_reason,
            requested_by=requested_by,
            ttl_seconds=ttl_seconds,
        )
        
        await self._repo.add(request)
        await self._notifications.notify_approval_requested(request)
        return request
    
    async def respond_to_approval(
        self,
        request_id: UUID,
        approved: bool,
        responded_by: str,
        response_data: dict[str, Any] | None = None,
        denial_reason: str | None = None,
    ) -> ApprovalRequest:
        """Process approval response."""
        request = await self._repo.get(request_id)
        if not request:
            raise ValueError("Approval request not found")
        
        if approved:
            request.approve(responded_by, response_data)
        else:
            request.deny(responded_by, denial_reason or "Denied by approver")
        
        await self._repo.update(request)
        await self._notifications.notify_approval_responded(request)
        return request
    
    async def get_pending_approvals(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        """Get pending approvals for a tenant/run."""
        return await self._repo.get_pending(tenant_id, run_id)
    
    async def expire_old_requests(self) -> int:
        """Expire old pending requests. Returns count expired."""
        return await self._repo.expire_old()
```

---

## Application Layer Implementation

### 7. Tool Execution Service

#### New: `app/application/services/tool_execution_service.py`

```python
class ToolExecutionService:
    """Service for secure tool execution with policy enforcement."""
    
    def __init__(
        self,
        tool_grant_repo: ToolGrantRepository,
        approval_coordinator: ApprovalCoordinator,
        audit_logger: AuditLogger,
        rate_limiter: RateLimiter,
    ) -> None:
        self._grants = tool_grant_repo
        self._approvals = approval_coordinator
        self._audit = audit_logger
        self._rate_limiter = rate_limiter
    
    async def execute_tool(
        self,
        run: Run,
        agent_version_id: UUID,
        tool_name: str,
        action: str,
        input_data: dict[str, Any],
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """Execute tool with security checks."""
        # 1. Get tool grant
        grant = await self._grants.get_by_tool(agent_version_id, tool_name)
        if not grant:
            await self._audit.log(
                run_id=run.id,
                event_type=AuditEventType.TOOL_DENIED,
                tool_name=tool_name,
                action=action,
                reason="No grant found for tool",
                success=False,
            )
            return ToolExecutionResult.denied("No grant found for tool")
        
        # 2. Evaluate policy
        decision = grant.evaluate(action, resource, context)
        
        # 3. Check rate limits
        if decision.rate_limit:
            allowed = await self._rate_limiter.check_limit(
                key=f"tool:{tool_name}:{action}:{run.tenant_id}",
                limit=decision.rate_limit.limit,
                window=decision.rate_limit.scope,
            )
            if not allowed:
                await self._audit.log(
                    run_id=run.id,
                    event_type=AuditEventType.RATE_LIMITED,
                    tool_name=tool_name,
                    action=action,
                    reason="Rate limit exceeded",
                    success=False,
                )
                return ToolExecutionResult.rate_limited(decision.rate_limit)
        
        # 4. Handle approval requirement
        if decision.require_approval:
            request = await self._approvals.request_approval(
                run_id=run.id,
                step_sequence=len(run.steps),
                tool_name=tool_name,
                action=action,
                resource=resource,
                input_data=input_data,
                policy_reason=decision.reason,
                requested_by="executor",
            )
            
            # Transition run to awaiting approval
            run.request_approval()
            
            await self._audit.log(
                run_id=run.id,
                event_type=AuditEventType.APPROVAL_REQUESTED,
                tool_name=tool_name,
                action=action,
                reason=decision.reason,
                approval_id=request.id,
                success=True,
            )
            
            return ToolExecutionResult.awaiting_approval(request.id)
        
        # 5. Execute tool (delegated to actual tool handler)
        result = await self._execute_tool_handler(tool_name, action, input_data)
        
        # 6. Audit successful execution
        await self._audit.log(
            run_id=run.id,
            event_type=AuditEventType.TOOL_EXECUTED,
            tool_name=tool_name,
            action=action,
            input_data=input_data,
            output_data=result.output,
            success=result.success,
        )
        
        return result
    
    async def _execute_tool_handler(...) -> ToolExecutionResult:
        """Delegate to actual tool implementation."""
        # This integrates with existing tool registry
        pass
```

### 8. Audit Logger Service

#### New: `app/application/services/audit_logger.py`

```python
class AuditEventType(StrEnum):
    TOOL_EXECUTED = "tool_executed"
    TOOL_DENIED = "tool_denied"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    RATE_LIMITED = "rate_limited"
    POLICY_VIOLATION = "policy_violation"

@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Audit log entry."""
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    tenant_id: UUID
    run_id: UUID | None
    agent_version_id: UUID | None
    event_type: AuditEventType
    tool_name: str | None
    action: str | None
    resource: str | None
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    success: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
    approval_id: UUID | None = None
    user_id: str | None = None  # For human approvals

class AuditLogger:
    """Centralized audit logging for tool executions."""
    
    def __init__(
        self,
        audit_repo: AuditRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._repo = audit_repo
        self._publisher = event_publisher
    
    async def log(self, **kwargs) -> AuditEntry:
        """Log audit entry."""
        entry = AuditEntry(**kwargs)
        await self._repo.add(entry)
        await self._publisher.publish(AuditEventLogged(entry=entry))
        return entry
    
    async def query(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
        event_types: list[AuditEventType] | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit logs."""
        return await self._repo.query(...)
```

---

## Infrastructure Layer Implementation

### 9. Database Models & Migrations

#### Migration: `alembic/versions/xxx_add_approval_and_audit.py`

```python
"""Add approval requests and audit logs tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

def upgrade() -> None:
    # Approval requests table
    approval_state_enum = ENUM(
        'pending', 'approved', 'denied', 'expired', 'cancelled',
        name='approval_state', create_type=True
    )
    approval_type_enum = ENUM(
        'tool_execution', 'sensitive_action', 'budget_exceed', 'policy_violation',
        name='approval_type', create_type=True
    )
    
    op.create_table(
        'approval_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', UUID(as_uuid=True), 
                  sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_sequence', sa.Integer(), nullable=False),
        sa.Column('approval_type', approval_type_enum, nullable=False),
        sa.Column('state', approval_state_enum, nullable=False, default='pending'),
        sa.Column('tool_name', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('resource', sa.Text(), nullable=True),
        sa.Column('input_data', JSONB(), nullable=False, default={}),
        sa.Column('policy_reason', sa.Text(), nullable=False, default=''),
        sa.Column('requested_by', sa.Text(), nullable=False, default='system'),
        sa.Column('requested_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
        sa.Column('approved_by', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('denial_reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ttl_seconds', sa.Integer(), nullable=False, default=3600),
        sa.Column('response_data', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_approval_requests_run_id', 'approval_requests', ['run_id'])
    op.create_index('ix_approval_requests_state', 'approval_requests', ['state'])
    op.create_index('ix_approval_requests_expires_at', 'approval_requests', ['expires_at'])
    
    # Audit logs table
    audit_event_type_enum = ENUM(
        'tool_executed', 'tool_denied', 'approval_requested',
        'approval_granted', 'approval_denied', 'rate_limited', 'policy_violation',
        name='audit_event_type', create_type=True
    )
    
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', UUID(as_uuid=True), 
                  sa.ForeignKey('runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('agent_version_id', UUID(as_uuid=True), 
                  sa.ForeignKey('agent_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', audit_event_type_enum, nullable=False),
        sa.Column('tool_name', sa.Text(), nullable=True),
        sa.Column('action', sa.Text(), nullable=True),
        sa.Column('resource', sa.Text(), nullable=True),
        sa.Column('input_data', JSONB(), nullable=True),
        sa.Column('output_data', JSONB(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('metadata', JSONB(), nullable=False, default={}),
        sa.Column('approval_id', UUID(as_uuid=True), 
                  sa.ForeignKey('approval_requests.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
    )
    
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_run_id', 'audit_logs', ['run_id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('ix_audit_logs_tool_name', 'audit_logs', ['tool_name'])

def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('approval_requests')
    # Drop enums
    op.execute('DROP TYPE audit_event_type')
    op.execute('DROP TYPE approval_type')
    op.execute('DROP TYPE approval_state')
```

#### Updated ToolGrantModel: `app/infrastructure/db/models/agent.py`

```python
class ToolGrantModel(Base, UUIDMixin, TimestampMixin):
    """Tool Grant database model with enhanced policy."""
    __tablename__ = "tool_grants"
    
    agent_version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(Text(), nullable=False)
    policy: Mapped[dict[str, object]] = mapped_column(
        JSONB(), nullable=False, default={}
    )  # Stores ToolPolicy as JSON
    is_active: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True
    )
    
    agent_version: Mapped["AgentVersionModel"] = relationship(
        "AgentVersionModel", back_populates="tool_grants"
    )
    
    __table_args__ = (
        sa.UniqueConstraint('agent_version_id', 'tool_name', name='uq_tool_grant_version_tool'),
    )
```

### 10. Repository Implementations

#### New: `app/infrastructure/db/repositories/approval.py`

```python
class SQLApprovalRepository(ApprovalRequestRepository):
    """SQL implementation of approval request repository."""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def add(self, request: ApprovalRequest) -> None:
        model = ApprovalRequestModel.from_entity(request)
        self._session.add(model)
        await self._session.flush()
    
    async def get(self, request_id: UUID) -> ApprovalRequest | None:
        result = await self._session.execute(
            select(ApprovalRequestModel).where(ApprovalRequestModel.id == request_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None
    
    async def update(self, request: ApprovalRequest) -> None:
        result = await self._session.execute(
            select(ApprovalRequestModel).where(ApprovalRequestModel.id == request.id)
        )
        model = result.scalar_one()
        model.update_from_entity(request)
        await self._session.flush()
    
    async def get_pending(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        query = (
            select(ApprovalRequestModel)
            .join(RunModel)
            .where(RunModel.tenant_id == tenant_id)
            .where(ApprovalRequestModel.state == ApprovalState.PENDING)
        )
        if run_id:
            query = query.where(ApprovalRequestModel.run_id == run_id)
        
        result = await self._session.execute(query)
        return [m.to_entity() for m in result.scalars().all()]
    
    async def expire_old(self) -> int:
        result = await self._session.execute(
            update(ApprovalRequestModel)
            .where(ApprovalRequestModel.state == ApprovalState.PENDING)
            .where(ApprovalRequestModel.expires_at < datetime.now(UTC))
            .values(state=ApprovalState.EXPIRED)
        )
        return result.rowcount
```

#### New: `app/infrastructure/db/repositories/audit.py`

```python
class SQLAuditRepository(AuditRepository):
    """SQL implementation of audit log repository."""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def add(self, entry: AuditEntry) -> None:
        model = AuditLogModel.from_entity(entry)
        self._session.add(model)
        await self._session.flush()
    
    async def query(...) -> list[AuditEntry]:
        # Implement with filters, pagination
        pass
```

---

## Integration with RunExecutor

### 11. Modified RunExecutor

#### Modified: `app/workers/executor.py`

```python
class RunExecutor:
    """Executor with tool security integration."""
    
    def __init__(
        self,
        ...,
        tool_execution_service: ToolExecutionService,  # NEW
        approval_coordinator: ApprovalCoordinator,      # NEW
    ) -> None:
        ...
        self._tool_execution = tool_execution_service
        self._approvals = approval_coordinator
    
    async def _execute_step(self, run: Run) -> None:
        """Execute a single step with tool security."""
        step = self._get_next_step(run)
        if not step:
            return
        
        step.start()
        await self._run_repository.update_step(run.id, step)
        
        try:
            if step.kind == RunStepKind.TOOL_CALL:
                result = await self._execute_tool_call(run, step)
            elif step.kind == RunStepKind.APPROVAL_REQUEST:
                result = await self._handle_approval_step(run, step)
            else:
                result = await self._execute_other_step(run, step)
            
            step.complete(result.output_data)
            
        except ToolApprovalRequired as e:
            # Run transitions to AWAITING_APPROVAL
            run.request_approval()
            step.fail(f"Approval required: {e.approval_id}")
            
        except ToolExecutionDenied as e:
            step.fail(e.reason)
            # Run may continue or fail based on configuration
            
        except Exception as e:
            step.fail(str(e))
            raise
        
        await self._run_repository.update_step(run.id, step)
        await self._run_repository.update(run)
    
    async def _execute_tool_call(self, run: Run, step: RunStep) -> ToolExecutionResult:
        """Execute tool call with security checks."""
        tool_name = step.input_data.get("tool_name")
        action = step.input_data.get("action", "execute")
        input_data = step.input_data.get("input", {})
        resource = step.input_data.get("resource")
        
        if not tool_name:
            raise ValueError("Tool name required for tool_call step")
        
        # Get agent version ID from run
        agent_version_id = run.agent_version_id
        
        # Execute with security
        result = await self._tool_execution.execute_tool(
            run=run,
            agent_version_id=agent_version_id,
            tool_name=tool_name,
            action=action,
            input_data=input_data,
            resource=resource,
            context={
                "run_id": str(run.id),
                "step_sequence": step.sequence,
                "tenant_id": str(run.tenant_id),
            },
        )
        
        if result.awaiting_approval:
            raise ToolApprovalRequired(approval_id=result.approval_id)
        
        if not result.success:
            raise ToolExecutionDenied(reason=result.reason)
        
        return result
    
    async def _handle_approval_step(self, run: Run, step: RunStep) -> StepResult:
        """Handle explicit approval request step."""
        # This allows agents to explicitly request approval in their logic
        approval_id = step.input_data.get("approval_id")
        if not approval_id:
            raise ValueError("approval_id required for approval_request step")
        
        # Check approval status
        request = await self._approvals.get(approval_id)
        if not request:
            raise ValueError(f"Approval request {approval_id} not found")
        
        if request.state == ApprovalState.APPROVED:
            return StepResult(output_data=request.response_data or {})
        elif request.state == ApprovalState.DENIED:
            raise ToolExecutionDenied(reason=request.denial_reason or "Approval denied")
        elif request.state == ApprovalState.EXPIRED:
            raise ToolExecutionDenied(reason="Approval request expired")
        else:
            # Still pending - transition run to awaiting approval
            run.request_approval()
            raise ToolApprovalRequired(approval_id=approval_id)
```

---

## API Layer Implementation

### 12. Approval API Endpoints

#### New: `app/api/v1/approvals/router.py`

```python
router = APIRouter(prefix="/approvals", tags=["approvals"])

@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    tenant_id: UUID = Depends(get_current_tenant),
    run_id: UUID | None = Query(None),
    state: ApprovalState | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:read")),
) -> ApprovalListResponse:
    """List approval requests for tenant."""
    approvals = await approval_coordinator.get_pending_approvals(
        tenant_id=tenant_id,
        run_id=run_id,
    )
    # Filter by state if provided
    if state:
        approvals = [a for a in approvals if a.state == state]
    
    return ApprovalListResponse(
        approvals=approvals[offset:offset+limit],
        total=len(approvals),
    )

@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:read")),
) -> ApprovalResponse:
    """Get approval request details."""
    request = await approval_coordinator.get(approval_id)
    if not request or request.tenant_id != tenant_id:
        raise NotFoundError("Approval request not found")
    return ApprovalResponse.from_entity(request)

@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: UUID,
    response: ApprovalDecisionRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:write")),
) -> ApprovalResponse:
    """Approve a pending request."""
    request = await approval_coordinator.respond_to_approval(
        request_id=approval_id,
        approved=True,
        responded_by=auth.user_id,
        response_data=response.response_data,
    )
    return ApprovalResponse.from_entity(request)

@router.post("/{approval_id}/deny", response_model=ApprovalResponse)
async def deny_request(
    approval_id: UUID,
    response: ApprovalDecisionRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:write")),
) -> ApprovalResponse:
    """Deny a pending request."""
    if not response.denial_reason:
        raise ValidationError("Denial reason required")
    
    request = await approval_coordinator.respond_to_approval(
        request_id=approval_id,
        approved=False,
        responded_by=auth.user_id,
        denial_reason=response.denial_reason,
    )
    return ApprovalResponse.from_entity(request)

@router.post("/{approval_id}/cancel", response_model=ApprovalResponse)
async def cancel_request(
    approval_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:write")),
) -> ApprovalResponse:
    """Cancel a pending request."""
    request = await approval_coordinator.get(approval_id)
    if not request or request.tenant_id != tenant_id:
        raise NotFoundError("Approval request not found")
    
    request.cancel("Cancelled by user")
    await approval_coordinator.update(request)
    return ApprovalResponse.from_entity(request)
```

### 13. Audit Log API Endpoints

#### New: `app/api/v1/audit/router.py`

```python
router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    tenant_id: UUID = Depends(get_current_tenant),
    run_id: UUID | None = Query(None),
    event_type: AuditEventType | None = Query(None),
    tool_name: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    auth: AuthContext = Depends(require_scopes("audit:read")),
) -> AuditLogListResponse:
    """Query audit logs."""
    entries = await audit_logger.query(
        tenant_id=tenant_id,
        run_id=run_id,
        event_types=[event_type] if event_type else None,
        tool_name=tool_name,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    total = await audit_logger.count(...)
    
    return AuditLogListResponse(entries=entries, total=total)

@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    tenant_id: UUID = Depends(get_current_tenant),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    auth: AuthContext = Depends(require_scopes("audit:read")),
) -> AuditStatsResponse:
    """Get audit statistics."""
    stats = await audit_logger.get_stats(tenant_id, start_time, end_time)
    return AuditStatsResponse(**stats)
```

---

## Schemas

#### New: `app/api/v1/schemas/approvals.py`

```python
class ApprovalDecisionRequest(BaseModel):
    """Request to approve/deny an approval."""
    response_data: dict[str, Any] | None = Field(
        None, description="Response data for approval"
    )
    denial_reason: str | None = Field(
        None, description="Reason for denial (required when denying)"
    )

class ApprovalResponse(BaseModel):
    """Approval request response."""
    id: UUID
    run_id: UUID
    step_sequence: int
    approval_type: ApprovalType
    state: ApprovalState
    tool_name: str
    action: str
    resource: str | None
    input_data: dict[str, Any]
    policy_reason: str
    requested_by: str
    requested_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    denial_reason: str | None
    expires_at: datetime | None
    response_data: dict[str, Any] | None
    
    @classmethod
    def from_entity(cls, request: ApprovalRequest) -> "ApprovalResponse":
        return cls(...)

class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalResponse]
    total: int
```

#### New: `app/api/v1/schemas/audit.py`

```python
class AuditLogEntry(BaseModel):
    id: UUID
    timestamp: datetime
    tenant_id: UUID
    run_id: UUID | None
    agent_version_id: UUID | None
    event_type: AuditEventType
    tool_name: str | None
    action: str | None
    resource: str | None
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    success: bool
    reason: str
    metadata: dict[str, Any]
    approval_id: UUID | None
    user_id: str | None

class AuditLogListResponse(BaseModel):
    entries: list[AuditLogEntry]
    total: int

class AuditStatsResponse(BaseModel):
    total_events: int
    by_event_type: dict[AuditEventType, int]
    by_tool: dict[str, int]
    approval_rate: float
    denial_rate: float
    rate_limit_hits: int
```

---

## Testing Strategy

### 14. Test Files

| Test File | Purpose |
|-----------|---------|
| `tests/unit/test_policy_evaluator.py` | Policy evaluation logic |
| `tests/unit/test_approval_coordinator.py` | Approval workflow |
| `tests/unit/test_tool_execution_service.py` | Tool execution with security |
| `tests/unit/test_audit_logger.py` | Audit logging |
| `tests/integration/test_approval_api.py` | Approval API endpoints |
| `tests/integration/test_audit_api.py` | Audit API endpoints |
| `tests/integration/test_executor_tool_security.py` | Executor integration |

### Key Test Scenarios

```python
# Policy Evaluation Tests
async def test_policy_allow_action():
    policy = ToolPolicy(tool_name="web_search", rules=[
        PolicyRule(type=PolicyType.ALLOW, condition=PolicyCondition(action="search"), 
                   effect=PolicyEffect(allow=True))
    ])
    decision = PolicyEvaluator.evaluate(policy, "search")
    assert decision.allowed

async def test_policy_require_approval():
    policy = ToolPolicy(tool_name="file_write", rules=[
        PolicyRule(type=PolicyType.REQUIRE_APPROVAL, condition=PolicyCondition(action="write"),
                   effect=PolicyEffect(allow=True, require_approval=True))
    ])
    decision = PolicyEvaluator.evaluate(policy, "write", resource="/etc/passwd")
    assert decision.require_approval
    assert not decision.allowed

# Approval Flow Tests
async def test_approval_request_flow():
    # Request approval
    request = await coordinator.request_approval(...)
    assert request.state == ApprovalState.PENDING
    
    # Approve
    request = await coordinator.respond_to_approval(request.id, True, "user1")
    assert request.state == ApprovalState.APPROVED
    
    # Try to approve again - should fail
    with pytest.raises(ValueError):
        await coordinator.respond_to_approval(request.id, True, "user2")

# Executor Integration Tests
async def test_executor_tool_requires_approval():
    # Setup run with tool that requires approval
    # Execute step
    # Verify run transitions to AWAITING_APPROVAL
    # Verify approval request created
    pass
```

---

## Implementation Phases

### Phase 1: Domain Layer (Days 1-3)
- [ ] Create `PolicyCondition`, `PolicyEffect`, `ToolPolicy`, `PolicyRule` value objects
- [ ] Create `PolicyDecision`, `RateLimitInfo` value objects
- [ ] Implement `PolicyEvaluator` domain service
- [ ] Create `ApprovalRequest` entity with state machine
- [ ] Create `ApprovalType`, `ApprovalState` enums
- [ ] Implement `ApprovalCoordinator` domain service
- [ ] Update `ToolGrant` entity to use `ToolPolicy`
- [ ] Add unit tests for all domain components

### Phase 2: Application Services (Days 4-5)
- [ ] Implement `ToolExecutionService`
- [ ] Implement `AuditLogger` service
- [ ] Create `AuditEventType` enum and `AuditEntry` value object
- [ ] Add repository interfaces (abstract base classes)
- [ ] Add unit tests for services

### Phase 3: Infrastructure (Days 6-7)
- [ ] Create database migration for `approval_requests` table
- [ ] Create database migration for `audit_logs` table
- [ ] Update `ToolGrantModel` with `is_active` and policy JSON
- [ ] Implement `SQLApprovalRepository`
- [ ] Implement `SQLAuditRepository`
- [ ] Implement `RateLimiter` (Redis-based)
- [ ] Add integration tests for repositories

### Phase 4: Executor Integration (Days 8-9)
- [ ] Modify `RunExecutor` to use `ToolExecutionService`
- [ ] Add `TOOL_CALL` step handling with security checks
- [ ] Add `APPROVAL_REQUEST` step handling
- [ ] Handle `ToolApprovalRequired` and `ToolExecutionDenied` exceptions
- [ ] Update run state transitions
- [ ] Add integration tests for executor

### Phase 5: API Layer (Days 10-11)
- [ ] Create approval API endpoints
- [ ] Create audit log API endpoints
- [ ] Add request/response schemas
- [ ] Add authentication/authorization (scopes)
- [ ] Add API integration tests

### Phase 6: Polish & Documentation (Days 12-14)
- [ ] Add OpenAPI documentation
- [ ] Create policy configuration examples
- [ ] Add integration test for full approval flow
- [ ] Performance testing for policy evaluation
- [ ] Security review
- [ ] Update CHANGELOG

---

## Configuration

### Policy Configuration Example

```yaml
# config/tool_policies.yaml
tool_policies:
  web_search:
    version: 1
    default_effect:
      allow: true
      max_calls_per_minute: 60
    rules:
      - priority: 10
        condition:
          action: "search"
          resource: "*.internal.*"
        effect:
          allow: false
          require_approval: true
  
  file_write:
    version: 1
    default_effect:
      allow: false
      require_approval: true
    rules:
      - priority: 10
        condition:
          action: "write"
          resource: "*.tmp"
        effect:
          allow: true
          max_calls_per_hour: 100
      - priority: 5
        condition:
          expression: "context.user.role == 'admin'"
        effect:
          allow: true
```

---

## Security Considerations

1. **Policy Injection Prevention**: All policies validated at creation time
2. **CEL Expression Sandboxing**: Use restricted CEL environment
3. **Audit Log Integrity**: Append-only, cryptographic hashing
4. **Approval Request Expiry**: Automatic expiration prevents stale requests
5. **Rate Limiting**: Per-tenant, per-tool, per-action limits
6. **Input Sanitization**: All tool inputs validated before execution

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| Policy evaluation latency | < 5ms p99 |
| Approval request creation | < 50ms p99 |
| Audit log write | < 10ms p99 (async) |
| Rate limit check | < 2ms p99 (Redis) |
| Memory overhead per run | < 1MB |

---

## Rollback Plan

If issues arise:
1. Feature flag `tool_security_enabled` to disable new checks
2. Database migrations are backward compatible
3. Old `ToolGrant.policy` dict still supported via migration
4. Executor falls back to direct tool execution if service unavailable

---

## Dependencies

### New Dependencies
```toml
[tool.poetry.dependencies]
celpy = "^0.2.0"  # CEL expression evaluation
redis = "^5.0.0"   # Rate limiting
```

---

## Success Criteria

- [ ] All existing tests pass
- [ ] New unit tests cover >90% of new code
- [ ] Integration tests cover full approval flow
- [ ] Policy evaluation < 5ms p99
- [ ] No regression in run execution performance
- [ ] Audit logs queryable via API
- [ ] Human approval workflow functional end-to-end
- [ ] Rate limiting enforced correctly
- [ ] Security review passed