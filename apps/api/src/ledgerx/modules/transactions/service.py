"""Owner-scoped enrichment use cases inside authenticated transactions."""

import base64
import binascii
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, insert, select
from sqlalchemy.orm import Session

from ledgerx.modules.identity.service import Principal
from ledgerx.modules.imports.models import StatementImport
from ledgerx.modules.transactions.enrichment_models import (
    MerchantPreference,
    TransactionAudit,
    TransactionEnrichment,
)
from ledgerx.modules.transactions.errors import TransactionFailure
from ledgerx.modules.transactions.models import ImportedTransaction
from ledgerx.modules.transactions.schemas import Page, TransactionPage, TransactionView
from ledgerx.modules.transactions.understanding import (
    NORMALIZATION_VERSION,
    RULE_VERSION,
    Category,
    merchant_match,
    understand,
)


def preferences_for(db: Session, principal: Principal) -> dict[str, Category]:
    return {
        row.merchant_code: Category(row.category)
        for row in db.scalars(
            select(MerchantPreference).where(
                MerchantPreference.user_id == principal.user.id,
                MerchantPreference.workspace_id == principal.workspace.id,
            )
        )
    }


def automatic_values(
    fact: ImportedTransaction,
    preferences: dict[str, Category] | None = None,
) -> dict[str, str | None]:
    result = understand(fact.description, fact.amount, preferences)
    merchant = merchant_match(result.normalized_description)
    return dict(
        normalized_description=result.normalized_description,
        merchant=result.merchant,
        merchant_code=merchant.code if merchant else None,
        merchant_source=(
            "catalog_alias"
            if merchant
            else "description_label"
            if result.merchant
            else "unidentified"
        ),
        automatic_category=result.category.value,
        source=result.source,
        reason=result.reason,
        rule_id=result.rule_id,
        rule_version=RULE_VERSION,
        normalization_version=NORMALIZATION_VERSION,
    )


def enrich_import(db: Session, principal: Principal, import_id: UUID) -> None:
    """Insert enrichment before finalization commits; any failure rolls back the whole import."""
    facts = db.scalars(
        select(ImportedTransaction).where(
            ImportedTransaction.user_id == principal.user.id,
            ImportedTransaction.import_id == import_id,
        )
    ).all()
    now = datetime.now(UTC)
    preferences = preferences_for(db, principal)
    for start in range(0, len(facts), 500):
        db.execute(
            insert(TransactionEnrichment),
            [
                dict(
                    transaction_id=fact.id,
                    user_id=principal.user.id,
                    automatic_updated_at=now,
                    **automatic_values(fact, preferences),
                )
                for fact in facts[start : start + 500]
            ],
        )


def owned_query(principal: Principal) -> Select[tuple[ImportedTransaction]]:
    return (
        select(ImportedTransaction)
        .join(
            StatementImport,
            (StatementImport.id == ImportedTransaction.import_id)
            & (StatementImport.user_id == ImportedTransaction.user_id),
        )
        .where(
            ImportedTransaction.user_id == principal.user.id,
            StatementImport.workspace_id == principal.workspace.id,
            StatementImport.status == "completed",
        )
    )


def owned_fact(db: Session, principal: Principal, identifier: UUID) -> ImportedTransaction:
    fact = db.scalar(owned_query(principal).where(ImportedTransaction.id == identifier))
    if fact is None:
        raise TransactionFailure(404, "TRANSACTION_NOT_FOUND", "Transaction was not found")
    return fact


def enrichment(db: Session, principal: Principal, identifier: UUID) -> TransactionEnrichment | None:
    return db.scalar(
        select(TransactionEnrichment).where(
            TransactionEnrichment.user_id == principal.user.id,
            TransactionEnrichment.transaction_id == identifier,
        )
    )


def view(
    fact: ImportedTransaction,
    metadata: TransactionEnrichment | None,
    preferences: dict[str, Category] | None = None,
) -> TransactionView:
    # Legacy facts remain visible immediately after additive migration; GET performs no writes.
    auto = (
        automatic_values(fact, preferences)
        if metadata is None
        else {key: getattr(metadata, key) for key in automatic_values_keys}
    )
    manual = metadata.manual_category if metadata else None
    return TransactionView(
        id=fact.id,
        transaction_date=fact.transaction_date,
        amount=format(fact.amount, ".4f"),
        currency=fact.currency,
        raw_description=fact.description,
        normalized_description=str(auto["normalized_description"]),
        merchant=auto["merchant"],
        merchant_code=auto["merchant_code"],
        merchant_source=auto["merchant_source"],
        category=Category(str(manual or auto["automatic_category"])),
        categorization_source="manual" if manual else str(auto["source"]),
        categorization_reason="User selected this category." if manual else str(auto["reason"]),
        automatic_category=Category(str(auto["automatic_category"])),
        automatic_source=str(auto["source"]),
        automatic_reason=str(auto["reason"]),
        rule_id=str(auto["rule_id"]),
        rule_version=str(auto["rule_version"]),
        normalization_version=str(auto["normalization_version"]),
        version=metadata.version if metadata else 0,
        enrichment_persisted=metadata is not None,
    )


