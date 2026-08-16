"""Test database module - async engine, session factory, health check."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.mark.asyncio
async def test_create_engine_returns_async_engine() -> None:
    from app.infrastructure.db.engine import create_engine
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )
    engine = create_engine(settings)
    assert isinstance(engine, AsyncEngine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_session_yields_session() -> None:
    from app.infrastructure.db.engine import get_session_factory
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )
    factory = get_session_factory(settings)

    async with factory() as session:
        assert isinstance(session, AsyncSession)


@pytest.mark.asyncio
async def test_check_database_health_returns_true_on_success() -> None:
    from app.infrastructure.db.engine import check_database_health

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    mock_engine.connect = MagicMock(return_value=cm)

    result = await check_database_health(mock_engine)
    assert result is True


@pytest.mark.asyncio
async def test_check_database_health_returns_false_on_failure() -> None:
    from app.infrastructure.db.engine import check_database_health

    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("connection refused")

    result = await check_database_health(mock_engine)
    assert result is False


def test_get_migration_version_returns_none_on_empty() -> None:
    from app.infrastructure.db.engine import get_migration_version

    with patch("alembic.command.current") as mock_current:
        result = get_migration_version("postgresql+asyncpg://x", "migrations")
        assert mock_current.called
        # Without a real alembic setup, current() raises → returns None
        assert result is None


def test_get_migration_version_returns_none_on_exception() -> None:
    from app.infrastructure.db.engine import get_migration_version

    with patch("alembic.command.current", side_effect=Exception("boom")):
        result = get_migration_version("postgresql+asyncpg://x", "migrations")
        assert result is None
