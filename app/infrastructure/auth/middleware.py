"""Authentication middleware and dependencies."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.api_key import APIKey
from app.domain.entities.user import User
from app.infrastructure.auth.jwt import decode_token
from app.infrastructure.db.session import get_session

security = HTTPBearer(auto_error=False)


class AuthContext:
    """Authentication context for the current request."""

    def __init__(
        self,
        user: User | None = None,
        api_key: APIKey | None = None,
        tenant_id: UUID | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        self.user = user
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.scopes = scopes or []

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None or self.api_key is not None

    @property
    def is_user(self) -> bool:
        return self.user is not None

    @property
    def is_api_key(self) -> bool:
        return self.api_key is not None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def require_scope(self, scope: str) -> None:
        if not self.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope: {scope}",
            )


async def get_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    """Extract authentication context from request."""
    # Try to get tenant from header (for RLS)
    tenant_id_header = request.headers.get("X-Tenant-ID")
    if tenant_id_header:
        try:
            tenant_id = UUID(tenant_id_header)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant ID format",
            )
    else:
        tenant_id = None

    if not credentials:
        return AuthContext(tenant_id=tenant_id)

    try:
        payload = decode_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate tenant context
    token_tenant_id = UUID(payload.tenant_id)
    if tenant_id and tenant_id != token_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant ID mismatch",
        )

    if payload.type == "access":
        # User authentication
        from app.infrastructure.db.repositories.user import SQLUserRepository

        user_repo = SQLUserRepository(session)
        user = await user_repo.get(UUID(payload.sub))
        if not user or not user.is_active():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        return AuthContext(
            user=user,
            tenant_id=token_tenant_id,
            scopes=payload.scopes,
        )

    if payload.type == "api_key":
        # API key authentication
        from app.infrastructure.db.repositories.api_key import SQLAPIKeyRepository

        api_key_repo = SQLAPIKeyRepository(session)
        api_key = await api_key_repo.get(UUID(payload.sub))
        if not api_key or not api_key.is_valid():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key not found or invalid",
            )
        return AuthContext(
            api_key=api_key,
            tenant_id=token_tenant_id,
            scopes=payload.scopes,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token type",
    )


async def get_current_user(
    auth: AuthContext = Depends(get_auth_context),
) -> User:
    """Get current authenticated user."""
    if not auth.is_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required",
        )
    return auth.user


async def get_current_tenant(
    auth: AuthContext = Depends(get_auth_context),
) -> UUID:
    """Get current tenant ID."""
    if not auth.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    return auth.tenant_id


async def get_optional_tenant(
    auth: AuthContext = Depends(get_auth_context),
) -> UUID | None:
    """Get current tenant ID if available."""
    return auth.tenant_id


def require_scopes(*scopes: str):
    """Dependency factory to require specific scopes."""

    async def _check_scopes(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        for scope in scopes:
            auth.require_scope(scope)
        return auth

    return _check_scopes


class AuthMiddleware:
    """Middleware to set tenant context for RLS."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # This middleware would need to be integrated with the request lifecycle
        # to set the app.current_tenant_id PostgreSQL session variable
        # For now, we'll handle this in the repository layer
        await self.app(scope, receive, send)
