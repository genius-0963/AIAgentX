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

    # Add provider health checks if provider service is available
    provider_service = getattr(request.app.state, "provider_service", None)
    if provider_service is not None:
        try:
            service_status = provider_service.get_service_status()
            provider_health = service_status.get("health_status", {})
            checks["providers"] = {
                "status": "ok" if provider_health.get("overall_healthy", False) else "degraded",
                "details": provider_health,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not get provider health: %s", exc)
            checks["providers"] = {"status": "fail", "error": str(exc)}

    all_ok = all(c["status"] == "ok" for c in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )


@router.get("/providers", summary="Provider health status")
async def provider_health(request: Request) -> JSONResponse:
    """Get detailed health status for all providers.

    Returns provider health, circuit breaker status, and fallback configuration.
    """
    provider_service = getattr(request.app.state, "provider_service", None)

    if provider_service is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "error": "Provider service not available"},
        )

    try:
        service_status = provider_service.get_service_status()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "service": service_status},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get provider service status: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "error": str(exc)},
        )


@router.get("/providers/{provider_name}", summary="Individual provider health")
async def provider_health_detail(request: Request, provider_name: str) -> JSONResponse:
    """Get detailed health status for a specific provider.

    Args:
        provider_name: Name of the provider to check

    Returns:
        Detailed health status for the provider
    """
    provider_service = getattr(request.app.state, "provider_service", None)

    if provider_service is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "error": "Provider service not available"},
        )

    try:
        health = provider_service.get_provider_health(provider_name)
        circuit_status = provider_service.get_circuit_breaker_status(provider_name)

        if health is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "not_found", "provider": provider_name},
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ok",
                "provider": provider_name,
                "health": health,
                "circuit_breaker": circuit_status,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get provider health: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "error": str(exc)},
        )