automatic_values_keys = (
    "normalized_description",
    "merchant",
    "merchant_code",
    "merchant_source",
    "automatic_category",
    "source",
    "reason",
    "rule_id",
    "rule_version",
    "normalization_version",
)


def list_transactions(
    db: Session, principal: Principal, limit: int, cursor: str | None
) -> TransactionPage:
    query = owned_query(principal)
    if cursor is not None:
        try:
            decoded = base64.b64decode(cursor, altchars=b"-_", validate=True).decode("ascii")
            owner, identifier = decoded.split(":")
            if UUID(owner) != principal.user.id:
                raise ValueError
            boundary = UUID(identifier)
        except (ValueError, UnicodeError, binascii.Error):
            raise TransactionFailure(422, "CURSOR_INVALID", "Cursor is invalid") from None
        query = query.where(ImportedTransaction.id > boundary)
    facts = db.scalars(query.order_by(ImportedTransaction.id).limit(limit + 1)).all()
    selected = facts[:limit]
    metadata = {
        row.transaction_id: row
        for row in db.scalars(
            select(TransactionEnrichment).where(
                TransactionEnrichment.user_id == principal.user.id,
                TransactionEnrichment.transaction_id.in_([fact.id for fact in selected]),
            )
        )
    }
    more = len(facts) > limit
    next_cursor = (
        base64.urlsafe_b64encode(f"{principal.user.id}:{selected[-1].id}".encode("ascii")).decode(
            "ascii"
        )
        if more
        else None
    )
    preferences = preferences_for(db, principal)
    return TransactionPage(
        items=[view(fact, metadata.get(fact.id), preferences) for fact in selected],
        page=Page(next_cursor=next_cursor, has_more=more),
    )


def update(
    db: Session,
    principal: Principal,
    identifier: UUID,
    correlation_id: UUID,
    *,
    manual: bool,
    category: Category | None = None,
    expected_version: int | None = None,
    preference_action: str = "keep",
) -> TransactionView:
    # Authentication holds the owner lock, serializing all supported mutations for this user.
    fact = owned_fact(db, principal, identifier)
    metadata = enrichment(db, principal, identifier)
    version = metadata.version if metadata else 0
    if manual and expected_version != version:
        raise TransactionFailure(
            409, "VERSION_CONFLICT", "Retrieve the current transaction version"
        )
    preference_changed = False
    if manual and preference_action != "keep":
        merchant = merchant_match(fact.description)
        if merchant is None or (preference_action == "save" and category is None):
            raise TransactionFailure(
                422,
                "MERCHANT_PREFERENCE_INVALID",
                "Select a category and an identified merchant to remember",
            )
        saved = db.scalar(
            select(MerchantPreference).where(
                MerchantPreference.user_id == principal.user.id,
                MerchantPreference.workspace_id == principal.workspace.id,
                MerchantPreference.merchant_code == merchant.code,
            )
        )
        if preference_action == "forget":
            if saved is not None:
                db.delete(saved)
                preference_changed = True
        else:
            assert category is not None
            if saved is None:
                db.add(
                    MerchantPreference(
                        user_id=principal.user.id,
                        workspace_id=principal.workspace.id,
                        merchant_code=merchant.code,
                        category=category.value,
                    )
                )
                preference_changed = True
            elif saved.category != category.value:
                saved.category = category.value
                preference_changed = True
        db.flush()
    values = automatic_values(fact, preferences_for(db, principal))
    if metadata is None:
        metadata = TransactionEnrichment(
            transaction_id=fact.id,
            user_id=principal.user.id,
            automatic_updated_at=datetime.now(UTC),
            version=1,
            **values,
        )
        db.add(metadata)
        changed = True
    else:
        changed = preference_changed
    if manual:
        desired = category.value if category is not None else None
        if metadata.manual_category != desired:
            metadata.manual_category = desired
            metadata.manual_updated_at = datetime.now(UTC) if desired is not None else None
            changed = True
    if not manual or preference_action != "keep" or category is None:
        for key, value in values.items():
            if getattr(metadata, key) != value:
                setattr(metadata, key, value)
                changed = True
        if changed:
            metadata.automatic_updated_at = datetime.now(UTC)
    if changed:
        metadata.version = version + 1
        db.add(
            TransactionAudit(
                user_id=principal.user.id,
                transaction_id=fact.id,
                event_code="override" if manual else "reprocess",
                correlation_id=correlation_id,
            )
        )
    db.flush()
    return view(fact, metadata)
