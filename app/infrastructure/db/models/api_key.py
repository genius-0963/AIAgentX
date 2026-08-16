"""API Key SQLAlchemy model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class APIKeyModel(Base, UUIDMixin, TimestampMixin):
    """API Key database model."""

    __tablename__ = "api_keys"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    scopes: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False, default={})
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["TenantModel"] = relationship("TenantModel", back_populates="api_keys")
