"""Async database engine, session factory, and health check.

This module is the only place in the application that creates SQLAlchemy
engines. The application layer depends on the ``AsyncSession`` interface and
never constructs engines directly.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from app.settings import Settings

logger = logging.getLogger(__name__)


def create_engine(settings: Settings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from application settings."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        echo=settings.db_echo,
        future=True,
    )


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the configured engine."""
    engine = create_engine(settings)
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an ``AsyncSession`` per request."""
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health(engine: AsyncEngine) -> bool:
    """Return True if the database is reachable and responds to SELECT 1."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database health check failed: %s", exc)
        return False


def get_migration_version(database_url: str, script_location: str) -> str | None:
    """Return the current Alembic migration version, or None on failure."""
    try:
        from io import StringIO

        cfg = AlembicConfig()
        cfg.set_main_option("script_location", script_location)
        cfg.set_main_option("sqlalchemy.url", database_url)

        buf = StringIO()
        cfg.stdout = buf
        alembic_command.current(cfg)
        output = buf.getvalue().strip()
        if not output:
            return None
        first = output.split()[0]
        return None if first in {"head", "(empty)"} else first
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read migration version: %s", exc)
        return None
