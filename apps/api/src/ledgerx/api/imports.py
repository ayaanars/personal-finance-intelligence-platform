"""Authenticated CSV upload, bounded preview and explicit finalize transport."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from starlette.concurrency import run_in_threadpool

from ledgerx.api.auth_schemas import EmptyMutation
from ledgerx.api.auth_security import Authenticated, AuthenticatedCSV
from ledgerx.api.import_upload import read_csv_upload
from ledgerx.modules.imports import service
from ledgerx.modules.imports.schemas import FinalizeView, ImportView, RowPage

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])
IdempotencyKey = Annotated[UUID, Header(alias="Idempotency-Key")]


@router.post(
    "",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload(
    request: Request,
    context: AuthenticatedCSV,
    idempotency_key: IdempotencyKey,
    x_filename: Annotated[str, Header(max_length=124)],
    parser_code: Annotated[str, Query(max_length=80)] = "ledgerx-canonical",
) -> ImportView:
    content = await read_csv_upload(request)
    try:
        return await run_in_threadpool(
            service.stage,
            context.db,
            context.principal,
            content,
            parser_code,
            idempotency_key,
            UUID(request.state.correlation_id),
        )
    finally:
        del content


@router.get("/{import_id}")
def preview(import_id: UUID, context: Authenticated) -> ImportView:
    return service.preview(
        context.db, service.owned_import(context.db, context.principal, import_id)
    )


@router.get("/{import_id}/rows")
def rows(
    import_id: UUID,
    context: Authenticated,
    after_row: Annotated[int, Query(ge=0, le=25001)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RowPage:
    batch = service.owned_import(context.db, context.principal, import_id)
    return service.row_page(context.db, batch, after_row, limit)


@router.post("/{import_id}/finalize")
def finalize(
    import_id: UUID,
    body: EmptyMutation,
    request: Request,
    context: Authenticated,
    idempotency_key: IdempotencyKey,
) -> FinalizeView:
    return service.finalize(
        context.db,
        context.principal,
        import_id,
        idempotency_key,
        UUID(request.state.correlation_id),
    )
