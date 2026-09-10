"""A coherent intelligence response under the existing authenticated owner lock."""

import calendar
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ledgerx.modules.analytics.baselines import BaselineReport, baselines
from ledgerx.modules.analytics.calculations import (
    Activity,
    build_currencies,
    month_name,
    shift_month,
)
from ledgerx.modules.analytics.intelligence import Behaviour, Observation, behaviour
from ledgerx.modules.analytics.recurring import RecurringReport, recurring
from ledgerx.modules.analytics.schemas import CurrencyOverview
from ledgerx.modules.identity.service import Principal
from ledgerx.modules.transactions.enrichment_models import TransactionEnrichment as Enrichment
from ledgerx.modules.transactions.models import ImportedTransaction as Fact
from ledgerx.modules.transactions.service import owned_query
from ledgerx.modules.transactions.understanding import understand


class IntelligenceCurrency(CurrencyOverview):
    behaviour: Behaviour
    baselines: BaselineReport
    recurring: RecurringReport


class IntelligenceOverview(BaseModel):
    month: str | None
    available_months: list[str]
    window_start: str | None
    currencies: list[IntelligenceCurrency]
    methodology_version: Literal["intelligence-v1"] = "intelligence-v1"
    intelligence_version: Literal["longitudinal-v1"] = "longitudinal-v1"
    coverage_note: str = (
        "Based on finalized imported activity, which may cover partial months or overlapping "
        "statements. Categories reflect your current corrections. This is not an account balance."
    )


def load_history(
    db: Session, principal: Principal, month: str | None, *, history_months: Literal[6, 14] = 6
) -> tuple[str | None, list[str], dict[str, list[Observation]]]:
    owned = owned_query(principal)
    period = func.to_char(Fact.transaction_date, "YYYY-MM")
    available = list(
        db.scalars(owned.with_only_columns(period).distinct().order_by(period.desc()).limit(120))
    )
    selected_text = month or (available[0] if available else None)
    if selected_text is None:
        return None, [], {}
    selected = date.fromisoformat(selected_text + "-01")
    start = shift_month(selected, -history_months)
    end = date(selected.year, selected.month, calendar.monthrange(selected.year, selected.month)[1])
    query = owned.outerjoin(
        Enrichment, (Enrichment.transaction_id == Fact.id) & (Enrichment.user_id == Fact.user_id)
    )
    query = query.where(Fact.transaction_date >= start, Fact.transaction_date <= end)
    observations: dict[str, list[Observation]] = {}
    for fact, metadata in db.execute(
        query.add_columns(Enrichment).execution_options(yield_per=500)
    ):
        if metadata is None:
            auto = understand(fact.description, fact.amount)
            category, merchant, rule = auto.category.value, auto.merchant, auto.rule_id
        else:
            category = metadata.manual_category or metadata.automatic_category
            merchant, rule = metadata.merchant, metadata.rule_id
        observations.setdefault(fact.currency, []).append(
            Observation(
                str(fact.id),
                fact.transaction_date,
                fact.currency,
                category,
                merchant,
                fact.amount,
                rule.startswith("return_"),
            )
        )
    return selected_text, available, observations


def intelligence(db: Session, principal: Principal, month: str | None) -> IntelligenceOverview:
    selected_text, available, observations = load_history(db, principal, month)
    if selected_text is None:
        return IntelligenceOverview(
            month=None, available_months=[], window_start=None, currencies=[]
        )
    selected = date.fromisoformat(selected_text + "-01")
    start = shift_month(selected, -6)
    # A single streaming owner-scoped read supplies summaries and date-level views.
    summaries = build_currencies(
        (
            Activity(
                month_name(r.day), r.currency, r.category, r.merchant, r.amount, 1, r.day, r.day
            )
            for rows in observations.values()
            for r in rows
        ),
        selected,
    )
    return IntelligenceOverview(
        month=selected_text,
        available_months=available,
        window_start=month_name(start),
        currencies=[
            IntelligenceCurrency(
                **summary.model_dump(),
                behaviour=behaviour(observations[summary.currency], selected),
                baselines=baselines(observations[summary.currency], selected),
                recurring=recurring(observations[summary.currency], selected),
            )
            for summary in summaries
        ],
    )
