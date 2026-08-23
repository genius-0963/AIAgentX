"""memory system with vector search and tenant isolation

Revision ID: 0005_memory_system
Revises: 0004_budget_enforcement
Create Date: 2026-08-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_memory_system"
down_revision: str | Sequence[str] | None = "0004_budget_enforcement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # Memory Records table
    op.create_table(
        "memory_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("namespace", sa.Text(), nullable=False),
        sa.Column("content_ciphertext", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("allowed_use_label", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "scope IN ('ephemeral', 'session', 'durable')", name="memory_records_scope_check"
        ),
    )

    # Indexes for memory_records
    op.create_index("ix_memory_records_tenant_agent", "memory_records", ["tenant_id", "agent_id"])
    op.create_index("ix_memory_records_namespace", "memory_records", ["namespace"])
    op.create_index(
        "ix_memory_records_expires_at",
        "memory_records",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    # Note: ivfflat index for embedding will be created separately after data insertion
    # op.create_index(
    #     "ix_memory_records_embedding",
    #     "memory_records",
    #     ["embedding"],
    #     postgresql_using="ivfflat",
    #     postgresql_with={"lists": "100"},
    #     postgresql_ops={"embedding": "vector_cosine_ops"},
    # )

    # Session Summaries table
    op.create_table(
        "session_summaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("summary_ciphertext", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "agent_id", "session_id", name="session_summaries_tenant_agent_session_unique"),
    )

    op.create_index("ix_session_summaries_tenant_agent", "session_summaries", ["tenant_id", "agent_id"])
    op.create_index("ix_session_summaries_session_id", "session_summaries", ["session_id"])

    # Memory Retention Policies table
    op.create_table(
        "memory_retention_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("max_records_per_tenant", sa.Integer(), nullable=True),
        sa.Column("max_storage_mb", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "scope", name="retention_policies_tenant_scope_unique"),
        sa.CheckConstraint("retention_days > 0", name="retention_policies_positive_days"),
    )

    op.create_index("ix_retention_policies_tenant_id", "memory_retention_policies", ["tenant_id"])

    # Enable Row Level Security
    op.execute("ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE session_summaries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memory_retention_policies ENABLE ROW LEVEL SECURITY")

    # RLS Policies - Tenants can only see their own data
    op.execute("""
        CREATE POLICY tenant_isolation ON memory_records
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON session_summaries
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON memory_retention_policies
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON memory_records")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON session_summaries")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON memory_retention_policies")

    # Disable RLS
    op.execute("ALTER TABLE memory_records DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE session_summaries DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memory_retention_policies DISABLE ROW LEVEL SECURITY")

    # Drop indexes
    op.drop_index("ix_retention_policies_tenant_id", table_name="memory_retention_policies")
    op.drop_index("ix_session_summaries_session_id", table_name="session_summaries")
    op.drop_index("ix_session_summaries_tenant_agent", table_name="session_summaries")
    op.drop_index("ix_memory_records_expires_at", table_name="memory_records")
    op.drop_index("ix_memory_records_namespace", table_name="memory_records")
    op.drop_index("ix_memory_records_tenant_agent", table_name="memory_records")

    # Drop tables
    op.drop_table("memory_retention_policies")
    op.drop_table("session_summaries")
    op.drop_table("memory_records")

    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS "vector"')
