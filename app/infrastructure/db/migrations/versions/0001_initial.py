"""initial schema placeholder

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-16 00:00:00.000000

Sprint 1 only establishes the Alembic framework. The full schema
(tenants, agents, runs, etc.) is added in Sprint 2.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT 1")  # placeholder no-op; Sprint 2 adds real schema


def downgrade() -> None:
    op.execute("SELECT 1")  # placeholder no-op
