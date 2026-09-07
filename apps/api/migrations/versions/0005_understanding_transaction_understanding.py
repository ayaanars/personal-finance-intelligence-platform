"""transaction_understanding

Revision ID: 0005_understanding
Revises: 0004_csv_import
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_understanding"
down_revision: str | Sequence[str] | None = "0004_csv_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_imported_transactions_owner_id", "imported_transactions", ["user_id", "id"]
    )
    op.create_table(
        "transaction_audit_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("event_code", sa.String(length=16), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_code IN ('override','reprocess')",
            name=op.f("ck_transaction_audit_events_event_code"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "transaction_id"],
            ["imported_transactions.user_id", "imported_transactions.id"],
            name="fk_transaction_audit_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_audit_events")),
    )
    op.create_table(
        "transaction_enrichments",
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("normalized_description", sa.String(length=1500), nullable=False),
        sa.Column("merchant", sa.String(length=100), nullable=True),
        sa.Column("automatic_category", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=250), nullable=False),
        sa.Column("rule_id", sa.String(length=80), nullable=False),
        sa.Column("rule_version", sa.String(length=40), nullable=False),
        sa.Column("normalization_version", sa.String(length=40), nullable=False),
        sa.Column("automatic_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("manual_category", sa.String(length=40), nullable=True),
        sa.Column("manual_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "automatic_category IN ('Income','Groceries','Food & Dining','Transport',"
            "'Shopping','Entertainment','Housing','Bills & Utilities','Health','Education',"
            "'Travel','Transfers','Cash / ATM','Banking Fees','Other')",
            name=op.f("ck_transaction_enrichments_automatic_category"),
        ),
        sa.CheckConstraint(
            "manual_category IN ('Income','Groceries','Food & Dining','Transport',"
            "'Shopping','Entertainment','Housing','Bills & Utilities','Health','Education',"
            "'Travel','Transfers','Cash / ATM','Banking Fees','Other')",
            name=op.f("ck_transaction_enrichments_manual_category"),
        ),
        sa.CheckConstraint(
            "source IN ('merchant_rule','description_rule','fallback')",
            name=op.f("ck_transaction_enrichments_source"),
        ),
        sa.CheckConstraint(
            "(manual_category IS NULL) = (manual_updated_at IS NULL)",
            name=op.f("ck_transaction_enrichments_manual_shape"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_transaction_enrichments_version")),
        sa.ForeignKeyConstraint(
            ["user_id", "transaction_id"],
            ["imported_transactions.user_id", "imported_transactions.id"],
            name="fk_transaction_enrichments_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("transaction_id", name=op.f("pk_transaction_enrichments")),
    )
    op.execute("""
        CREATE TRIGGER transaction_audit_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON transaction_audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION ledgerx_import_append_only()
    """)


def downgrade() -> None:
    # Destructive only to enrichment/correction metadata; imported facts remain untouched.
    op.drop_table("transaction_enrichments")
    op.drop_table("transaction_audit_events")
    op.drop_constraint("uq_imported_transactions_owner_id", "imported_transactions", type_="unique")
