"""Request body size limiting middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.errors.exceptions import PayloadTooLargeError
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    def __init__(
        self,
        app,
        max_size_bytes: int = 262144,  # 256 KiB default
        excluded_paths: list[str] | None = None,
    ) -> None:
        """Initialize request size middleware.

        Args:
            app: ASGI application
            max_size_bytes: Maximum request body size in bytes
            excluded_paths: List of paths to exclude from size checking
        """
        super().__init__(app)
        self._max_size_bytes = max_size_bytes
        self._excluded_paths = excluded_paths or ["/healthz", "/readyz"]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request with size checking.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response with size checking applied
        """
        # Skip size checking for excluded paths and non-mutating methods
        if request.method in ["GET", "HEAD", "OPTIONS"] or self._is_excluded_path(request.url.path):
            return await call_next(request)

        # Check content length header first (more efficient)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self._max_size_bytes:
                    logger.warning(
                        "Request body too large (content-length header)",
                        extra={
                            "size": size,
                            "max_size": self._max_size_bytes,
                            "path": request.url.path,
                        },
                    )
                    raise PayloadTooLargeError(
                        message="Request body too large",
                        detail=(
                            f"Request body size {size} bytes exceeds "
                            f"maximum allowed size of {self._max_size_bytes} bytes"
                        ),
                    )
            except ValueError:
                # Invalid content-length header, will check actual body
                pass

        # Check actual body size for methods that typically have bodies
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            if len(body) > self._max_size_bytes:
                logger.warning(
                    "Request body too large (actual body)",
                    extra={
                        "size": len(body),
                        "max_size": self._max_size_bytes,
                        "path": request.url.path,
                    },
                )
                raise PayloadTooLargeError(
                    message="Request body too large",
                    detail=(
                        f"Request body size {len(body)} bytes exceeds "
                        f"maximum allowed size of {self._max_size_bytes} bytes"
                    ),
                )

        return await call_next(request)

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from size checking.

        Args:
            path: Request path

        Returns:
            True if excluded, False otherwise
        """
        return any(path.startswith(excluded) for excluded in self._excluded_paths)
