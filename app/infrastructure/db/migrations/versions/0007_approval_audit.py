"""add approval requests and audit logs tables

Revision ID: 0007_approval_audit
Revises: 0006_outbox_events
Create Date: 2026-08-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_approval_audit"
down_revision: str | Sequence[str] | None = "0006_outbox_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Approval requests table
    approval_state_enum = postgresql.ENUM(
        "pending",
        "approved",
        "denied",
        "expired",
        "cancelled",
        name="approval_state",
        create_type=True,
    )
    approval_state_enum.create(op.get_bind(), checkfirst=True)

    approval_type_enum = postgresql.ENUM(
        "tool_execution",
        "sensitive_action",
        "budget_exceed",
        "policy_violation",
        name="approval_type",
        create_type=True,
    )
    approval_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "approval_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_sequence", sa.Integer(), nullable=False),
        sa.Column("approval_type", approval_type_enum, nullable=False),
        sa.Column("state", approval_state_enum, nullable=False, server_default="pending"),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("policy_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("requested_by", sa.Text(), nullable=False, server_default="system"),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("denial_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("response_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_approval_requests_run_id", "approval_requests", ["run_id"])
    op.create_index("ix_approval_requests_state", "approval_requests", ["state"])
    op.create_index("ix_approval_requests_expires_at", "approval_requests", ["expires_at"])
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["run_id"])  # For tenant isolation via run

    # Enable Row Level Security
    op.execute("ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation ON approval_requests
        USING (run_id IN (SELECT id FROM runs WHERE tenant_id = current_setting('app.current_tenant_id')::uuid))
    """)

    # Audit logs table
    audit_event_type_enum = postgresql.ENUM(
        "tool_executed",
        "tool_denied",
        "approval_requested",
        "approval_granted",
        "approval_denied",
        "rate_limited",
        "policy_violation",
        name="audit_event_type",
        create_type=True,
    )
    audit_event_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "agent_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", audit_event_type_enum, nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column(
            "approval_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_id", sa.Text(), nullable=True),
    )

    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_run_id", "audit_logs", ["run_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_tool_name", "audit_logs", ["tool_name"])
    op.create_index("ix_audit_logs_approval_id", "audit_logs", ["approval_id"])

    # Enable Row Level Security
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation ON audit_logs
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)


def downgrade() -> None:
    # Drop audit logs
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_logs")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_audit_logs_approval_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tool_name", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_run_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")

    op.drop_table("audit_logs")

    # Drop approval requests
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON approval_requests")
    op.execute("ALTER TABLE approval_requests DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_approval_requests_tenant_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_expires_at", table_name="approval_requests")
    op.drop_index("ix_approval_requests_state", table_name="approval_requests")
    op.drop_index("ix_approval_requests_run_id", table_name="approval_requests")

    op.drop_table("approval_requests")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS audit_event_type")
    op.execute("DROP TYPE IF EXISTS approval_type")
    op.execute("DROP TYPE IF EXISTS approval_state")