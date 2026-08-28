"""Typed configuration management using Pydantic Settings.

All configuration values are loaded once at startup from environment variables
or a .env file. Required values are validated and missing values cause
immediate, clear failure. The :func:`get_settings` function returns a cached
singleton.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


def _parse_cors_origins(value: str | list[str]) -> list[str]:
    """Allow CORS origins as a comma-separated string or list."""
    if isinstance(value, str):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    return value


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AIAgentX"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/v1"

    secret_key: str = Field(min_length=16)
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_echo: bool = False

    redis_pool_max_connections: int = 10
    redis_socket_timeout: int = 5

    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    access_token_expire_minutes: int = 30

    # Provider configuration
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_provider: str = "fake"  # Default to fake provider for testing
    default_model: str = "gpt-4o"

    # Circuit breaker configuration
    circuit_breaker_failure_rate_threshold: float = 0.5
    circuit_breaker_minimum_requests: int = 10
    circuit_breaker_open_timeout_seconds: int = 60
    circuit_breaker_half_open_max_calls: int = 3

    # Retry configuration
    provider_max_retries: int = 2
    provider_initial_backoff_ms: int = 1000
    provider_max_backoff_ms: int = 10000
    provider_backoff_multiplier: float = 2.0
    provider_retry_jitter: bool = True

    # Provider timeouts
    provider_timeout_seconds: int = 45
    provider_connect_timeout_seconds: int = 3

    # Fallback configuration
    fallback_enabled: bool = False
    fallback_providers: str = ""
    fallback_max_attempts: int = 2

    # Pricing configuration (per 1M tokens in USD)
    pricing_openai_gpt4o_prompt_price: float = 2.50
    pricing_openai_gpt4o_completion_price: float = 10.00
    pricing_anthropic_claude3_opus_prompt_price: float = 15.00
    pricing_anthropic_claude3_opus_completion_price: float = 75.00

    # Observability configuration
    # OpenTelemetry
    otel_enabled: bool = True
    otel_service_name: str = "aiagentx-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_exporter_otlp_insecure: bool = True
    otel_traces_sampler: str = "parentbased_traceidratio"
    otel_traces_sampler_arg: float = 0.1
    otel_propagators: str = "tracecontext,baggage"

    # Structured Logging
    log_format: str = "json"  # json or console
    log_redact_keys: str = "password,secret,token,api_key,authorization,credit_card,ssn"
    log_level_overrides: str = ""

    # Prometheus Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    metrics_buckets: str = "0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0,2.5,5.0,10.0"

    # Audit System
    audit_enabled: bool = True
    audit_outbox_table: str = "audit_outbox"
    audit_batch_size: int = 100
    audit_flush_interval_seconds: int = 5
    audit_retention_days: int = 2555  # 7 years
    audit_tamper_proof: bool = True

    # Backup & Recovery
    backup_enabled: bool = False
    backup_schedule: str = "0 2 * * *"  # Daily at 2 AM UTC
    backup_retention_days: int = 30
    backup_encryption_key: str = ""
    backup_storage_path: str = "/backups"
    backup_s3_bucket: str = ""
    backup_s3_prefix: str = "aiagentx/backups"

    @property
    def log_redact_keys_list(self) -> list[str]:
        """Return log redact keys as a list."""
        return [k.strip() for k in self.log_redact_keys.split(",") if k.strip()]

    @property
    def log_level_overrides_dict(self) -> dict[str, str]:
        """Return log level overrides as a dict."""
        if not self.log_level_overrides.strip():
            return {}
        import json

        return json.loads(self.log_level_overrides)  # type: ignore[no-any-return]

    @property
    def metrics_buckets_list(self) -> list[float]:
        """Return metrics buckets as a list of floats."""
        return [float(b.strip()) for b in self.metrics_buckets.split(",") if b.strip()]

    @property
    def fallback_providers_list(self) -> list[str]:
        """Return fallback providers as a list."""
        if not self.fallback_providers:
            return []
        return [
            p.strip() for p in self.fallback_providers.split(",") if p.strip()
        ]

    @field_validator("database_url")
    @classmethod
    def _validate_async_driver(cls, value: str) -> str:
        if not value:
            raise ValueError("database_url is required")
        if "asyncpg" not in value and "psycopg" not in value:
            raise ValueError("database_url must use an async driver (asyncpg or psycopg async)")
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins as a list."""
        return _parse_cors_origins(self.cors_origins)

    @field_validator("circuit_breaker_failure_rate_threshold")
    @classmethod
    def _validate_failure_rate_threshold(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("Failure rate threshold must be between 0 and 1")
        return value

    @field_validator("provider_backoff_multiplier")
    @classmethod
    def _validate_backoff_multiplier(cls, value: float) -> float:
        if value <= 1.0:
            raise ValueError("Backoff multiplier must be greater than 1.0")
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_test(self) -> bool:
        return self.environment == Environment.TEST


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
