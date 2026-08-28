"""Test FastAPI app factory, health endpoints, and middleware."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_db_engine() -> object:
    from unittest.mock import AsyncMock, MagicMock

    engine = MagicMock()
    cm = MagicMock()
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=1)))
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    engine.connect = MagicMock(return_value=cm)
    return engine


@pytest.fixture
def mock_redis() -> object:
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture
def app_with_dependencies(mock_db_engine: object, mock_redis: object) -> FastAPI:
    from app.main import create_app
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )
    return create_app(
        settings=settings,
        db_engine=mock_db_engine,  # type: ignore[arg-type]
        redis_client=mock_redis,  # type: ignore[arg-type]
    )


@pytest.fixture
async def client(app_with_dependencies: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_with_dependencies)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_healthz_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_readyz_returns_ok_when_dependencies_healthy(
    client: AsyncClient,
) -> None:
    from unittest.mock import patch

    with patch("app.api.v1.health.get_migration_version", return_value="0001_initial"):
        response = await client.get("/readyz")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["database"]["status"] == "ok"
        assert body["checks"]["redis"]["status"] == "ok"
        assert body["checks"]["migrations"]["status"] == "ok"
        assert body["checks"]["migrations"]["version"] == "0001_initial"


@pytest.mark.asyncio
async def test_readyz_returns_503_when_db_unhealthy(mock_redis: object) -> None:
    from unittest.mock import MagicMock

    from httpx import ASGITransport, AsyncClient

    from app.main import create_app
    from app.settings import Settings

    bad_db = MagicMock()
    bad_db.connect.side_effect = Exception("db down")

    settings = Settings(
        _env_file=None,
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )
    app: FastAPI = create_app(
        settings=settings,
        db_engine=bad_db,
        redis_client=mock_redis,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/readyz")
        assert response.status_code == 503
        body = response.json()
        assert body["checks"]["database"]["status"] == "fail"


@pytest.mark.asyncio
async def test_request_id_middleware_adds_header(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_request_id_middleware_uses_provided_id(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"x-request-id": "my-id-123"})
    assert response.headers["x-request-id"] == "my-id-123"


@pytest.mark.asyncio
async def test_openapi_docs_generated(app_with_dependencies: FastAPI) -> None:
    schema = app_with_dependencies.openapi()
    assert schema["info"]["title"]
    assert "/healthz" in schema["paths"]
    assert "/readyz" in schema["paths"]


@pytest.mark.asyncio
async def test_cors_headers_on_options(client: AsyncClient) -> None:
    response = await client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_global_error_handler_returns_500_for_unhandled() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from httpx import ASGITransport, AsyncClient

    from app.main import create_app
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )
    db = MagicMock()
    redis = MagicMock()
    redis.ping = AsyncMock(return_value=True)
    app: FastAPI = create_app(settings=settings, db_engine=db, redis_client=redis)
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    # Mount a route that raises
    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/boom")
        assert response.status_code == 500
        body = response.json()
        # Error response has 'error' as top-level key per RFC 7807
        assert "error" in body
        assert "request_id" in body["error"]
        assert body["error"]["code"] == "INTERNAL_ERROR"
