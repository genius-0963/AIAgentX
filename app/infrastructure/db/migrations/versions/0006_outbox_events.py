"""add outbox events table

Revision ID: 0006_outbox_events
Revises: 0005_memory_system
Create Date: 2026-08-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_outbox_events"
down_revision: str | Sequence[str] | None = "0005_memory_system"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_aggregate_type_id", "outbox_events", ["aggregate_type", "aggregate_id"])
    op.create_index(
        "ix_outbox_events_unprocessed",
        "outbox_events",
        ["processed_at"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )

    # Enable Row Level Security
    op.execute("ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation ON outbox_events
        USING (true)  -- Outbox events are system-level, not tenant-scoped
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON outbox_events")
    op.execute("ALTER TABLE outbox_events DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_outbox_events_unprocessed", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_type_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")

    op.drop_table("outbox_events")