"""Idempotency middleware for API endpoints."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.errors.exceptions import ConflictError
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle idempotency for API requests."""

    def __init__(self, app, idempotency_service, excluded_paths: list[str] | None = None) -> None:
        """Initialize idempotency middleware.

        Args:
            app: ASGI application
            idempotency_service: Idempotency service instance
            excluded_paths: List of paths to exclude from idempotency checking
        """
        super().__init__(app)
        self._idempotency_service = idempotency_service
        self._excluded_paths = excluded_paths or [
            "/healthz",
            "/readyz",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request with idempotency handling.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response with idempotency handling applied
        """
        # Skip idempotency for excluded paths and non-mutating methods
        if request.method in ["GET", "HEAD", "OPTIONS"] or self._is_excluded_path(request.url.path):
            return await call_next(request)

        # Extract idempotency key
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # For mutating operations without idempotency key, proceed normally
            # but log a warning in production
            return await call_next(request)

        # Get tenant ID from request state (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            logger.warning("No tenant_id in request state for idempotency check")
            return await call_next(request)

        # Check for existing operation
        operation = f"{request.method} {request.url.path}"
        request_data = await self._extract_request_data(request)

        result = await self._idempotency_service.check_and_store(
            key=idempotency_key,
            tenant_id=tenant_id,
            operation=operation,
            request_data=request_data,
        )

        # If duplicate, return cached response
        if result.is_duplicate and result.cached_response:
            logger.info(
                "Returning cached response for duplicate request",
                extra={
                    "idempotency_key": idempotency_key,
                    "tenant_id": str(tenant_id),
                    "operation": operation,
                },
            )
            return JSONResponse(
                content=result.cached_response,
                status_code=200,
                headers={
                    "X-Idempotency-Key": idempotency_key,
                    "X-Cached-Response": "true",
                },
            )

        # If duplicate but no cached response, return conflict
        if result.is_duplicate:
            raise ConflictError(
                message="Request already in progress",
                detail="A request with this idempotency key is already being processed",
            )

        # Process the request
        response = await call_next(request)

        # Store response if successful
        if response.status_code < 300:
            try:
                response_data = await self._extract_response_data(response)
                request_id = getattr(request.state, "request_id", None)

                await self._idempotency_service.store_response(
                    key=idempotency_key,
                    tenant_id=tenant_id,
                    response=response_data,
                    request_id=request_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to store idempotency response",
                    extra={
                        "idempotency_key": idempotency_key,
                        "tenant_id": str(tenant_id),
                        "error": str(e),
                    },
                )

        return response

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from idempotency handling.

        Args:
            path: Request path

        Returns:
            True if excluded, False otherwise
        """
        return any(path.startswith(excluded) for excluded in self._excluded_paths)

    async def _extract_request_data(self, request: Request) -> dict[str, Any] | None:
        """Extract request data for idempotency comparison.

        Args:
            request: Incoming request

        Returns:
            Request data dictionary or None
        """
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                if body:
                    return json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.warning(
                "Failed to extract request data for idempotency",
                extra={"error": str(e)},
            )
        return None

    async def _extract_response_data(self, response: Response) -> dict[str, Any]:
        """Extract response data for idempotency caching.

        Args:
            response: Response object

        Returns:
            Response data dictionary
        """
        try:
            if isinstance(response, JSONResponse):
                # Get the body from the response
                body = getattr(response, "body", b"")
                if body:
                    return json.loads(body.decode("utf-8"))
                # If body is not set, try to get from the content
                if hasattr(response, "body_obj"):
                    content = response.body_obj
                    if hasattr(content, "decode"):
                        return json.loads(content.decode("utf-8"))
        except Exception as e:
            logger.warning(
                "Failed to extract response data for idempotency",
                extra={"error": str(e)},
            )
        return {}
