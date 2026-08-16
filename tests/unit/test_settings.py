"""Test settings module - typed configuration with Pydantic Settings."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure we have a minimal env for tests
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-do-not-use-in-prod")


def test_settings_loads_defaults() -> None:
    from app.settings import Settings

    settings = Settings(_env_file=None, environment="test")
    assert settings.app_name == "AIAgentX"
    assert settings.environment == "test"
    assert settings.api_prefix == "/v1"
    assert settings.log_level == "INFO"


def test_settings_requires_database_url() -> None:
    from app.settings import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, database_url="")
    assert "database_url" in str(exc_info.value)


def test_settings_uses_environment_variables(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_NAME=CustomApp\n"
        "ENVIRONMENT=production\n"
        "DATABASE_URL=postgresql+asyncpg://prod:5432/main\n"
        "REDIS_URL=redis://prod:6379/0\n"
        "SECRET_KEY=prod-secret\n"
    )
    from app.settings import Settings

    settings = Settings(_env_file=str(env_file))
    assert settings.app_name == "CustomApp"
    assert settings.environment == "production"


def test_settings_database_url_must_be_async_driver() -> None:
    from app.settings import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@host:5432/db",
        )
    assert "asyncpg" in str(exc_info.value).lower()


def test_settings_redis_url_validation() -> None:
    from app.settings import Settings

    settings = Settings(_env_file=None, redis_url="redis://localhost:6379/0")
    assert settings.redis_url.startswith("redis://")


def test_settings_environment_enum() -> None:
    from app.settings import Environment, Settings

    dev = Settings(_env_file=None, environment="development").environment
    staging = Settings(_env_file=None, environment="staging").environment
    prod = Settings(_env_file=None, environment="production").environment
    assert dev == Environment.DEVELOPMENT
    assert staging == Environment.STAGING
    assert prod == Environment.PRODUCTION


def test_settings_invalid_environment_rejected() -> None:
    from app.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="invalid-env")


def test_settings_cors_origins_parsing() -> None:
    from app.settings import Settings

    settings = Settings(_env_file=None, cors_origins="http://localhost:3000,http://localhost:8000")
    assert "http://localhost:3000" in settings.cors_origins
    assert "http://localhost:8000" in settings.cors_origins


def test_settings_database_pool_configuration() -> None:
    from app.settings import Settings

    settings = Settings(_env_file=None, db_pool_size=10, db_max_overflow=20, db_pool_timeout=30)
    assert settings.db_pool_size == 10
    assert settings.db_max_overflow == 20
    assert settings.db_pool_timeout == 30


def test_settings_singleton_returns_same_instance() -> None:
    from app.settings import get_settings

    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
