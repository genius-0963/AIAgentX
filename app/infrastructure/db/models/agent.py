"""Agent SQLAlchemy models."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities.agent import AgentStatus
from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class AgentModel(Base, UUIDMixin, TimestampMixin):
    """Agent database model."""

    __tablename__ = "agents"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    versions: Mapped[list["AgentVersionModel"]] = relationship(
        "AgentVersionModel", back_populates="agent", cascade="all, delete-orphan"
    )

    tenant: Mapped["TenantModel"] = relationship("TenantModel", back_populates="agents")


class AgentVersionModel(Base, UUIDMixin, TimestampMixin):
    """Agent Version database model."""

    __tablename__ = "agent_versions"

    agent_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text(), nullable=False)
    model_policy: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False, default={})
    memory_mode: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, name="agent_version_status", create_constraint=False),
        nullable=False,
        default=AgentStatus.DRAFT,
    )

    agent: Mapped["AgentModel"] = relationship("AgentModel", back_populates="versions")
    tool_grants: Mapped[list["ToolGrantModel"]] = relationship(
        "ToolGrantModel", back_populates="agent_version", cascade="all, delete-orphan"
    )


class ToolGrantModel(Base, UUIDMixin, TimestampMixin):
    """Tool Grant database model."""

    __tablename__ = "tool_grants"

    agent_version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(Text(), nullable=False)
    policy: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False, default={})
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)

    agent_version: Mapped["AgentVersionModel"] = relationship(
        "AgentVersionModel", back_populates="tool_grants"
    )

    __table_args__ = (
        sa.UniqueConstraint("agent_version_id", "tool_name", name="uq_tool_grant_version_tool"),
    )
