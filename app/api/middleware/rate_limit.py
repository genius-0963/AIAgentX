"""Rate limiting middleware for API endpoints."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.errors.exceptions import RateLimitExceededError
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits on API requests."""

    def __init__(
        self,
        app,
        rate_limit_service,
        excluded_paths: list[str] | None = None,
    ) -> None:
        """Initialize rate limit middleware.

        Args:
            app: ASGI application
            rate_limit_service: Rate limit service instance
            excluded_paths: List of paths to exclude from rate limiting
        """
        super().__init__(app)
        self._rate_limit_service = rate_limit_service
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
        """Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response with rate limiting applied
        """
        # Skip rate limiting for excluded paths
        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        # Get tenant ID from request state (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            logger.warning("No tenant_id in request state for rate limiting")
            return await call_next(request)

        # Get tenant plan from request state
        plan = getattr(request.state, "tenant_plan", "free")

        # Check rate limit
        result = await self._rate_limit_service.check_rate_limit(
            tenant_id=tenant_id,
            endpoint=request.url.path,
            plan=plan,
        )

        # Add rate limit headers to response
        response = await call_next(request)
        rate_limit_headers = await self._rate_limit_service.get_rate_limit_headers(
            tenant_id=tenant_id,
            endpoint=request.url.path,
            plan=plan,
        )

        for header_name, header_value in rate_limit_headers.items():
            response.headers[header_name] = header_value

        # Check if rate limit exceeded
        if not result.allowed:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "tenant_id": str(tenant_id),
                    "endpoint": request.url.path,
                    "plan": plan,
                },
            )
            raise RateLimitExceededError(
                message="Rate limit exceeded",
                detail=f"Rate limit of {result.limit} requests per minute exceeded",
                retry_after=result.reset_at,
            )

        # Record the request
        await self._rate_limit_service.record_request(tenant_id, request.url.path)

        return response

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from rate limiting.

        Args:
            path: Request path

        Returns:
            True if excluded, False otherwise
        """
        return any(path.startswith(excluded) for excluded in self._excluded_paths)
