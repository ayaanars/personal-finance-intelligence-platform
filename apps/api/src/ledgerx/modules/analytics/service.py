"""Owner-scoped aggregates with bounded history and legacy interpretation fallback."""

import calendar
from collections.abc import Iterator
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledgerx.modules.analytics.calculations import (
    Activity,
    build_currencies,
    month_name,
    shift_month,
)
from ledgerx.modules.analytics.schemas import Overview
from ledgerx.modules.identity.service import Principal
from ledgerx.modules.transactions.enrichment_models import TransactionEnrichment as Enrichment
from ledgerx.modules.transactions.models import ImportedTransaction as Fact
from ledgerx.modules.transactions.service import owned_query
from ledgerx.modules.transactions.understanding import understand


def overview(db: Session, principal: Principal, month: str | None) -> Overview:
    owned = owned_query(principal)
    period = func.to_char(Fact.transaction_date, "YYYY-MM")
    available = list(
        db.scalars(owned.with_only_columns(period).distinct().order_by(period.desc()).limit(120))
    )
    selected_text = month or (available[0] if available else None)
    if selected_text is None:
        return Overview(month=None, available_months=[], window_start=None, currencies=[])
    selected = date.fromisoformat(selected_text + "-01")
    start = shift_month(selected, -5)
    end = date(selected.year, selected.month, calendar.monthrange(selected.year, selected.month)[1])
    window = owned.where(Fact.transaction_date >= start, Fact.transaction_date <= end)
    join = (Enrichment.transaction_id == Fact.id) & (Enrichment.user_id == Fact.user_id)
    category = func.coalesce(Enrichment.manual_category, Enrichment.automatic_category)
    grouped = (
        window.join(Enrichment, join)
        .with_only_columns(
            period,
            Fact.currency,
            category,
            Enrichment.merchant,
            func.sum(Fact.amount),
            func.count(),
            func.min(Fact.transaction_date),
            func.max(Fact.transaction_date),
        )
        .group_by(period, Fact.currency, category, Enrichment.merchant, Fact.amount > 0)
    )

    def activity() -> Iterator[Activity]:
        for row in db.execute(grouped):
            yield Activity(*row)
        # One streaming query, not an N+1. Never write enrichment during analytics reads.
        legacy = window.outerjoin(Enrichment, join).where(Enrichment.transaction_id.is_(None))
        for fact in db.scalars(legacy.execution_options(yield_per=500)):
            understood = understand(fact.description, fact.amount)
            yield Activity(
                month_name(fact.transaction_date),
                fact.currency,
                understood.category.value,
                understood.merchant,
                fact.amount,
                1,
                fact.transaction_date,
                fact.transaction_date,
            )

    return Overview(
        month=selected_text,
        available_months=available,
        window_start=month_name(start),
        currencies=build_currencies(activity(), selected),
    )
