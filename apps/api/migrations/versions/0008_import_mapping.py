"""Explicit CSV mappings and owner/workspace-scoped reusable profiles."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_import_mapping"
down_revision = "0007_monthly_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("statement_imports", sa.Column("mapping_spec", postgresql.JSONB(), nullable=True))
    op.add_column(
        "statement_imports",
        sa.Column("source_headers", postgresql.ARRAY(sa.String(120)), nullable=True),
    )
    op.create_table(
        "import_mapping_profiles",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("source_headers", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.Column("mapping_spec", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            name="fk_import_mapping_profiles_owner",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "user_id", "workspace_id", "name", name="uq_import_mapping_profiles_name"
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="name"),
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM import_mapping_profiles)"))
        .scalar()
    ):
        raise RuntimeError("Export and explicitly remove import mapping profiles before downgrade")
    op.drop_table("import_mapping_profiles")
    op.drop_column("statement_imports", "source_headers")
    op.drop_column("statement_imports", "mapping_spec")
