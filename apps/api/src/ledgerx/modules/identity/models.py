"""Persistence mappings for principals and their private workspace."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ledgerx.db.base import Base
from ledgerx.db.primitives import CreatedAtMixin, IdentityMixin


class User(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        CheckConstraint(
            "email_normalized <> '' AND email_normalized = lower(btrim(email_normalized))",
            name="email_normalized_canonical",
        ),
        CheckConstraint("btrim(email_display) <> ''", name="email_display_nonblank"),
        CheckConstraint(
            "status IN ('active', 'locked', 'deletion_pending', 'deleted')", name="status"
        ),
    )

    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    email_display: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("statement_timestamp()"),
        server_onupdate=FetchedValue(),
    )


class Workspace(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_workspaces_owner_user_id"),
        UniqueConstraint("owner_user_id", "id", name="uq_workspaces_owner_user_id_id"),
        CheckConstraint("btrim(display_name) <> ''", name="display_name_nonblank"),
    )

    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
