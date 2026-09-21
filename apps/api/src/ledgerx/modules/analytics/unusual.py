"""Versioned advisory evidence from the existing personal baseline window."""

from collections import Counter
from datetime import date
from decimal import Decimal, localcontext
from statistics import median
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ledgerx.modules.analytics.baselines import baselines
from ledgerx.modules.analytics.calculations import ZERO, money, month_name, percent, shift_month
from ledgerx.modules.analytics.intelligence import Observation
from ledgerx.modules.analytics.intelligence_service import load_history
from ledgerx.modules.analytics.recurring import recurring
from ledgerx.modules.analytics.unusual_ml import ml_support
from ledgerx.modules.identity.service import Principal


class Evidence(BaseModel):
    code: str
    explanation: str
    current: str
    reference: str | None = None
    unit: Literal["money", "count"] = "money"
    ratio: str | None = None
    reference_scale: str | None = None


class Anomaly(BaseModel):
    basis: Literal["historical", "current_month"] = "historical"
    identifier: str
    subject: str
    day: str | None = None
    severity: Literal["Notable", "High"] = "Notable"
    evidence: list[Evidence]
    transaction_ids: list[str]
    ml_supported: bool = False


class UnusualCurrency(BaseModel):
    currency: str
    state: Literal["available", "insufficient_history", "no_activity"]
    prior_months: list[str]
    historical_purchases: int
    ml_state: Literal["active", "insufficient_history", "unavailable", "no_activity"]
    total: int
    items: list[Anomaly]


class UnusualReport(BaseModel):
    month: str | None
    available_months: list[str]
    currencies: list[UnusualCurrency]
    methodology_version: Literal["unusual-v2"] = "unusual-v2"
    coverage_note: str = (
        "Advisory comparisons with your own imported history, not fraud findings. "
        "Partial or overlapping statements can change the evidence. Currency views are separate. "
        "Category, merchant and purchase signals overlap; counts are observations, not incidents."
    )


