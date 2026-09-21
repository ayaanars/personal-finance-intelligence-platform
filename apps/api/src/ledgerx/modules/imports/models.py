"""Import aggregate persistence; ownership is enforced with composite foreign keys."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ledgerx.db.base import Base
from ledgerx.db.primitives import CreatedAtMixin, IdentityMixin


class StatementImport(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "statement_imports"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_statement_imports_owner_id"),
        UniqueConstraint("user_id", "upload_key", name="uq_statement_imports_upload_key"),
        UniqueConstraint("user_id", "finalize_key", name="uq_statement_imports_finalize_key"),
        ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            ondelete="RESTRICT",
            name="fk_statement_imports_workspace_owner",
        ),
        CheckConstraint("status IN ('ready', 'invalid', 'completed', 'expired')", name="status"),
        CheckConstraint(
            "total_rows BETWEEN 1 AND 25000 AND valid_rows >= 0 AND invalid_rows >= 0 "
            "AND total_rows = valid_rows + invalid_rows",
            name="counts",
        ),
        CheckConstraint("octet_length(file_sha256) = 32", name="file_hash"),
        CheckConstraint("expires_at > created_at", name="expiry"),
        CheckConstraint(
            "(status = 'completed' AND finalized_at IS NOT NULL AND finalize_key IS NOT NULL "
            "AND invalid_rows = 0 AND finalized_at >= created_at AND finalized_at < expires_at) OR "
            "(status <> 'completed' AND finalized_at IS NULL AND finalize_key IS NULL)",
            name="finalization",
        ),
        CheckConstraint("status <> 'ready' OR invalid_rows = 0", name="ready_valid"),
        CheckConstraint("status <> 'invalid' OR invalid_rows > 0", name="invalid_count"),
        CheckConstraint(
            "(period_start IS NULL AND period_end IS NULL) OR "
            "(period_start IS NOT NULL AND period_end IS NOT NULL AND period_start <= period_end)",
            name="period",
        ),
        Index("ix_statement_imports_expiry", "status", "expires_at"),
    )
    user_id: Mapped[UUID]
    workspace_id: Mapped[UUID]
    upload_key: Mapped[UUID]
    finalize_key: Mapped[UUID | None]
    parser_name: Mapped[str] = mapped_column(String(80))
    parser_version: Mapped[str] = mapped_column(String(40))
    file_sha256: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(16))
    total_rows: Mapped[int]
    valid_rows: Mapped[int]
    invalid_rows: Mapped[int]
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    currencies: Mapped[list[str]] = mapped_column(ARRAY(CHAR(3)))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mapping_spec: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    source_headers: Mapped[list[str] | None] = mapped_column(ARRAY(String(120)))


class MappingProfile(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "import_mapping_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            ondelete="RESTRICT",
            name="fk_import_mapping_profiles_owner",
        ),
        UniqueConstraint("user_id", "workspace_id", "name", name="uq_import_mapping_profiles_name"),
        CheckConstraint("btrim(name) <> ''", name="name"),
    )
    user_id: Mapped[UUID]
    workspace_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(80))
    source_headers: Mapped[list[str]] = mapped_column(ARRAY(String(120)))
    mapping_spec: Mapped[dict[str, object]] = mapped_column(JSONB)


class ImportRow(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "import_id"],
            ["statement_imports.user_id", "statement_imports.id"],
            ondelete="RESTRICT",
            name="fk_import_rows_import_owner",
        ),
        UniqueConstraint("user_id", "import_id", "source_row_number", name="uq_import_rows_source"),
        CheckConstraint("source_row_number BETWEEN 2 AND 25001", name="source_row"),
        CheckConstraint(
            "(cardinality(errors) = 0 AND transaction_date IS NOT NULL AND description IS NOT NULL "
            "AND amount IS NOT NULL AND currency IS NOT NULL AND fingerprint IS NOT NULL) OR "
            "(cardinality(errors) > 0 AND transaction_date IS NULL AND description IS NULL "
            "AND amount IS NULL AND currency IS NULL AND fingerprint IS NULL)",
            name="validation",
        ),
        CheckConstraint("amount <> 0 AND amount <> 'NaN'::numeric", name="amount"),
        CheckConstraint("currency IN ('AED','USD','EUR','GBP')", name="currency"),
        CheckConstraint("btrim(description) <> ''", name="description"),
        CheckConstraint("octet_length(fingerprint) = 32", name="fingerprint"),
    )
    user_id: Mapped[UUID]
    import_id: Mapped[UUID]
    source_row_number: Mapped[int]
    transaction_date: Mapped[date | None]
    description: Mapped[str | None] = mapped_column(String(500))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str | None] = mapped_column(CHAR(3))
    fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    errors: Mapped[list[str]] = mapped_column(ARRAY(String(40)))


class ImportAudit(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "import_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "import_id"],
            ["statement_imports.user_id", "statement_imports.id"],
            ondelete="RESTRICT",
            name="fk_import_audit_import_owner",
        ),
        CheckConstraint("event_code IN ('staged','finalized','expired')", name="event_code"),
        UniqueConstraint("user_id", "import_id", "event_code", name="uq_import_audit_event"),
    )
    user_id: Mapped[UUID]
    import_id: Mapped[UUID]
    event_code: Mapped[str] = mapped_column(String(16))
    correlation_id: Mapped[UUID]
