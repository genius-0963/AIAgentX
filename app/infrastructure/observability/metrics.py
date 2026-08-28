"""Prometheus metrics for the AIAgentX application."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, Info, generate_latest

if TYPE_CHECKING:
    from app.settings import Settings


# =============================================================================
# API Metrics
# =============================================================================

api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)

api_request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
)

api_requests_in_progress = Gauge(
    "api_requests_in_progress",
    "Number of API requests currently in progress",
    ["method", "endpoint"],
)


# =============================================================================
# Worker Metrics
# =============================================================================

worker_queue_age = Gauge(
    "worker_queue_age_seconds",
    "Age of queued runs in seconds",
    ["state"],
)

worker_active_runs = Gauge(
    "worker_active_runs",
    "Number of active runs per worker",
    ["worker_id"],
)

worker_lease_conflicts = Counter(
    "worker_lease_conflicts_total",
    "Total number of lease conflicts",
    ["worker_id"],
)

worker_runs_completed = Counter(
    "worker_runs_completed_total",
    "Total runs completed by worker",
    ["worker_id", "status"],
)

worker_poll_duration = Histogram(
    "worker_poll_duration_seconds",
    "Worker poll loop duration in seconds",
    ["worker_id"],
)


# =============================================================================
# Provider Metrics
# =============================================================================

provider_request_duration = Histogram(
    "provider_request_duration_seconds",
    "Provider request duration in seconds",
    ["provider", "model"],
)

provider_requests_total = Counter(
    "provider_requests_total",
    "Total provider requests",
    ["provider", "model", "status"],
)

provider_errors_total = Counter(
    "provider_errors_total",
    "Total provider errors",
    ["provider", "error_type"],
)

provider_circuit_state = Gauge(
    "provider_circuit_state",
    "Provider circuit breaker state (1=closed, 0=open, 0.5=half-open)",
    ["provider"],
)

provider_available_models = Gauge(
    "provider_available_models",
    "Number of available models per provider",
    ["provider"],
)

provider_fallback_activations = Counter(
    "provider_fallback_activations_total",
    "Total fallback activations",
    ["from_provider", "to_provider"],
)


# =============================================================================
# Tool Metrics
# =============================================================================

tool_execution_duration = Histogram(
    "tool_execution_duration_seconds",
    "Tool execution duration in seconds",
    ["tool_name", "classification"],
)

tool_executions_total = Counter(
    "tool_executions_total",
    "Total tool executions",
    ["tool_name", "status"],
)

tool_policy_denials_total = Counter(
    "tool_policy_denials_total",
    "Total tool policy denials",
    ["tool_name", "policy_reason"],
)

tool_active_executions = Gauge(
    "tool_active_executions",
    "Number of currently executing tool invocations",
    ["tool_name"],
)


# =============================================================================
# Database Metrics
# =============================================================================

db_pool_connections_total = Gauge(
    "db_pool_connections_total",
    "Total database connections in pool",
)

db_pool_connections_active = Gauge(
    "db_pool_connections_active",
    "Active database connections",
)

db_pool_connections_idle = Gauge(
    "db_pool_connections_idle",
    "Idle database connections",
)

db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
)

db_query_errors_total = Counter(
    "db_query_errors_total",
    "Total database query errors",
    ["operation", "table", "error_type"],
)

db_migration_version = Info(
    "db_migration_version",
    "Current database migration version",
)


# =============================================================================
# Redis Metrics
# =============================================================================

redis_pool_connections_total = Gauge(
    "redis_pool_connections_total",
    "Total Redis connections in pool",
)

redis_pool_connections_active = Gauge(
    "redis_pool_connections_active",
    "Active Redis connections",
)

redis_command_duration = Histogram(
    "redis_command_duration_seconds",
    "Redis command duration in seconds",
    ["command"],
)

redis_errors_total = Counter(
    "redis_errors_total",
    "Total Redis errors",
    ["command", "error_type"],
)


# =============================================================================
# Business Metrics
# =============================================================================

runs_total = Counter(
    "runs_total",
    "Total runs created",
    ["tenant_id", "status"],
)

run_duration = Histogram(
    "run_duration_seconds",
    "Run duration in seconds",
    ["tenant_id", "status"],
)

cost_usd_total = Counter(
    "cost_usd_total",
    "Total cost in USD",
    ["tenant_id", "provider"],
)

tokens_total = Counter(
    "tokens_total",
    "Total tokens used",
    ["tenant_id", "provider", "type"],
)

agents_total = Counter(
    "agents_total",
    "Total agents created",
    ["tenant_id"],
)

agent_versions_total = Counter(
    "agent_versions_total",
    "Total agent versions created",
    ["tenant_id", "agent_id"],
)

tool_grants_total = Counter(
    "tool_grants_total",
    "Total tool grants created",
    ["tenant_id", "agent_version_id"],
)

approvals_total = Counter(
    "approvals_total",
    "Total approvals",
    ["tenant_id", "status"],  # status: pending, approved, rejected
)


# =============================================================================
# System Metrics
# =============================================================================

app_info = Info(
    "app_info",
    "Application information",
)

app_uptime_seconds = Gauge(
    "app_uptime_seconds",
    "Application uptime in seconds",
)

app_start_time = time.time()


# =============================================================================
# Metrics Helper Functions
# =============================================================================

def init_metrics(settings: Settings) -> None:
    """Initialize metrics with application info.

    Args:
        settings: Application settings.
    """
    if not settings.metrics_enabled:
        return

    app_info.info({
        "version": "0.1.0",
        "service_name": settings.otel_service_name,
        "environment": settings.environment.value,
    })


def update_uptime() -> None:
    """Update the application uptime metric."""
    app_uptime_seconds.set(time.time() - app_start_time)


def record_api_request(method: str, endpoint: str, status: int, duration: float) -> None:
    """Record an API request metric.

    Args:
        method: HTTP method.
        endpoint: API endpoint.
        status: HTTP status code.
        duration: Request duration in seconds.
    """
    api_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    api_request_duration.labels(method=method, endpoint=endpoint).observe(duration)


def record_provider_request(provider: str, model: str, status: str, duration: float) -> None:
    """Record a provider request metric.

    Args:
        provider: Provider name.
        model: Model name.
        status: Request status (success, error).
        duration: Request duration in seconds.
    """
    provider_requests_total.labels(provider=provider, model=model, status=status).inc()
    provider_request_duration.labels(provider=provider, model=model).observe(duration)


def record_tool_execution(
    tool_name: str, classification: str, status: str, duration: float
) -> None:
    """Record a tool execution metric.

    Args:
        tool_name: Name of the tool.
        classification: Tool classification (read, write, etc.).
        status: Execution status (success, error).
        duration: Execution duration in seconds.
    """
    tool_executions_total.labels(tool_name=tool_name, status=status).inc()
    tool_execution_duration.labels(
        tool_name=tool_name, classification=classification
    ).observe(duration)


def record_cost(tenant_id: str, provider: str, cost_usd: float) -> None:
    """Record cost metric.

    Args:
        tenant_id: Tenant identifier.
        provider: Provider name.
        cost_usd: Cost in USD.
    """
    cost_usd_total.labels(tenant_id=tenant_id, provider=provider).inc(cost_usd)


def record_tokens(tenant_id: str, provider: str, token_type: str, count: int) -> None:
    """Record token usage metric.

    Args:
        tenant_id: Tenant identifier.
        provider: Provider name.
        token_type: Token type (prompt, completion).
        count: Number of tokens.
    """
    tokens_total.labels(tenant_id=tenant_id, provider=provider, type=token_type).inc(count)


def get_metrics() -> bytes:
    """Get metrics in Prometheus format.

    Returns:
        Metrics data as bytes.
    """
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics.

    Returns:
        Content type string.
    """
    return CONTENT_TYPE_LATEST