"""Owner-scoped merchant preferences and identification provenance.

Revision ID: 0006_merchant_preferences
Revises: 0005_understanding
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_merchant_preferences"
down_revision: str | Sequence[str] | None = "0005_understanding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transaction_enrichments", sa.Column("merchant_code", sa.String(80)))
    op.add_column("transaction_enrichments", sa.Column("merchant_source", sa.String(24)))
    op.drop_constraint(op.f("ck_transaction_enrichments_source"), "transaction_enrichments")
    op.create_check_constraint(
        op.f("ck_transaction_enrichments_source"),
        "transaction_enrichments",
        "source IN ('merchant_rule','description_rule','fallback','user_preference')",
    )
    op.create_table(
        "merchant_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_code", sa.String(80), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "workspace_id", "merchant_code"),
        sa.ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            name="fk_merchant_preferences_owner",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "category IN ('Income','Groceries','Food & Dining','Transport','Shopping',"
            "'Entertainment','Housing','Bills & Utilities','Health','Education','Travel',"
            "'Transfers','Cash / ATM','Banking Fees','Other')",
            name="category",
        ),
    )


def downgrade() -> None:
    # Refuse to silently discard learned decisions or their persisted explanations.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM merchant_preferences)
           OR EXISTS (SELECT 1 FROM transaction_enrichments WHERE source = 'user_preference')
        THEN RAISE EXCEPTION 'Remove preferences and reprocess before downgrade'; END IF;
    END $$""")
    op.drop_table("merchant_preferences")
    op.drop_constraint(op.f("ck_transaction_enrichments_source"), "transaction_enrichments")
    op.create_check_constraint(
        op.f("ck_transaction_enrichments_source"),
        "transaction_enrichments",
        "source IN ('merchant_rule','description_rule','fallback')",
    )
    op.drop_column("transaction_enrichments", "merchant_source")
    op.drop_column("transaction_enrichments", "merchant_code")
