"""authentication_sessions

Revision ID: 0003_authentication
Revises: 0002_identity_ownership
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_authentication"
down_revision: str | Sequence[str] | None = "0002_identity_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_audit_events",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("event_code", sa.String(length=24), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "event_code IN ('registered', 'login', 'login_failed', 'logout', 'logout_all')",
            name=op.f("ck_auth_audit_events_event_code"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_audit_events_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_audit_events")),
    )
    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "password_hash LIKE '$argon2id$%'", name=op.f("ck_user_credentials_argon2id")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_credentials_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_credentials")),
    )
    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("csrf_secret_hash", sa.LargeBinary(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=40), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoke_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoke_reason IS NOT NULL AND "
            "revoked_at >= created_at AND "
            "revoke_reason IN ('logout', 'logout_all', 'login_rotation'))",
            name=op.f("ck_user_sessions_revocation"),
        ),
        sa.CheckConstraint(
            "created_at <= last_seen_at AND last_seen_at < idle_expires_at "
            "AND idle_expires_at <= absolute_expires_at",
            name=op.f("ck_user_sessions_expiry_order"),
        ),
        sa.CheckConstraint(
            "octet_length(csrf_secret_hash) = 32", name=op.f("ck_user_sessions_csrf_hash_length")
        ),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32", name=op.f("ck_user_sessions_token_hash_length")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index(
        "ix_user_sessions_owner_active",
        "user_sessions",
        ["user_id", "revoked_at", "absolute_expires_at"],
        unique=False,
    )
    op.execute("""
        CREATE FUNCTION ledgerx_auth_audit_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Authentication audit is append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_auth_audit_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON auth_audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION ledgerx_auth_audit_append_only()
    """)


def downgrade() -> None:
    op.drop_index("ix_user_sessions_owner_active", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("user_credentials")
    op.drop_table("auth_audit_events")
    op.execute("DROP FUNCTION ledgerx_auth_audit_append_only()")
