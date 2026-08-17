"""Typed configuration management using Pydantic Settings.

All configuration values are loaded once at startup from environment variables
or a .env file. Required values are validated and missing values cause
immediate, clear failure. The :func:`get_settings` function returns a cached
singleton.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

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

    cors_origins: Annotated[list[str], Field(default_factory=lambda: ["http://localhost:3000"])]

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
    fallback_providers: list[str] = Field(default_factory=list)
    fallback_max_attempts: int = 2

    # Pricing configuration (per 1M tokens in USD)
    pricing_openai_gpt4o_prompt_price: float = 2.50
    pricing_openai_gpt4o_completion_price: float = 10.00
    pricing_anthropic_claude3_opus_prompt_price: float = 15.00
    pricing_anthropic_claude3_opus_completion_price: float = 75.00

    @field_validator("database_url")
    @classmethod
    def _validate_async_driver(cls, value: str) -> str:
        if not value:
            raise ValueError("database_url is required")
        if "asyncpg" not in value and "psycopg" not in value:
            raise ValueError("database_url must use an async driver (asyncpg or psycopg async)")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return _parse_cors_origins(value)
        return value

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
