"""Currency-specific owner/workspace monthly goals."""

import sqlalchemy as sa
from alembic import op

revision = "0007_monthly_goals"
down_revision = "0006_merchant_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_goals",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("target", sa.Numeric(20, 4), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "workspace_id", "month", "currency", "kind"),
        sa.ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            name="fk_monthly_goals_owner",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("kind IN ('spending','net_cash_flow')", name="kind"),
        sa.CheckConstraint("currency IN ('AED','USD','EUR','GBP')", name="currency"),
        sa.CheckConstraint("target > 0", name="target"),
        sa.CheckConstraint("EXTRACT(DAY FROM month) = 1", name="month"),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM monthly_goals)")).scalar():
        raise RuntimeError("Export and explicitly remove monthly goals before downgrade")
    op.drop_table("monthly_goals")
