"""Deterministic imported-activity estimates; never balances or promises."""

import calendar
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from pydantic import BaseModel

from ledgerx.modules.analytics.calculations import ZERO, money, month_name, shift_month
from ledgerx.modules.analytics.intelligence import Observation
from ledgerx.modules.analytics.recurring import recurring


class Commitment(BaseModel):
    merchant: str
    amount: str
    state: Literal["observed", "remaining", "overdue"]
    expected_day: str


class Forecast(BaseModel):
    currency: str
    state: Literal["estimate", "historical", "unavailable"]
    quality: str
    elapsed_days: int
    days_in_month: int
    history_months: int
    observed_span_days: int
    last_activity: str | None
    actual_spending: str
    actual_outflow: str
    actual_net_cash_flow: str
    projected_spending: str | None
    projected_outflow: str | None
    projected_net_cash_flow: str | None
    remaining_recurring: str
    commitments: list[Commitment]
    explanation: str
    insight: str | None


def forecast(rows: list[Observation], selected: date, today: date, currency: str) -> Forecast:
    with localcontext() as ctx:
        ctx.prec = 60
        ctx.rounding = ROUND_HALF_EVEN
        return _forecast(rows, selected, today, currency)


def _forecast(rows: list[Observation], selected: date, today: date, currency: str) -> Forecast:
    selected = selected.replace(day=1)
    days = calendar.monthrange(selected.year, selected.month)[1]
    end = selected.replace(day=days)
    cutoff = min(today, end)
    rows = list(
        {r.identifier: r for r in rows if r.currency == currency and r.day <= cutoff}.values()
    )
    current = [r for r in rows if selected <= r.day <= cutoff]
    observed_span = (
        (max(r.day for r in current) - min(r.day for r in current)).days + 1 if current else 0
    )
    recent = bool(current) and (cutoff - max(r.day for r in current)).days <= 3
    elapsed = max(0, min(days, (cutoff - selected).days + 1))
    spending = sum((-r.amount for r in current if r.spending), ZERO)
    outflow = sum((-r.amount for r in current if r.amount < 0), ZERO)
    net = sum((r.amount for r in current), ZERO)
    prior = []
    for offset in (-1, -2, -3):
        start = shift_month(selected, offset)
        group = [r for r in rows if month_name(r.day) == month_name(start)]
        # Broad date coverage is evidence, not proof of a complete statement.
        if (
            start >= selected
            or not group
            or min(r.day.day for r in group) > 7
            or max(r.day.day for r in group) < 21
        ):
            break
        prior.append(group)
    qualified = (
        recurring(rows, shift_month(selected, -1)).payments
        if selected.year > 1 or selected.month > 1
        else []
    )
    # Newly qualified patterns can describe this month's actual charge, but cannot
    # invent an outstanding charge without three completed prior-month examples.
    qualified = list(
        {p.merchant: p for p in [*qualified, *recurring(rows, selected).payments]}.values()
    )
    merchants = {p.merchant for p in qualified}
    commitments = []
    remaining = ZERO
    for payment in qualified:
        typical_day = sorted(date.fromisoformat(e.day).day for e in payment.evidence)[1]
        due = selected.replace(day=min(days, typical_day))
        observed = [
            r
            for r in current
            if r.merchant == payment.merchant and r.spending and not r.return_signal
        ]
        state: Literal["observed", "remaining", "overdue"] = (
            "observed" if observed else "remaining" if due > cutoff else "overdue"
        )
        value = (
            sum((-r.amount for r in observed), ZERO)
            if observed
            else Decimal(payment.typical_amount)
        )
        if state == "remaining" and elapsed:
            remaining += value
        commitments.append(
            Commitment(
                merchant=payment.merchant,
                amount=money(value),
                state=state,
                expected_day=due.isoformat(),
            )
        )

    income_totals = sorted(
        sum((r.amount for r in group if r.amount > 0 and r.category == "Income"), ZERO)
        for group in prior
    )
    stable_income = (
        income_totals[1]
        if len(income_totals) == 3
        and income_totals[1] > 0
        and all(
            abs(v - income_totals[1]) <= income_totals[1] * Decimal("0.05") for v in income_totals
        )
        else None
    )

    def variable(group: list[Observation], metric: str) -> Decimal:
        if metric == "spending":
            return sum(
                (-r.amount for r in group if r.spending and r.merchant not in merchants), ZERO
            )
        if metric == "outflow":
            return sum(
                (
                    -r.amount
                    for r in group
                    if r.amount < 0 and not (r.spending and r.merchant in merchants)
                ),
                ZERO,
            )
        return sum(
            (
                r.amount
                for r in group
                if r.amount > 0 and (stable_income is None or r.category != "Income")
            ),
            ZERO,
        )

    def future(metric: str) -> Decimal:
        pace = variable(current, metric) / Decimal(elapsed)
        if len(prior) >= 3:
            historical = sum(
                (
                    variable(g, metric)
                    / Decimal(calendar.monthrange(g[0].day.year, g[0].day.month)[1])
                    for g in prior
                ),
                ZERO,
            ) / Decimal(len(prior))
            pace = (pace + historical) / 2
        result = pace * Decimal(days - elapsed)
        if metric == "inflows" and stable_income is not None and elapsed < days:
            received = sum(
                (r.amount for r in current if r.amount > 0 and r.category == "Income"), ZERO
            )
            result += max(ZERO, stable_income - received)
        return result

    available = bool(current) and elapsed > 0
    historical = end < today
    ps = spending + future("spending") + remaining if available else None
    po = outflow + future("outflow") + remaining if available else None
    pn = net + future("inflows") - future("outflow") - remaining if available else None
    quality = (
        "Observed outcome"
        if historical
        else "Stronger estimate"
        if observed_span >= 21 and recent and len(prior) >= 3
        else "Developing estimate"
        if observed_span >= 8 and recent and prior
        else "Early estimate"
    )
    explanation = (
        "Current daily pace"
        + (
            " blended equally with three recent broadly observed months"
            if len(prior) >= 3
            else "; limited history, using current pace only"
        )
        + ". Qualified recurring spending is removed from pace and future due charges added once. "
        + (
            "Income uses the median of three stable prior monthly totals, less income already "
            "observed; other inflows use pace. Expected income is not guaranteed. "
            if stable_income is not None
            else "Inflows use the same pace method; salary timing is not promised. "
        )
        + "Imported coverage may be incomplete."
    )
    if historical:
        explanation = (
            "Observed imported outcome for a past month; no future charges added. "
            "Coverage may be incomplete."
        )
    return Forecast(
        currency=currency,
        state="historical"
        if historical and available
        else "estimate"
        if available
        else "unavailable",
        quality=quality if available else "Not enough current-month activity",
        elapsed_days=elapsed,
        days_in_month=days,
        history_months=len(prior),
        observed_span_days=observed_span,
        last_activity=max(r.day for r in current).isoformat() if current else None,
        actual_spending=money(spending),
        actual_outflow=money(outflow),
        actual_net_cash_flow=money(net),
        projected_spending=money(ps) if ps is not None else None,
        projected_outflow=money(po) if po is not None else None,
        projected_net_cash_flow=money(pn) if pn is not None else None,
        remaining_recurring=money(remaining),
        commitments=commitments,
        explanation=explanation,
        insight="Recurring commitments account for most of the remaining expected outflow."
        if po is not None and remaining > (po - outflow) / 2 and remaining > 0
        else None,
    )


def goal_status(
    kind: str, target: Decimal, actual: Decimal, projected: Decimal | None, elapsed: int, days: int
) -> str:
    if projected is None:
        return "Awaiting activity"
    pace_target = target * Decimal(elapsed) / Decimal(days)
    if kind == "spending":
        if actual > target or (projected > target and actual > pace_target):
            return "Off track"
        return "Watch closely" if projected > target or actual > pace_target else "On track"
    if projected < target and actual < pace_target:
        return "Off track"
    return "Watch closely" if projected < target or actual < pace_target else "On track"