def evaluate(rows: list[Observation], selected: date, currency: str) -> UnusualCurrency:
    # Enforce the currency boundary even for direct callers.
    rows = [r for r in rows if r.currency == currency]
    with localcontext() as context:
        context.prec = 60
        baseline = baselines(rows, selected)
        months = baseline.prior_months
        purchases = [r for r in rows if r.spending and not r.return_signal]
        history = [r for r in purchases if month_name(r.day) in months]
        current = sorted(
            [r for r in purchases if month_name(r.day) == month_name(selected)],
            key=lambda r: (r.day, r.identifier),
        )
        enough = len(months) >= 3 and len(history) >= 20
        ml_state, supported = ml_support(history, current, len(months))
        items: dict[str, Anomaly] = {}

        def add(
            key: str,
            subject: str,
            code: str,
            explanation: str,
            value: Decimal,
            reference: Decimal | None,
            ids: list[str],
            day: str | None = None,
            unit: Literal["money", "count"] = "money",
            high: bool = False,
            basis: Literal["historical", "current_month"] = "historical",
        ) -> None:
            item = items.setdefault(
                key,
                Anomaly(
                    identifier=key,
                    subject=subject,
                    day=day,
                    evidence=[],
                    transaction_ids=ids[:5],
                    basis=basis,
                ),
            )
            item.transaction_ids = list(dict.fromkeys(item.transaction_ids + ids))[:5]
            ratio = percent(value, reference * 100) if reference else None
            item.evidence.append(
                Evidence(
                    code=code,
                    explanation=explanation,
                    current=money(value),
                    reference=money(reference) if reference is not None else None,
                    ratio=ratio,
                    unit=unit,
                    reference_scale=percent(reference, max(value, reference))
                    if reference is not None and max(value, reference)
                    else None,
                )
            )
            if high:
                item.severity = "High"
            item.ml_supported = any(identifier in supported for identifier in ids)

        # Descriptive peer comparison, not a claim about this user's personal normal.
        # Keep scarce evidence quiet; no ML, novelty, or recurring inference from one month.
        if not enough and len(current) >= 6:
            current_median = median([-r.amount for r in current])
            current_total = sum((-r.amount for r in current), ZERO)
            for row in current:
                value = -row.amount
                if value >= current_median * 4 and value >= current_total / 4:
                    add(
                        row.identifier,
                        row.merchant or row.category,
                        "current_month_large_purchase",
                        "At least 4× this month's median purchase and 25% of this month's spending "
                        "across at least six purchases. Current-month comparison only, not a "
                        "historical anomaly or fraud finding.",
                        value,
                        current_median,
                        [row.identifier],
                        row.day.isoformat(),
                        basis="current_month",
                    )

        if enough:
            typical = median([-r.amount for r in history])
            largest = max(-r.amount for r in history)
            seen = {r.merchant for r in purchases if r.day < selected and r.merchant}
            for row in current:
                value = -row.amount
                if value >= typical * 3 and value > largest:
                    add(
                        row.identifier,
                        row.merchant or row.category,
                        "large_purchase",
                        "Larger than every reference purchase and at least 3× the median purchase.",
                        value,
                        typical,
                        [row.identifier],
                        row.day.isoformat(),
                        high=value >= typical * 6,
                    )
                if row.merchant and row.merchant not in seen:
                    add(
                        row.identifier,
                        row.merchant,
                        "first_observed_merchant",
                        "First observed merchant in this currency's seven-month imported window; "
                        "this does not establish a first-ever purchase.",
                        value,
                        None,
                        [row.identifier],
                        row.day.isoformat(),
                    )
                    seen.add(row.merchant)
            counts = Counter(month_name(r.day) for r in history)
            reference_count = Decimal(sum(counts.values())) / len(months)
            if len(current) >= reference_count * 2 and len(current) > max(counts.values()):
                add(
                    "frequency",
                    "Purchase frequency",
                    "frequency_spike",
                    "Purchase count is at least 2× the prior monthly mean and above every "
                    "reference month. Observed totals are not adjusted for partial months.",
                    Decimal(len(current)),
                    reference_count,
                    [r.identifier for r in current],
                    unit="count",
                    high=len(current) >= reference_count * 3,
                )
            for merchant in sorted({r.merchant for r in current if r.merchant}):
                previous = [r for r in history if r.merchant == merchant]
                totals = [
                    sum((-r.amount for r in previous if month_name(r.day) == m), ZERO)
                    for m in months
                ]
                now = [r for r in current if r.merchant == merchant]
                value = sum((-r.amount for r in now), ZERO)
                mean = sum(totals, ZERO) / len(months)
                if sum(t > 0 for t in totals) >= 3 and value >= mean * 2 and value > max(totals):
                    add(
                        "merchant:" + merchant,
                        merchant,
                        "merchant_spike",
                        "Merchant spending is at least 2× the prior monthly mean and above "
                        "every reference month.",
                        value,
                        mean,
                        [r.identifier for r in now],
                        high=value >= mean * 3,
                    )

        for category in baseline.categories:
            if category.state != "available":
                continue
            value, mean = Decimal(category.current or "0"), Decimal(category.mean or "0")
            if (
                mean > 0
                and value >= mean * Decimal("1.5")
                and value > Decimal(category.high or "0")
            ):
                add(
                    "category:" + category.name,
                    category.name,
                    "category_spike",
                    "Category spending is at least 50% above the personal baseline mean "
                    "and outside its observed range.",
                    value,
                    mean,
                    [r.identifier for r in current if r.category == category.name],
                    high=value >= mean * 3,
                )

        for payment in recurring(rows, shift_month(selected, -1)).payments:
            now = [r for r in current if r.merchant == payment.merchant]
            if len(now) != 1:
                continue
            row = now[0]
            gap = (row.day - date.fromisoformat(payment.evidence[-1].day)).days
            typical, value = Decimal(payment.typical_amount), -row.amount
            if 21 <= gap <= 40 and abs(value - typical) >= typical * Decimal("0.2"):
                add(
                    row.identifier,
                    payment.merchant,
                    "recurring_amount_change",
                    "A previously stable monthly pattern changed by at least 20%; "
                    "the new charge retains a 21–40-day gap. "
                    "This is a likely pattern, not a contract.",
                    value,
                    typical,
                    [row.identifier] + [e.identifier for e in payment.evidence],
                    row.day.isoformat(),
                    high=abs(value - typical) >= typical,
                )

        ranked = sorted(
            items.values(),
            key=lambda i: (
                i.severity != "High",
                -len(i.evidence),
                not i.ml_supported,
                -max(Decimal(e.ratio or "0") for e in i.evidence),
                i.identifier,
            ),
        )
        return UnusualCurrency(
            currency=currency,
            state="no_activity"
            if not any(month_name(r.day) == month_name(selected) for r in rows)
            else "available"
            if len(months) >= 3
            else "insufficient_history",
            prior_months=months,
            historical_purchases=len(history),
            ml_state=ml_state,
            total=len(ranked),
            items=ranked[:100],
        )


def unusual(db: Session, principal: Principal, month: str | None) -> UnusualReport:
    selected, available, observations = load_history(db, principal, month)
    return UnusualReport(
        month=selected,
        available_months=available,
        currencies=[
            evaluate(rows, date.fromisoformat(selected + "-01"), currency)
            for currency, rows in sorted(observations.items())
        ]
        if selected
        else [],
    )
