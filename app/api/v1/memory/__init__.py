"""Memory API v1 module."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.memory.router import router as memory_router

router = APIRouter()
router.include_router(memory_router)