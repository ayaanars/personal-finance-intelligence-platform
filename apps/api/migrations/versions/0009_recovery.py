"""One-time recovery and database-backed auth budgets."""

import sqlalchemy as sa
from alembic import op

revision = "0009_recovery"
down_revision = "0008_import_mapping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("token_hash", sa.LargeBinary(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="token_hash_length"),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
    op.create_table(
        "auth_rate_limits",
        sa.Column("scope", sa.String(32), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempts > 0", name="positive_attempts"),
    )


def downgrade() -> None:
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_table("password_resets")
