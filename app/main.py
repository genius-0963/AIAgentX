"""FastAPI application factory.

The factory accepts an optional ``db_engine`` and ``redis_client`` so the
caller can inject test doubles in unit tests. In production, the lifespan
context manager constructs and disposes real engines.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError as PydanticValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.errors.exceptions import APIError, ConflictError, NotFoundError, ValidationError
from app.api.errors.handlers import (
    api_error_handler,
    conflict_error_handler,
    not_found_error_handler,
    pydantic_validation_error_handler,
    validation_error_handler,
)
from app.api.middleware.middleware import (
    AccessLogMiddleware,
    ErrorHandlerMiddleware,
    RequestIDMiddleware,
)
from app.api.v1.agents import router as agents_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit import router as audit_router
from app.api.v1.health import router as health_router
from app.api.v1.runs import agent_runs_router
from app.api.v1.runs import router as runs_router
from app.infrastructure.cache.redis_client import create_redis_client
from app.infrastructure.db.engine import create_engine
from app.infrastructure.observability import (
    configure_logging,
    configure_tracing,
    get_metrics,
    get_metrics_content_type,
    init_metrics,
    instrument_fastapi_app,
)
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle: create and dispose engine + client."""
    settings: Settings = app.state.settings

    if not hasattr(app.state, "db_engine") or app.state.db_engine is None:
        app.state.db_engine = create_engine(settings)
        logger.info("Database engine created")

    if not hasattr(app.state, "redis_client") or app.state.redis_client is None:
        app.state.redis_client = create_redis_client(settings)
        logger.info("Redis client created")

    try:
        yield
    finally:
        if isinstance(app.state.db_engine, AsyncEngine):
            await app.state.db_engine.dispose()
        if isinstance(app.state.redis_client, Redis):
            await app.state.redis_client.aclose()  # type: ignore[attr-defined]


def create_app(
    settings: Settings | None = None,
    db_engine: AsyncEngine | None = None,
    redis_client: Redis[str] | None = None,
) -> FastAPI:
    """Construct and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    configure_logging(settings)

    # Configure OpenTelemetry tracing
    configure_tracing(settings)

    # Initialize Prometheus metrics
    init_metrics(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AIAgentX multi-agent runtime API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Instrument FastAPI with OpenTelemetry
    instrument_fastapi_app(app, settings)

    app.state.settings = settings
    if db_engine is not None:
        app.state.db_engine = db_engine
    if redis_client is not None:
        app.state.redis_client = redis_client

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Register error handlers
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(NotFoundError, not_found_error_handler)
    app.add_exception_handler(ConflictError, conflict_error_handler)
    app.add_exception_handler(PydanticValidationError, pydantic_validation_error_handler)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {
            "name": settings.app_name,
            "version": "0.1.0",
            "environment": settings.environment.value,
        }

    # Prometheus metrics endpoint
    if settings.metrics_enabled:

        @app.get(settings.metrics_path, include_in_schema=False)
        async def metrics() -> Response:
            return Response(content=get_metrics(), media_type=get_metrics_content_type())

    app.include_router(health_router)
    app.include_router(agents_router, prefix=settings.api_prefix)
    app.include_router(runs_router, prefix=settings.api_prefix)
    app.include_router(agent_runs_router, prefix=settings.api_prefix)
    app.include_router(approvals_router, prefix=settings.api_prefix)
    app.include_router(audit_router, prefix=settings.api_prefix)

    return app


app = create_app()
