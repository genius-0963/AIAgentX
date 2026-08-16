"""Tenant SQLAlchemy model."""

from __future__ import annotations

from sqlalchemy import Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities.tenant import TenantPlan, TenantStatus
from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class TenantModel(Base, UUIDMixin, TimestampMixin):
    """Tenant database model."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan, name="tenant_plan", create_constraint=False),
        nullable=False,
        default=TenantPlan.FREE,
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", create_constraint=False),
        nullable=False,
        default=TenantStatus.ACTIVE,
    )

    users: Mapped[list["UserModel"]] = relationship("UserModel", back_populates="tenant")
    agents: Mapped[list["AgentModel"]] = relationship("AgentModel", back_populates="tenant")
    api_keys: Mapped[list["APIKeyModel"]] = relationship("APIKeyModel", back_populates="tenant")
    runs: Mapped[list["RunModel"]] = relationship("RunModel", back_populates="tenant")
