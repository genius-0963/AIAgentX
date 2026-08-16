"""core schema with multi-tenancy

Revision ID: 0002_core_schema
Revises: 0001_initial
Create Date: 2026-08-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_core_schema"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Tenants table
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("plan", sa.Text(), nullable=False, server_default="free"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'deleted')", name="tenants_status_check"
        ),
        sa.CheckConstraint(
            "plan IN ('free', 'starter', 'professional', 'enterprise')", name="tenants_plan_check"
        ),
    )

    # Users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="users_status_check"),
        sa.UniqueConstraint("tenant_id", "email", name="users_tenant_email_unique"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # API Keys table
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column(
            "scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    # Agents table
    op.create_table(
        "agents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "name", name="agents_tenant_name_unique"),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])

    # Agent Versions table
    op.create_table(
        "agent_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "model_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("memory_mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="agent_versions_status_check"
        ),
        sa.UniqueConstraint("agent_id", "version", name="agent_versions_agent_version_unique"),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])
    op.create_index("ix_agent_versions_tenant_id", "agent_versions", ["tenant_id"])

    # Tool Grants table
    op.create_table(
        "tool_grants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column(
            "policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "agent_version_id", "tool_name", name="tool_grants_version_tool_unique"
        ),
    )
    op.create_index("ix_tool_grants_agent_version_id", "tool_grants", ["agent_version_id"])

    # Runs table
    op.create_table(
        "runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column(
            "input_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.SmallInteger(), nullable=False, server_default="100"),
        sa.Column(
            "max_cost_microunits", sa.BigInteger(), nullable=False, server_default="10000000"
        ),
        sa.Column("spent_cost_microunits", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "state IN ('queued','running','awaiting_approval','retry_scheduled','succeeded','failed','cancelled','timed_out')",
            name="runs_state_check",
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="runs_tenant_idempotency_unique"),
    )
    op.create_index("ix_runs_tenant_id", "runs", ["tenant_id"])
    op.create_index("ix_runs_tenant_id_state", "runs", ["tenant_id", "state"])
    op.create_index("ix_runs_agent_version_id", "runs", ["agent_version_id"])
    op.create_index("ix_runs_state_created", "runs", ["state", "created_at"])

    # Run Steps table
    op.create_table(
        "run_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "sequence", name="run_steps_run_sequence_unique"),
    )
    op.create_index("ix_run_steps_run_id", "run_steps", ["run_id"])

    # Enable Row Level Security
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_grants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE run_steps ENABLE ROW LEVEL SECURITY")

    # RLS Policies - Tenants can only see their own data
    op.execute("""
        CREATE POLICY tenant_isolation ON tenants
        USING (id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON users
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON api_keys
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON agents
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON agent_versions
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON tool_grants
        USING (agent_version_id IN (
            SELECT id FROM agent_versions WHERE tenant_id = current_setting('app.current_tenant_id', true)::uuid
        ))
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON runs
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    op.execute("""
        CREATE POLICY tenant_isolation ON run_steps
        USING (run_id IN (
            SELECT id FROM runs WHERE tenant_id = current_setting('app.current_tenant_id', true)::uuid
        ))
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON api_keys")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON agents")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON agent_versions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tool_grants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON runs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON run_steps")

    # Disable RLS
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agents DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_versions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_grants DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runs DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE run_steps DISABLE ROW LEVEL SECURITY")

    # Drop tables
    op.drop_table("run_steps")
    op.drop_table("runs")
    op.drop_table("tool_grants")
    op.drop_table("agent_versions")
    op.drop_table("agents")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("tenants")

    # Drop UUID extension
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
