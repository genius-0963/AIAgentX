"""Agent API endpoints."""

from __future__ import annotations

from app.api.v1.agents.router import router as agents_router

__all__ = ["agents_router"]
