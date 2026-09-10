from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ledgerx.db.base import Base
from ledgerx.db.primitives import CreatedAtMixin, IdentityMixin
from ledgerx.modules.transactions.understanding import Category

CATEGORY_SQL = ",".join("'" + category.value + "'" for category in Category)


class TransactionEnrichment(Base):
    __tablename__ = "transaction_enrichments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "transaction_id"],
            ["imported_transactions.user_id", "imported_transactions.id"],
            name="fk_transaction_enrichments_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(f"automatic_category IN ({CATEGORY_SQL})", name="automatic_category"),
        CheckConstraint(f"manual_category IN ({CATEGORY_SQL})", name="manual_category"),
        CheckConstraint(
            "source IN ('merchant_rule','description_rule','fallback','user_preference')",
            name="source",
        ),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(
            "(manual_category IS NULL) = (manual_updated_at IS NULL)", name="manual_shape"
        ),
    )
    transaction_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID]
    normalized_description: Mapped[str] = mapped_column(String(1500))
    merchant: Mapped[str | None] = mapped_column(String(100))
    merchant_code: Mapped[str | None] = mapped_column(String(80))
    merchant_source: Mapped[str | None] = mapped_column(String(24))
    automatic_category: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(250))
    rule_id: Mapped[str] = mapped_column(String(80))
    rule_version: Mapped[str] = mapped_column(String(40))
    normalization_version: Mapped[str] = mapped_column(String(40))
    automatic_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    manual_category: Mapped[str | None] = mapped_column(String(40))
    manual_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(server_default=text("1"))


class TransactionAudit(IdentityMixin, CreatedAtMixin, Base):
    __tablename__ = "transaction_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "transaction_id"],
            ["imported_transactions.user_id", "imported_transactions.id"],
            name="fk_transaction_audit_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint("event_code IN ('override','reprocess')", name="event_code"),
    )
    user_id: Mapped[UUID]
    transaction_id: Mapped[UUID]
    event_code: Mapped[str] = mapped_column(String(16))
    correlation_id: Mapped[UUID]


class MerchantPreference(Base):
    __tablename__ = "merchant_preferences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            name="fk_merchant_preferences_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(f"category IN ({CATEGORY_SQL})", name="category"),
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(primary_key=True)
    merchant_code: Mapped[str] = mapped_column(String(80), primary_key=True)
    category: Mapped[str] = mapped_column(String(40))
