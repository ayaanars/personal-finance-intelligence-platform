"""Transparent observed-history baselines, never a model of complete bank coverage."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from pydantic import BaseModel

from ledgerx.modules.analytics.calculations import ZERO, money, month_name, percent, shift_month
from ledgerx.modules.analytics.intelligence import Observation


class Baseline(BaseModel):
    name: str
    kind: Literal["metric", "category"]
    state: Literal["available", "insufficient_history", "no_activity"]
    current: str | None
    mean: str | None = None
    low: str | None = None
    high: str | None = None
    average_three: str | None = None
    average_six: str | None = None
    delta: str | None = None
    relative_percent: str | None = None
    position: Literal["above", "within", "below"] | None = None
    current_scale: str | None = None
    low_scale: str | None = None
    high_scale: str | None = None
    mean_scale: str | None = None
    months: list[str]
    values: list[str]


class BaselineReport(BaseModel):
    prior_months: list[str]
    observed_months: int
    metrics: list[Baseline]
    categories: list[Baseline]
    method: str = (
        "Mean and observed min-max of 3-6 consecutive prior months with imported activity. "
        "The selected month is excluded. Missing months break the run. This is an observed "
        "range, not a statistical confidence interval or proof of complete coverage."
    )


def baselines(rows: list[Observation], selected: date) -> BaselineReport:
    """Caller supplies exactly one currency from the owned seven-month window."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        monthly: dict[str, dict[str, Decimal]] = {}
        category_monthly: dict[str, dict[str, Decimal]] = {}
        names: set[str] = set()
        for row in rows:
            month = month_name(row.day)
            values = monthly.setdefault(month, defaultdict(Decimal))
            categories = category_monthly.setdefault(month, defaultdict(Decimal))
            if row.amount > 0 and row.category == "Income":
                values["Income"] += row.amount
            if row.amount < 0:
                values["Outflow"] -= row.amount
            if row.spending:
                values["Spending"] -= row.amount
                category = "Other" if row.category == "Income" else row.category
                categories[category] -= row.amount
                names.add(category)
        selected_month = month_name(selected)
        prior: list[str] = []
        for offset in range(1, 7):
            month = month_name(shift_month(selected, -offset))
            # shift_month clamps at year 1; never repeat the boundary month.
            if month == selected_month or month in prior or month not in monthly:
                break
            prior.append(month)
        prior.reverse()

        def build(name: str, kind: Literal["metric", "category"]) -> Baseline:
            source = monthly if kind == "metric" else category_monthly
            values = [source[month].get(name, ZERO) for month in prior]
            current = source.get(selected_month, {}).get(name, ZERO)
            enough = len(prior) >= 3 and (
                kind == "metric" or sum(value > 0 for value in values) >= 3
            )
            state: Literal["available", "insufficient_history", "no_activity"] = (
                "no_activity"
                if selected_month not in monthly
                else "insufficient_history"
                if not enough
                else "available"
            )
            result = Baseline(
                name=name,
                kind=kind,
                state=state,
                current=money(current) if selected_month in monthly else None,
                months=prior,
                values=[money(value) for value in values],
            )
            if not enough:
                return result
            # Quantize the derived mean at its boundary so deltas reconcile to its display.
            mean = Decimal(money(sum(values, ZERO) / len(values)))
            low, high = min(values), max(values)
            result.mean, result.low, result.high = money(mean), money(low), money(high)
            result.average_three = money(sum(values[-3:], ZERO) / 3)
            result.average_six = money(mean) if len(values) == 6 else None
            if state == "no_activity":
                return result
            result.delta = money(current - mean)
            result.relative_percent = percent(current - mean, mean)
            result.position = "above" if current > high else "below" if current < low else "within"
            maximum = max(current, high) * Decimal("1.1")
            result.current_scale = percent(current, maximum) or "0.00"
            result.low_scale = percent(low, maximum) or "0.00"
            result.high_scale = percent(high, maximum) or "0.00"
            result.mean_scale = percent(mean, maximum) or "0.00"
            return result

        return BaselineReport(
            prior_months=prior,
            observed_months=len(monthly),
            metrics=[build(name, "metric") for name in ("Spending", "Outflow", "Income")],
            categories=[build(name, "category") for name in sorted(names)],
        )
