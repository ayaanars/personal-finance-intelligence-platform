from typing import Annotated

from fastapi import APIRouter, Query, Response

from ledgerx.api.analytics import OverviewQuery
from ledgerx.api.auth_security import Authenticated
from ledgerx.modules.goals.service import GoalInput, GoalKey, Plan, plan, remove, save

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


@router.get("")
def get_plan(context: Authenticated, query: Annotated[OverviewQuery, Query()]) -> Plan:
    return plan(context.db, context.principal, query.month)


@router.put("", status_code=204)
def put_goal(context: Authenticated, body: GoalInput) -> Response:
    save(context.db, context.principal, body)
    return Response(status_code=204)


@router.delete("", status_code=204)
def delete_goal(context: Authenticated, body: GoalKey) -> Response:
    remove(context.db, context.principal, body)
    return Response(status_code=204)
