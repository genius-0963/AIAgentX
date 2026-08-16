"""Run SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.value_objects.state import RunState, RunStepKind
from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class RunModel(Base, UUIDMixin, TimestampMixin):
    """Run database model."""

    __tablename__ = "runs"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    state: Mapped[RunState] = mapped_column(
        Enum(RunState, name="run_state", create_constraint=False),
        nullable=False,
        default=RunState.QUEUED,
    )
    input_data: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False, default={})
    output_data: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text(), nullable=False)
    attempt: Mapped[int] = mapped_column(nullable=False, default=0)
    max_steps: Mapped[int] = mapped_column(nullable=False, default=100)
    max_cost_microunits: Mapped[int] = mapped_column(nullable=False, default=10_000_000)
    spent_cost_microunits: Mapped[int] = mapped_column(nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(Text(), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    steps: Mapped[list["RunStepModel"]] = relationship(
        "RunStepModel", back_populates="run", cascade="all, delete-orphan", order_by="RunStepModel.sequence"
    )

    tenant: Mapped["TenantModel"] = relationship("TenantModel", back_populates="runs")


class RunStepModel(Base, UUIDMixin, TimestampMixin):
    """Run Step database model."""

    __tablename__ = "run_steps"

    run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(nullable=False)
    kind: Mapped[RunStepKind] = mapped_column(
        Enum(RunStepKind, name="run_step_kind", create_constraint=False),
        nullable=False,
    )
    state: Mapped[RunState] = mapped_column(
        Enum(RunState, name="run_step_state", create_constraint=False),
        nullable=False,
        default=RunState.QUEUED,
    )
    input_data: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    output_data: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="steps")
