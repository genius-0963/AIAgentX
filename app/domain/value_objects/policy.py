from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from celpy import Environment
from celpy.celtypes import MapType


class PolicyType(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMIT = "rate_limit"
    CONDITIONAL = "conditional"


@dataclass(frozen=True, slots=True)
class PolicyCondition:
    """Condition for policy evaluation."""
    action: str | None = None
    resource: str | None = None
    context: dict[str, Any] | None = None
    expression: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyEffect:
    """Effect when condition matches."""
    allow: bool = True
    requires_approval: bool = False
    max_calls_per_minute: int | None = None
    max_calls_per_hour: int | None = None
    max_calls_per_day: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """Single policy rule with condition and effect."""
    type: PolicyType
    condition: PolicyCondition
    effect: PolicyEffect
    priority: int = 0


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Complete policy for a tool."""
    tool_name: str
    version: int = 1
    rules: list[PolicyRule] = field(default_factory=list)
    default_effect: PolicyEffect = field(default_factory=lambda: PolicyEffect(allow=False))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    """Rate limit information."""
    limit: int
    remaining: int
    reset_at: datetime
    scope: str


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Result of policy evaluation."""
    allowed: bool
    requires_approval: bool = False
    reason: str = ""
    matched_rule: PolicyRule | None = None
    rate_limit: RateLimitInfo | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, reason: str = "", **kwargs) -> PolicyDecision:
        return cls(allowed=True, reason=reason, **kwargs)

    @classmethod
    def deny(cls, reason: str, **kwargs) -> PolicyDecision:
        return cls(allowed=False, reason=reason, **kwargs)

    @classmethod
    def require_approval(cls, reason: str, **kwargs) -> PolicyDecision:
        return cls(allowed=False, requires_approval=True, reason=reason, **kwargs)


class PolicyEvaluator:
    """Evaluates tool policies against requests."""

    _cel_env: Environment = Environment()

    @classmethod
    def evaluate(
        cls,
        policy: ToolPolicy,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate policy rules in priority order."""
        context = context or {}

        sorted_rules = sorted(policy.rules, key=lambda r: -r.priority)

        for rule in sorted_rules:
            if cls._matches_condition(rule.condition, action, resource, context):
                return cls._apply_effect(rule.effect, rule, context)

        return cls._apply_effect(policy.default_effect, None, context)

    @classmethod
    def _matches_condition(
        cls,
        condition: PolicyCondition,
        action: str,
        resource: str | None,
        context: dict[str, Any],
    ) -> bool:
        """Check if condition matches request."""
        if condition.action and condition.action != action:
            return False
        if condition.resource and resource:
            if not cls._match_pattern(condition.resource, resource):
                return False
        if condition.expression:
            try:
                program = cls._cel_env.compile(condition.expression)
                runner = cls._cel_env.runner_class(cls._cel_env, program)
                # Convert context to CEL MapType
                cel_context = {"context": cls._dict_to_cel_map(context)}
                result = runner.evaluate(cel_context)
                return bool(result)
            except Exception:
                return False
        return True

    @staticmethod
    def _dict_to_cel_map(d: dict[str, Any]) -> MapType:
        """Convert a Python dict to CEL MapType recursively."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = PolicyEvaluator._dict_to_cel_map(value)
            elif isinstance(value, list):
                result[key] = [PolicyEvaluator._dict_to_cel_map(v) if isinstance(v, dict) else v for v in value]
            else:
                result[key] = value
        return MapType(result)

    @classmethod
    def _apply_effect(
        cls,
        effect: PolicyEffect,
        rule: PolicyRule | None,
        context: dict[str, Any],
    ) -> PolicyDecision:
        """Apply policy effect."""
        if effect.requires_approval:
            return PolicyDecision.require_approval(
                reason="Policy requires approval",
                matched_rule=rule,
                rate_limit=cls._build_rate_limit(effect),
            )

        if not effect.allow:
            return PolicyDecision.deny(
                reason="Policy denies access",
                matched_rule=rule,
            )

        return PolicyDecision.allow(
            reason="Policy allows access",
            matched_rule=rule,
            rate_limit=cls._build_rate_limit(effect),
        )

    @staticmethod
    def _match_pattern(pattern: str, value: str) -> bool:
        """Simple glob-style pattern matching."""
        import fnmatch
        return fnmatch.fnmatch(value, pattern)

    @classmethod
    def _build_rate_limit(cls, effect: PolicyEffect) -> RateLimitInfo | None:
        now = datetime.now()
        if effect.max_calls_per_minute:
            return RateLimitInfo(
                limit=effect.max_calls_per_minute,
                remaining=effect.max_calls_per_minute,
                reset_at=now.replace(second=0, microsecond=0) + timedelta(minutes=1),
                scope="minute",
            )
        if effect.max_calls_per_hour:
            return RateLimitInfo(
                limit=effect.max_calls_per_hour,
                remaining=effect.max_calls_per_hour,
                reset_at=now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
                scope="hour",
            )
        if effect.max_calls_per_day:
            return RateLimitInfo(
                limit=effect.max_calls_per_day,
                remaining=effect.max_calls_per_day,
                reset_at=now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
                scope="day",
            )
        return None