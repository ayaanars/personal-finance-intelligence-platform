from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ledgerx.db.base import Base
from ledgerx.db.primitives import CreatedAtMixin, IdentityMixin


class ImportedTransaction(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "imported_transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "import_id"],
            ["statement_imports.user_id", "statement_imports.id"],
            ondelete="RESTRICT",
            name="fk_imported_transactions_import_owner",
        ),
        UniqueConstraint(
            "user_id", "import_id", "source_row_number", name="uq_imported_transactions_source"
        ),
        CheckConstraint("source_row_number BETWEEN 2 AND 25001", name="source_row"),
        CheckConstraint("amount <> 0 AND amount <> 'NaN'::numeric", name="amount"),
        CheckConstraint("currency IN ('AED','USD','EUR','GBP')", name="currency"),
        CheckConstraint("btrim(description) <> ''", name="description"),
        CheckConstraint("octet_length(fingerprint) = 32", name="fingerprint"),
    )
    user_id: Mapped[UUID]
    import_id: Mapped[UUID]
    source_row_number: Mapped[int]
    transaction_date: Mapped[date]
    description: Mapped[str] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    currency: Mapped[str] = mapped_column(CHAR(3))
    fingerprint: Mapped[bytes] = mapped_column(LargeBinary)
