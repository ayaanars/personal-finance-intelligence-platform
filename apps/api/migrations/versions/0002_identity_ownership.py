"""Initial principal and workspace ownership foundation."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_identity_ownership"
down_revision: str | None = "0001_foundation"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email_normalized", sa.String(320), nullable=False),
        sa.Column("email_display", sa.String(320), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        sa.CheckConstraint(
            "email_normalized <> '' AND email_normalized = lower(btrim(email_normalized))",
            name=op.f("ck_users_email_normalized_canonical"),
        ),
        sa.CheckConstraint(
            "btrim(email_display) <> ''", name=op.f("ck_users_email_display_nonblank")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'locked', 'deletion_pending', 'deleted')",
            name=op.f("ck_users_status"),
        ),
    )
    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_workspaces_owner_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("owner_user_id", name="uq_workspaces_owner_user_id"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_workspaces_owner_user_id_id"),
        sa.CheckConstraint(
            "btrim(display_name) <> ''", name=op.f("ck_workspaces_display_name_nonblank")
        ),
    )
    op.execute("""
        CREATE FUNCTION ledgerx_touch_user_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := statement_timestamp();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION ledgerx_touch_user_updated_at()
    """)


def downgrade() -> None:
    op.drop_table("workspaces")
    op.drop_table("users")
    op.execute("DROP FUNCTION ledgerx_touch_user_updated_at()")
