"""HTTP middleware: request ID, access logging, error handling.

All middleware in this package operates on :class:`fastapi.Request` and
:class:`fastapi.Response` only — they do not touch domain or application code.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def _new_request_id() -> str:
    return uuid.uuid4().hex


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every request and response.

    Honours an incoming ``X-Request-ID`` header if present, otherwise mints
    a new UUID4 hex string.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER.lower()) or _new_request_id()
        request.state.request_id = request_id

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            client=request.client.host if request.client else None,
        )
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Convert unhandled exceptions to a structured 500 response.

    Domain and validation errors raised by FastAPI handlers are converted to
    structured responses by FastAPI itself; this middleware is the last
    line of defence.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001
            request_id = getattr(request.state, "request_id", None) or _new_request_id()
            logger.exception("unhandled_exception", error=str(exc), path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "type": "https://api.aiagentx.com/errors/internal_error",
                        "title": "Internal Server Error",
                        "status": 500,
                        "detail": "An unexpected error occurred.",
                        "request_id": request_id,
                        "code": "INTERNAL_ERROR",
                    }
                },
            )
