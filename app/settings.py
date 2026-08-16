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
