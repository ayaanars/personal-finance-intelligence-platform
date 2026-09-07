"""canonical_csv_import

Revision ID: 0004_csv_import
Revises: 0003_authentication
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_csv_import"
down_revision: str | Sequence[str] | None = "0003_authentication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "statement_imports",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("upload_key", sa.Uuid(), nullable=False),
        sa.Column("finalize_key", sa.Uuid(), nullable=True),
        sa.Column("parser_name", sa.String(length=80), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("file_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("currencies", postgresql.ARRAY(sa.CHAR(length=3)), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND finalized_at IS NOT NULL AND finalize_key IS NOT NULL "
            "AND invalid_rows = 0 AND finalized_at >= created_at AND finalized_at < expires_at) OR "
            "(status <> 'completed' AND finalized_at IS NULL AND finalize_key IS NULL)",
            name=op.f("ck_statement_imports_finalization"),
        ),
        sa.CheckConstraint(
            "status <> 'invalid' OR invalid_rows > 0",
            name=op.f("ck_statement_imports_invalid_count"),
        ),
        sa.CheckConstraint(
            "status <> 'ready' OR invalid_rows = 0", name=op.f("ck_statement_imports_ready_valid")
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'invalid', 'completed', 'expired')",
            name=op.f("ck_statement_imports_status"),
        ),
        sa.CheckConstraint(
            "(period_start IS NULL AND period_end IS NULL) OR "
            "(period_start IS NOT NULL AND period_end IS NOT NULL AND period_start <= period_end)",
            name=op.f("ck_statement_imports_period"),
        ),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_statement_imports_expiry")),
        sa.CheckConstraint(
            "octet_length(file_sha256) = 32", name=op.f("ck_statement_imports_file_hash")
        ),
        sa.CheckConstraint(
            "total_rows BETWEEN 1 AND 25000 AND valid_rows >= 0 AND invalid_rows >= 0 "
            "AND total_rows = valid_rows + invalid_rows",
            name=op.f("ck_statement_imports_counts"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            name="fk_statement_imports_workspace_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statement_imports")),
        sa.UniqueConstraint("user_id", "finalize_key", name="uq_statement_imports_finalize_key"),
        sa.UniqueConstraint("user_id", "id", name="uq_statement_imports_owner_id"),
        sa.UniqueConstraint("user_id", "upload_key", name="uq_statement_imports_upload_key"),
    )
    op.create_index(
        "ix_statement_imports_expiry", "statement_imports", ["status", "expires_at"], unique=False
    )
    op.create_table(
        "import_audit_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
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
            "event_code IN ('staged','finalized','expired')",
            name=op.f("ck_import_audit_events_event_code"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "import_id"],
            ["statement_imports.user_id", "statement_imports.id"],
            name="fk_import_audit_import_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_audit_events")),
        sa.UniqueConstraint("user_id", "import_id", "event_code", name="uq_import_audit_event"),
    )
    op.create_table(
        "import_rows",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), nullable=True),
        sa.Column("fingerprint", sa.LargeBinary(), nullable=True),
        sa.Column("errors", postgresql.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount <> 0 AND amount <> 'NaN'::numeric", name=op.f("ck_import_rows_amount")
        ),
        sa.CheckConstraint("btrim(description) <> ''", name=op.f("ck_import_rows_description")),
        sa.CheckConstraint(
            "currency IN ('AED','USD','EUR','GBP')", name=op.f("ck_import_rows_currency")
        ),
        sa.CheckConstraint(
            "(cardinality(errors) = 0 AND transaction_date IS NOT NULL AND description IS NOT NULL "
            "AND amount IS NOT NULL AND currency IS NOT NULL AND fingerprint IS NOT NULL) OR "
            "(cardinality(errors) > 0 AND transaction_date IS NULL AND description IS NULL "
            "AND amount IS NULL AND currency IS NULL AND fingerprint IS NULL)",
            name=op.f("ck_import_rows_validation"),
        ),
        sa.CheckConstraint(
            "octet_length(fingerprint) = 32", name=op.f("ck_import_rows_fingerprint")
        ),
        sa.CheckConstraint(
            "source_row_number BETWEEN 2 AND 25001", name=op.f("ck_import_rows_source_row")
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "import_id"],
            ["statement_imports.user_id", "statement_imports.id"],
            name="fk_import_rows_import_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_rows")),
        sa.UniqueConstraint(
            "user_id", "import_id", "source_row_number", name="uq_import_rows_source"
        ),
    )
    op.create_table(
        "imported_transactions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount <> 0 AND amount <> 'NaN'::numeric", name=op.f("ck_imported_transactions_amount")
        ),
        sa.CheckConstraint(
            "btrim(description) <> ''", name=op.f("ck_imported_transactions_description")
        ),
        sa.CheckConstraint(
            "currency IN ('AED','USD','EUR','GBP')", name=op.f("ck_imported_transactions_currency")
        ),
        sa.CheckConstraint(
            "octet_length(fingerprint) = 32", name=op.f("ck_imported_transactions_fingerprint")
        ),
        sa.CheckConstraint(
            "source_row_number BETWEEN 2 AND 25001",
            name=op.f("ck_imported_transactions_source_row"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "import_id"],
            ["statement_imports.user_id", "statement_imports.id"],
            name="fk_imported_transactions_import_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_imported_transactions")),
        sa.UniqueConstraint(
            "user_id", "import_id", "source_row_number", name="uq_imported_transactions_source"
        ),
    )
    # Facts and fixed-shape audit cannot be rewritten through the runtime connection.
    op.execute("""
        CREATE FUNCTION ledgerx_import_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Imported facts and audit are append-only';
        END;
        $$
    """)
    for table in ("imported_transactions", "import_audit_events"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE OR TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION ledgerx_import_append_only()
        """)
    op.execute("""
        CREATE FUNCTION ledgerx_import_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status IN ('completed', 'expired') OR
               (NEW.status <> OLD.status AND NOT (
                   (OLD.status = 'ready' AND NEW.status IN ('completed', 'expired')) OR
                   (OLD.status = 'invalid' AND NEW.status = 'expired'))) THEN
                RAISE EXCEPTION 'Invalid import state transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_import_transition BEFORE UPDATE ON statement_imports
        FOR EACH ROW EXECUTE FUNCTION ledgerx_import_transition()
    """)
    # A batch-level deferred check counts once, rather than once per imported row.
    op.execute("""
        CREATE FUNCTION ledgerx_import_complete_count() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE batch statement_imports%ROWTYPE; actual bigint;
        BEGIN
            SELECT * INTO batch FROM statement_imports WHERE id = NEW.id;
            IF batch.status = 'completed' THEN
                SELECT count(*) INTO actual FROM imported_transactions
                    WHERE user_id = batch.user_id AND import_id = batch.id;
                IF actual <> batch.total_rows OR batch.invalid_rows <> 0 THEN
                    RAISE EXCEPTION 'Incomplete import finalization';
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_import_complete_count
        AFTER INSERT OR UPDATE ON statement_imports DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION ledgerx_import_complete_count()
    """)
    # Facts can only be inserted during ready -> completed, with the batch locked.
    op.execute("""
        CREATE FUNCTION ledgerx_import_fact_ready() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE batch statement_imports%ROWTYPE;
        BEGIN
            SELECT * INTO batch FROM statement_imports
                WHERE id = NEW.import_id AND user_id = NEW.user_id FOR UPDATE;
            IF NOT FOUND OR batch.status <> 'ready' OR batch.invalid_rows <> 0 OR
               batch.expires_at <= clock_timestamp() THEN
                RAISE EXCEPTION 'Import is not ready';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_import_fact_ready BEFORE INSERT ON imported_transactions
        FOR EACH ROW EXECUTE FUNCTION ledgerx_import_fact_ready()
    """)
    op.execute("""
        CREATE FUNCTION ledgerx_import_fact_completed() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM statement_imports
                WHERE id = NEW.import_id AND user_id = NEW.user_id AND status = 'completed') THEN
                RAISE EXCEPTION 'Import was not finalized';
            END IF;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_import_fact_completed AFTER INSERT ON imported_transactions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION ledgerx_import_fact_completed()
    """)


def downgrade() -> None:
    # Destructive to import data: downgrade only disposable DBs; otherwise roll forward.
    op.drop_table("imported_transactions")
    op.drop_table("import_rows")
    op.drop_table("import_audit_events")
    op.drop_index("ix_statement_imports_expiry", table_name="statement_imports")
    op.drop_table("statement_imports")
    op.execute("DROP FUNCTION ledgerx_import_fact_completed()")
    op.execute("DROP FUNCTION ledgerx_import_fact_ready()")
    op.execute("DROP FUNCTION ledgerx_import_complete_count()")
    op.execute("DROP FUNCTION ledgerx_import_transition()")
    op.execute("DROP FUNCTION ledgerx_import_append_only()")
