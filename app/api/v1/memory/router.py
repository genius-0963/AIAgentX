"""Memory API router."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.memory.dependencies import (
    get_agent_id,
    get_memory_cleanup_service,
    get_memory_retrieval_service,
    get_memory_write_service,
    get_session_memory_service,
    get_tenant_id,
)
from app.api.v1.memory.schemas import (
    CleanupRequest,
    CleanupResponse,
    MemoryListRequest,
    MemoryListResponse,
    MemoryRecordResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryWriteRequest,
    MemoryWriteResponse,
    RetentionPolicyRequest,
    RetentionPolicyResponse,
    SessionAddRequest,
    SessionAddResponse,
    SessionContextResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionEndResponse,
    SessionListResponse,
)

if TYPE_CHECKING:
    from app.application.services.memory_cleanup_service import MemoryCleanupService
    from app.application.services.memory_retrieval_service import MemoryRetrievalService
    from app.application.services.memory_write_service import MemoryWriteService
    from app.application.services.session_memory_service import SessionMemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post(
    "/write",
    response_model=MemoryWriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Write memory",
    description="Write memory through the validation and redaction pipeline",
)
async def write_memory(
    request: MemoryWriteRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    write_service: MemoryWriteService = Depends(get_memory_write_service),
) -> MemoryWriteResponse:
    """Write memory with full validation, redaction, chunking, embedding, and encryption."""
    records = await write_service.write_memory(
        tenant_id=tenant_id,
        agent_id=agent_id,
        content=request.content,
        scope=request.scope,
        namespace=request.namespace,
        metadata=request.metadata,
        session_id=request.session_id,
    )

    return MemoryWriteResponse(
        records=[
            MemoryRecordResponse(
                id=r.id,
                tenant_id=r.tenant_id,
                agent_id=r.agent_id,
                scope=r.scope,
                namespace=r.namespace,
                content=r.content_ciphertext,  # Already decrypted in write service for response
                metadata=r.metadata,
                allowed_use_label=r.allowed_use_label,
                session_id=r.session_id,
                expires_at=r.expires_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ],
        chunk_count=len(records),
        was_redacted=any(
            r.allowed_use_label != r.allowed_use_label.PUBLIC for r in records
        ),
    )


@router.post(
    "/search",
    response_model=MemorySearchResponse,
    summary="Search memory",
    description="Search memory using semantic vector similarity",
)
async def search_memory(
    request: MemorySearchRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    retrieval_service: MemoryRetrievalService = Depends(get_memory_retrieval_service),
) -> MemorySearchResponse:
    """Search memory using semantic similarity with filtering."""
    records = await retrieval_service.retrieve_memory(
        tenant_id=tenant_id,
        agent_id=agent_id,
        query=request.query,
        namespace=request.namespace,
        scope=request.scope,
        limit=request.limit,
        session_id=request.session_id,
        metadata_filters=request.metadata_filters,
        similarity_threshold=request.similarity_threshold,
    )

    return MemorySearchResponse(
        results=[
            MemoryRecordResponse(
                id=r.id,
                tenant_id=r.tenant_id,
                agent_id=r.agent_id,
                scope=r.scope,
                namespace=r.namespace,
                content=r.content_ciphertext,
                metadata=r.metadata,
                allowed_use_label=r.allowed_use_label,
                session_id=r.session_id,
                expires_at=r.expires_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
                similarity=r.metadata.get("_similarity"),
            )
            for r in records
        ],
        query=request.query,
        total_found=len(records),
        limit=request.limit,
    )


@router.get(
    "/{record_id}",
    response_model=MemoryRecordResponse,
    summary="Get memory record",
    description="Get a single memory record by ID",
)
async def get_memory_record(
    record_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    retrieval_service: MemoryRetrievalService = Depends(get_memory_retrieval_service),
) -> MemoryRecordResponse:
    """Get a single memory record by ID."""
    record = await retrieval_service.get_memory_record(tenant_id=tenant_id, record_id=record_id)

    if not record:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory record not found",
        )

    return MemoryRecordResponse(
        id=record.id,
        tenant_id=record.tenant_id,
        agent_id=record.agent_id,
        scope=record.scope,
        namespace=record.namespace,
        content=record.content_ciphertext,
        metadata=record.metadata,
        allowed_use_label=record.allowed_use_label,
        session_id=record.session_id,
        expires_at=record.expires_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "",
    response_model=MemoryListResponse,
    summary="List memory records",
    description="List memory records with pagination",
)
async def list_memory_records(
    request: MemoryListRequest = Depends(),
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    retrieval_service: MemoryRetrievalService = Depends(get_memory_retrieval_service),
) -> MemoryListResponse:
    """List memory records for a tenant and agent."""
    records = await retrieval_service.list_memory_records(
        tenant_id=tenant_id,
        agent_id=agent_id,
        limit=request.limit,
        offset=request.offset,
    )

    # Note: Total count would require a separate query in production
    return MemoryListResponse(
        records=[
            MemoryRecordResponse(
                id=r.id,
                tenant_id=r.tenant_id,
                agent_id=r.agent_id,
                scope=r.scope,
                namespace=r.namespace,
                content=r.content_ciphertext,
                metadata=r.metadata,
                allowed_use_label=r.allowed_use_label,
                session_id=r.session_id,
                expires_at=r.expires_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ],
        limit=request.limit,
        offset=request.offset,
        total=len(records),
    )


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete memory record",
    description="Delete a memory record by ID",
)
async def delete_memory_record(
    record_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    memory_repository = Depends(lambda: None),  # Would need proper dependency
) -> None:
    """Delete a memory record by ID."""
    # Implementation would use repository.delete()
    # For now, return 204
    pass


# Session endpoints
@router.post(
    "/session/start",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start session",
    description="Create a new conversation session",
)
async def start_session(
    request: SessionCreateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    session_service: SessionMemoryService = Depends(get_session_memory_service),
) -> SessionCreateResponse:
    """Start a new session."""
    meta = await session_service.create_session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=request.session_id,
        metadata=request.metadata,
    )

    return SessionCreateResponse(
        session_id=meta["session_id"],
        tenant_id=UUID(meta["tenant_id"]),
        agent_id=UUID(meta["agent_id"]),
        created_at=meta["created_at"],
        message_count=meta["message_count"],
        metadata=meta["metadata"],
    )


@router.post(
    "/session/{session_id}/add",
    response_model=SessionAddResponse,
    summary="Add to session",
    description="Add a message to the session conversation history",
)
async def add_to_session(
    session_id: str,
    request: SessionAddRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    session_service: SessionMemoryService = Depends(get_session_memory_service),
) -> SessionAddResponse:
    """Add a message to the session."""
    meta = await session_service.add_to_session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        role=request.role,
        content=request.content,
        metadata=request.metadata,
    )

    return SessionAddResponse(
        session_id=session_id,
        message_count=meta["message_count"],
        updated_at=meta["updated_at"],
    )


@router.get(
    "/session/{session_id}",
    response_model=SessionContextResponse,
    summary="Get session context",
    description="Get recent conversation context for a session",
)
async def get_session_context(
    session_id: str,
    limit: int = 10,
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    session_service: SessionMemoryService = Depends(get_session_memory_service),
) -> SessionContextResponse:
    """Get session conversation context."""
    messages = await session_service.get_session_context(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        limit=limit,
    )

    return SessionContextResponse(
        session_id=session_id,
        messages=messages,
        message_count=len(messages),
    )


@router.post(
    "/session/{session_id}/end",
    response_model=SessionEndResponse,
    summary="End session",
    description="End a session and persist summary to durable storage",
)
async def end_session(
    session_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    session_service: SessionMemoryService = Depends(get_session_memory_service),
) -> SessionEndResponse:
    """End a session."""
    result = await session_service.end_session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
    )

    return SessionEndResponse(
        session_id=result["session_id"],
        ended_at=result["ended_at"],
        summarized=result["summarized"],
        summary_id=UUID(result["summary_id"]) if result["summary_id"] else None,
        final_message_count=result["final_message_count"],
    )


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List sessions",
    description="List all sessions for an agent",
)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    session_service: SessionMemoryService = Depends(get_session_memory_service),
) -> SessionListResponse:
    """List sessions for an agent."""
    sessions = await session_service.list_sessions(
        tenant_id=tenant_id,
        agent_id=agent_id,
        limit=limit,
        offset=offset,
    )

    return SessionListResponse(
        sessions=sessions,
        limit=limit,
        offset=offset,
        total=len(sessions),
    )


@router.post(
    "/cleanup",
    response_model=CleanupResponse,
    summary="Run memory cleanup",
    description="Run memory cleanup: expired records, retention enforcement, quota checks",
)
async def run_cleanup(
    request: CleanupRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    cleanup_service: MemoryCleanupService = Depends(get_memory_cleanup_service),
) -> CleanupResponse:
    """Run full memory cleanup."""
    result = await cleanup_service.run_full_cleanup(tenant_id=tenant_id)

    return CleanupResponse(
        tenant_id=UUID(result["tenant_id"]),
        expired_cleanup=result["expired_cleanup"],
        retention_enforcement=result["retention_enforcement"],
        quota_status=result["quota_status"],
        total_duration_ms=result["total_duration_ms"],
    )


@router.get(
    "/stats",
    response_model=dict,
    summary="Get memory statistics",
    description="Get memory usage statistics for the tenant",
)
async def get_memory_stats(
    tenant_id: UUID = Depends(get_tenant_id),
    agent_id: UUID = Depends(get_agent_id),
    cleanup_service: MemoryCleanupService = Depends(get_memory_cleanup_service),
) -> dict:
    """Get memory statistics for the tenant."""
    quota_statuses = await cleanup_service.get_quota_status(tenant_id)

    return {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        "scopes": {
            s.scope.value: {
                "record_count": s.record_count,
                "storage_mb": round(s.storage_mb, 2),
                "max_records": s.max_records,
                "max_storage_mb": s.max_storage_mb,
                "is_over_quota": s.is_over_quota,
            }
            for s in quota_statuses
        },
        "total_records": sum(s.record_count for s in quota_statuses),
        "total_storage_mb": round(sum(s.storage_mb for s in quota_statuses), 2),
    }