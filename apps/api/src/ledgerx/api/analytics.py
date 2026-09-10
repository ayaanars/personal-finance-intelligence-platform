from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ledgerx.api.auth_security import Authenticated
from ledgerx.modules.analytics.intelligence_service import IntelligenceOverview, intelligence
from ledgerx.modules.analytics.relationships import RelationshipsReport, relationships
from ledgerx.modules.analytics.schemas import Overview
from ledgerx.modules.analytics.service import overview
from ledgerx.modules.analytics.unusual import UnusualReport, unusual

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class OverviewQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str | None = Field(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")

    @field_validator("month")
    @classmethod
    def valid_month(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value + "-01")
        return value


@router.get("/overview")
def get_overview(context: Authenticated, query: Annotated[OverviewQuery, Query()]) -> Overview:
    return overview(context.db, context.principal, query.month)


@router.get("/intelligence")
def get_intelligence(
    context: Authenticated, query: Annotated[OverviewQuery, Query()]
) -> IntelligenceOverview:
    return intelligence(context.db, context.principal, query.month)


@router.get("/unusual")
def get_unusual(context: Authenticated, query: Annotated[OverviewQuery, Query()]) -> UnusualReport:
    return unusual(context.db, context.principal, query.month)


@router.get("/relationships")
def get_relationships(
    context: Authenticated, query: Annotated[OverviewQuery, Query()]
) -> RelationshipsReport:
    return relationships(context.db, context.principal, query.month)
