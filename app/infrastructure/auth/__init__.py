"""Authentication infrastructure."""

from __future__ import annotations

from app.infrastructure.auth.jwt import TokenPayload, create_access_token, decode_token
from app.infrastructure.auth.middleware import AuthMiddleware, get_current_tenant, get_current_user
from app.infrastructure.auth.password import hash_password, verify_password

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "TokenPayload",
    "AuthMiddleware",
    "get_current_tenant",
    "get_current_user",
]
