"""Health check endpoints: ``/healthz`` and ``/readyz``.

- ``/healthz`` is a pure liveness check; it must never call external
  dependencies. It returns 200 as long as the process is running.
- ``/readyz`` performs dependency checks (database, Redis, migration
  version) and returns 503 if any required dependency is unhealthy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.infrastructure.cache.redis_client import check_redis_health
from app.infrastructure.db.engine import check_database_health, get_migration_version

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncEngine
else:
    Redis = object
    AsyncEngine = object

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Return 200 as long as the process is running. No dependency calls."""
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
async def readiness(request: Request) -> JSONResponse:
    """Verify that the application is ready to serve traffic.

    Checks the database, Redis, and Alembic migration version. Returns 503
    with per-check details if any required check fails.
    """
    engine: AsyncEngine | None = getattr(request.app.state, "db_engine", None)
    redis: Redis[str] | None = getattr(request.app.state, "redis_client", None)

    db_ok = await check_database_health(engine) if engine is not None else False
    redis_ok = await check_redis_health(redis) if redis is not None else False

    migration_version: str | None = None
    if engine is not None:
        try:
            from app.settings import get_settings

            settings = get_settings()
            migration_version = get_migration_version(
                settings.database_url, "app/infrastructure/db/migrations"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read migration version: %s", exc)

    checks: dict[str, dict[str, Any]] = {
        "database": {"status": "ok" if db_ok else "fail"},
        "redis": {"status": "ok" if redis_ok else "fail"},
        "migrations": {
            "status": "ok" if migration_version is not None else "fail",
            "version": migration_version,
        },
    }

    all_ok = all(c["status"] == "ok" for c in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
