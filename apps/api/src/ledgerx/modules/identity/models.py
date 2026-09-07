"""Persistence mappings for principals and their private workspace."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
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


class Credential(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (CheckConstraint("password_hash LIKE '$argon2id$%'", name="argon2id"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )


class UserSession(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        CheckConstraint("octet_length(token_hash) = 32", name="token_hash_length"),
        CheckConstraint("octet_length(csrf_secret_hash) = 32", name="csrf_hash_length"),
        CheckConstraint(
            "created_at <= last_seen_at AND last_seen_at < idle_expires_at "
            "AND idle_expires_at <= absolute_expires_at",
            name="expiry_order",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoke_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoke_reason IS NOT NULL "
            "AND revoked_at >= created_at AND "
            "revoke_reason IN ('logout', 'logout_all', 'login_rotation'))",
            name="revocation",
        ),
        Index("ix_user_sessions_owner_active", "user_id", "revoked_at", "absolute_expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    csrf_secret_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(40))


class AuthAudit(IdentityMixin, Base):
    """Fixed-shape authentication audit; never accepts arbitrary payload metadata."""

    __tablename__ = "auth_audit_events"
    __table_args__ = (
        CheckConstraint(
            "event_code IN ('registered', 'login', 'login_failed', 'logout', 'logout_all')",
            name="event_code",
        ),
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_code: Mapped[str] = mapped_column(String(24), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )
