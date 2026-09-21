"""Import use cases run inside the caller's authenticated database transaction."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from ledgerx.modules.identity.service import Principal
from ledgerx.modules.imports.errors import ImportFailure
from ledgerx.modules.imports.mapping import ColumnMapping, MappedCSV, read_table
from ledgerx.modules.imports.models import ImportAudit, ImportRow, StatementImport
from ledgerx.modules.imports.normalization import ERROR_MESSAGES, normalize
from ledgerx.modules.imports.parser import select_adapter
from ledgerx.modules.imports.schemas import (
    FinalizeView,
    ImportView,
    RowIssue,
    RowPage,
    RowView,
)
from ledgerx.modules.transactions.models import ImportedTransaction
from ledgerx.modules.transactions.service import enrich_import


def utcnow() -> datetime:
    return datetime.now(UTC)


def owned_import(
    db: Session,
    principal: Principal,
    import_id: UUID,
    *,
    lock: bool = False,
) -> StatementImport:
    query = select(StatementImport).where(
        StatementImport.id == import_id,
        StatementImport.user_id == principal.user.id,
        StatementImport.workspace_id == principal.workspace.id,
    )
    if lock:
        query = query.with_for_update()
    batch = db.scalar(query)
    if batch is None:
        raise ImportFailure(404, "IMPORT_NOT_FOUND", "Import was not found")
    return batch


def effective_status(batch: StatementImport) -> str:
    if batch.status != "completed" and batch.expires_at <= utcnow():
        return "expired"
    return batch.status


def row_page(db: Session, batch: StatementImport, after_row: int, limit: int) -> RowPage:
    if not 0 <= after_row <= 25001 or not 1 <= limit <= 100:
        raise ImportFailure(422, "PAGE_INVALID", "Use limit 1–100 and after_row 0–25001")
    if effective_status(batch) == "expired":
        return RowPage(items=[], next_after_row=None)
    model = ImportedTransaction if batch.status == "completed" else ImportRow
    rows = cast(
        list[ImportRow] | list[ImportedTransaction],
        list(
            db.scalars(
                select(model)
                .where(
                    model.user_id == batch.user_id,
                    model.import_id == batch.id,
                    model.source_row_number > after_row,
                )
                .order_by(model.source_row_number)
                .limit(limit + 1)
            ).all()
        ),
    )
    items = [
        RowView(
            source_row_number=row.source_row_number,
            transaction_date=row.transaction_date,
            description=row.description,
            amount=format(row.amount, ".4f") if row.amount is not None else None,
            currency=row.currency,
            errors=[
                RowIssue(code=code, message=ERROR_MESSAGES[code])
                for code in (row.errors if isinstance(row, ImportRow) else [])
            ],
        )
        for row in rows[:limit]
    ]
    return RowPage(
        items=items,
        next_after_row=items[-1].source_row_number if len(rows) > limit else None,
    )


def preview(db: Session, batch: StatementImport) -> ImportView:
    status = effective_status(batch)
    return ImportView(
        id=batch.id,
        status=status,
        parser_name=batch.parser_name,
        parser_version=batch.parser_version,
        total_rows=batch.total_rows,
        valid_rows=batch.valid_rows,
        invalid_rows=batch.invalid_rows,
        accepted_rows=batch.total_rows if status == "completed" else 0,
        period_start=batch.period_start,
        period_end=batch.period_end,
        currencies=batch.currencies,
        created_at=batch.created_at,
        expires_at=batch.expires_at,
        finalized_at=batch.finalized_at,
        can_finalize=status == "ready",
        can_save_mapping=status in {"ready", "completed"} and batch.mapping_spec is not None,
        rows=row_page(db, batch, 0, 50),
    )


def stage(
    db: Session,
    principal: Principal,
    content: bytes,
    parser_code: str,
    key: UUID,
    correlation_id: UUID,
    mapping: ColumnMapping | None = None,
) -> ImportView:
    adapter = MappedCSV(mapping) if mapping is not None else select_adapter(parser_code)
    # Bind retries to both the original bytes and every normalization choice.
    digest = hashlib.sha256(content).digest()
    # The authentication dependency already locks the owner across uploads and finalize.
    existing = db.scalar(
        select(StatementImport).where(
            StatementImport.user_id == principal.user.id,
            StatementImport.upload_key == key,
        )
    )
    if existing is not None:
        if (
            existing.file_sha256,
            existing.parser_name,
            existing.parser_version,
            existing.mapping_spec,
        ) != (
            digest,
            adapter.name,
            adapter.version,
            mapping.model_dump() if mapping else None,
        ):
            raise ImportFailure(
                409, "IDEMPOTENCY_KEY_REUSED", "Use a new key for a different upload"
            )
        return preview(db, existing)
    rows = [normalize(candidate) for candidate in adapter.candidates(content)]
    valid = [row for row in rows if not row.errors]
    dates = [row.transaction_date for row in valid if row.transaction_date is not None]
    now = utcnow()
    batch = StatementImport(
        user_id=principal.user.id,
        workspace_id=principal.workspace.id,
        upload_key=key,
        parser_name=adapter.name,
        parser_version=adapter.version,
        file_sha256=digest,
        status="ready" if len(valid) == len(rows) else "invalid",
        total_rows=len(rows),
        valid_rows=len(valid),
        invalid_rows=len(rows) - len(valid),
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        currencies=sorted({row.currency for row in valid if row.currency is not None}),
        created_at=now,
        expires_at=now + timedelta(hours=24),
        mapping_spec=mapping.model_dump() if mapping else None,
        source_headers=read_table(content).headers if mapping else None,
    )
    db.add(batch)
    db.flush()
    # Bounded batches avoid one enormous statement and keep insert parameters manageable.
    for start in range(0, len(rows), 500):
        db.execute(
            insert(ImportRow),
            [
                {
                    "user_id": principal.user.id,
                    "import_id": batch.id,
                    "source_row_number": row.source_row_number,
                    "transaction_date": row.transaction_date,
                    "description": row.description,
                    "amount": row.amount,
                    "currency": row.currency,
                    "fingerprint": row.fingerprint,
                    "errors": list(row.errors),
                }
                for row in rows[start : start + 500]
            ],
        )
    db.add(
        ImportAudit(
            user_id=principal.user.id,
            import_id=batch.id,
            event_code="staged",
            correlation_id=correlation_id,
        )
    )
    db.flush()
    return preview(db, batch)


def finalize(
    db: Session,
    principal: Principal,
    import_id: UUID,
    key: UUID,
    correlation_id: UUID,
) -> FinalizeView:
    batch = owned_import(db, principal, import_id, lock=True)
    used = db.scalar(
        select(StatementImport.id).where(
            StatementImport.user_id == principal.user.id,
            StatementImport.finalize_key == key,
        )
    )
    if used is not None and used != batch.id:
        raise ImportFailure(
            409, "IDEMPOTENCY_KEY_REUSED", "Key already belongs to another finalize"
        )
    if batch.status == "completed":
        if batch.finalize_key != key:
            raise ImportFailure(
                409, "FINALIZE_KEY_MISMATCH", "Retry with the original finalize key"
            )
        assert batch.finalized_at is not None
        return FinalizeView(
            id=batch.id,
            status="completed",
            accepted_rows=batch.total_rows,
            finalized_at=batch.finalized_at,
        )
    if effective_status(batch) == "expired":
        raise ImportFailure(
            409, "IMPORT_EXPIRED", "Preview expired; upload the corrected CSV again"
        )
    if batch.status != "ready" or batch.invalid_rows:
        raise ImportFailure(409, "IMPORT_INVALID", "Correct every invalid row and upload again")
    valid_rows = select(ImportRow).where(
        ImportRow.user_id == principal.user.id,
        ImportRow.import_id == batch.id,
    )
    count = db.scalar(select(func.count()).select_from(valid_rows.subquery()))
    invalid = db.scalar(
        select(func.count())
        .select_from(ImportRow)
        .where(
            ImportRow.user_id == principal.user.id,
            ImportRow.import_id == batch.id,
            func.cardinality(ImportRow.errors) != 0,
        )
    )
    if count != batch.total_rows or invalid:
        raise ImportFailure(409, "IMPORT_INTEGRITY_ERROR", "Staging is incomplete; upload again")
    columns = [
        "user_id",
        "import_id",
        "source_row_number",
        "transaction_date",
        "description",
        "amount",
        "currency",
        "fingerprint",
    ]
    db.execute(
        insert(ImportedTransaction).from_select(
            columns,
            select(*(getattr(ImportRow, column) for column in columns)).where(
                ImportRow.user_id == principal.user.id, ImportRow.import_id == batch.id
            ),
        )
    )
    enrich_import(db, principal, batch.id)
    # Check the clock again after copying: expiry during processing must roll back all facts.
    now = utcnow()
    if now >= batch.expires_at:
        raise ImportFailure(409, "IMPORT_EXPIRED", "Preview expired; upload again")
    batch.status = "completed"
    batch.finalized_at = now
    batch.finalize_key = key
    db.execute(
        delete(ImportRow).where(
            ImportRow.user_id == principal.user.id,
            ImportRow.import_id == batch.id,
        )
    )
    db.add(
        ImportAudit(
            user_id=principal.user.id,
            import_id=batch.id,
            event_code="finalized",
            correlation_id=correlation_id,
        )
    )
    db.flush()
    return FinalizeView(
        id=batch.id,
        status="completed",
        accepted_rows=batch.total_rows,
        finalized_at=now,
    )


def purge_expired(db: Session, *, limit: int, correlation_id: UUID) -> int:
    """Privileged maintenance only; row locks serialize cleanup with finalization."""
    if not 1 <= limit <= 100:
        raise ValueError("Cleanup batch limit must be 1–100")
    batches = db.scalars(
        select(StatementImport)
        .where(
            StatementImport.status.in_(["ready", "invalid"]),
            StatementImport.expires_at <= utcnow(),
        )
        .order_by(StatementImport.expires_at, StatementImport.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    for batch in batches:
        db.execute(
            delete(ImportRow).where(
                ImportRow.user_id == batch.user_id,
                ImportRow.import_id == batch.id,
            )
        )
        batch.status = "expired"
        db.add(
            ImportAudit(
                user_id=batch.user_id,
                import_id=batch.id,
                event_code="expired",
                correlation_id=correlation_id,
            )
        )
    db.flush()
    return len(batches)
