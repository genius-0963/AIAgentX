"""budget enforcement features

Revision ID: 0004_budget_enforcement
Revises: 0002_core_schema
Create Date: 2026-08-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_budget_enforcement"
down_revision: str | Sequence[str] | None = "0002_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add timeout and retry budget to runs
    op.add_column("runs", sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="90"))
    op.add_column("runs", sa.Column("retry_budget", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("runs", sa.Column("idempotency_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Add budget limits to tenants
    op.add_column(
        "tenants",
        sa.Column("monthly_budget_usd", postgresql.NUMERIC(precision=10, scale=2), nullable=False, server_default="100.0"),
    )
    op.add_column(
        "tenants",
        sa.Column("daily_budget_usd", postgresql.NUMERIC(precision=10, scale=2), nullable=False, server_default="10.0"),
    )
    op.add_column(
        "tenants",
        sa.Column("spent_monthly_usd", postgresql.NUMERIC(precision=10, scale=2), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "tenants",
        sa.Column("spent_daily_usd", postgresql.NUMERIC(precision=10, scale=2), nullable=False, server_default="0.0"),
    )
    op.add_column("tenants", sa.Column("budget_reset_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("rate_limit_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Add performance indexes
    op.create_index(
        "ix_runs_cancel_requested", "runs", ["cancel_requested_at"], unique=False, postgresql_where=sa.text("cancel_requested_at IS NOT NULL")
    )
    op.create_index(
        "ix_runs_lease_expires", "runs", ["lease_expires_at"], unique=False, postgresql_where=sa.text("lease_expires_at IS NOT NULL")
    )
    op.create_index("ix_tenant_budget_reset", "tenants", ["budget_reset_at"], unique=False)


def downgrade() -> None:
    # Drop performance indexes
    op.drop_index("ix_tenant_budget_reset", table_name="tenants")
    op.drop_index("ix_runs_lease_expires", table_name="runs")
    op.drop_index("ix_runs_cancel_requested", table_name="runs")

    # Drop timeout and retry budget from runs
    op.drop_column("runs", "retry_budget")
    op.drop_column("runs", "timeout_seconds")
    op.drop_column("runs", "idempotency_response")

    # Drop budget columns from tenants
    op.drop_column("tenants", "rate_limit_config")
    op.drop_column("tenants", "budget_reset_at")
    op.drop_column("tenants", "spent_daily_usd")
    op.drop_column("tenants", "spent_monthly_usd")
    op.drop_column("tenants", "daily_budget_usd")
    op.drop_column("tenants", "monthly_budget_usd")
