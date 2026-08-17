"""usage tracking for provider calls

Revision ID: 0003_usage_tracking
Revises: 0002_core_schema
Create Date: 2026-08-17 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_usage_tracking"
down_revision: str | Sequence[str] | None = "0002_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add usage tracking columns to run_steps table
    op.add_column(
        "run_steps",
        sa.Column("prompt_tokens", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "run_steps",
        sa.Column("completion_tokens", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "run_steps",
        sa.Column("total_tokens", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "run_steps",
        sa.Column("cost_microunits", sa.BigInteger(), nullable=True, server_default="0"),
    )
    op.add_column(
        "run_steps",
        sa.Column("provider", sa.Text(), nullable=True),
    )
    op.add_column(
        "run_steps",
        sa.Column("model", sa.Text(), nullable=True),
    )

    # Create usage summaries table for aggregated usage data
    op.create_table(
        "usage_summaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("total_prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_microunits", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_usage_summaries_tenant_id", "usage_summaries", ["tenant_id"])
    op.create_index("ix_usage_summaries_run_id", "usage_summaries", ["run_id"])
    op.create_index("ix_usage_summaries_period", "usage_summaries", ["period_start", "period_end"])

    # Enable RLS for usage_summaries table
    op.execute("ALTER TABLE usage_summaries ENABLE ROW LEVEL SECURITY")

    # Add RLS policy for usage_summaries
    op.execute("""
        CREATE POLICY tenant_isolation ON usage_summaries
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    # Drop RLS policy for usage_summaries
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON usage_summaries")

    # Disable RLS for usage_summaries
    op.execute("ALTER TABLE usage_summaries DISABLE ROW LEVEL SECURITY")

    # Drop usage_summaries table
    op.drop_table("usage_summaries")

    # Remove usage tracking columns from run_steps table
    op.drop_column("run_steps", "model")
    op.drop_column("run_steps", "provider")
    op.drop_column("run_steps", "cost_microunits")
    op.drop_column("run_steps", "total_tokens")
    op.drop_column("run_steps", "completion_tokens")
    op.drop_column("run_steps", "prompt_tokens")
