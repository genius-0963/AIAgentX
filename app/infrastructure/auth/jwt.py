"""JWT token handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.settings import get_settings


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """JWT token payload."""

    sub: str  # user_id or api_key_id
    tenant_id: str
    scopes: list[str]
    type: str  # "access" or "api_key"
    exp: int
    iat: int


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    now = datetime.now(UTC)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "scopes": scopes or [],
        "type": "access",
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }

    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_api_key_token(
    api_key_id: UUID,
    tenant_id: UUID,
    scopes: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT token for API key authentication."""
    settings = get_settings()
    now = datetime.now(UTC)

    if expires_delta:
        expire = now + expires_delta
    else:
        # API keys use longer expiry by default
        expire = now + timedelta(days=365)

    payload: dict[str, Any] = {
        "sub": str(api_key_id),
        "tenant_id": str(tenant_id),
        "scopes": scopes,
        "type": "api_key",
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }

    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return TokenPayload(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            scopes=payload.get("scopes", []),
            type=payload.get("type", "access"),
            exp=payload["exp"],
            iat=payload["iat"],
        )
    except InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}") from e


def get_token_expiry(token: str) -> datetime | None:
    """Get token expiry without full validation."""
    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        return datetime.fromtimestamp(payload["exp"], tz=UTC)
    except InvalidTokenError:
        return None
