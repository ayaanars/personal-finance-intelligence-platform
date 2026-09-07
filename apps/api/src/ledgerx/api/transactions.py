from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request

from ledgerx.api.auth_schemas import EmptyMutation
from ledgerx.api.auth_security import Authenticated
from ledgerx.modules.transactions import service
from ledgerx.modules.transactions.schemas import CategoryOverride, TransactionPage, TransactionView

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.get("")
def transactions(
    context: Authenticated,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> TransactionPage:
    return service.list_transactions(context.db, context.principal, limit, cursor)


@router.get("/{transaction_id}")
def transaction(transaction_id: UUID, context: Authenticated) -> TransactionView:
    fact = service.owned_fact(context.db, context.principal, transaction_id)
    return service.view(fact, service.enrichment(context.db, context.principal, transaction_id))


@router.patch("/{transaction_id}/category")
def override(
    transaction_id: UUID,
    body: CategoryOverride,
    request: Request,
    context: Authenticated,
    if_match: Annotated[str, Header(pattern=r'^"[0-9]{1,10}"$')],
) -> TransactionView:
    return service.update(
        context.db,
        context.principal,
        transaction_id,
        UUID(request.state.correlation_id),
        manual=True,
        category=body.category,
        expected_version=int(if_match.strip('"')),
    )


@router.post("/{transaction_id}/reprocess")
def reprocess(
    transaction_id: UUID, body: EmptyMutation, request: Request, context: Authenticated
) -> TransactionView:
    return service.update(
        context.db,
        context.principal,
        transaction_id,
        UUID(request.state.correlation_id),
        manual=False,
    )
