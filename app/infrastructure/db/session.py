"""Database session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from app.settings import Settings


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the configured engine."""
    from app.infrastructure.db.engine import create_engine

    engine = create_engine(settings)
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an ``AsyncSession`` per request."""
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session using app settings."""
    from app.settings import get_settings
    from app.infrastructure.db.engine import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    settings = get_settings()
    engine = create_engine(settings)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
