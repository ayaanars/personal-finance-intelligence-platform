"""Five predeclared descriptive associations, never causal or predictive claims."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from statistics import median
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ledgerx.modules.analytics.calculations import (
    ZERO,
    Activity,
    Bucket,
    money,
    month_name,
    shift_month,
)
from ledgerx.modules.analytics.intelligence import Observation, behaviour
from ledgerx.modules.analytics.intelligence_service import load_history
from ledgerx.modules.analytics.recurring import recurring
from ledgerx.modules.identity.service import Principal

MIN_MONTHS = 6
STRONG = Decimal("0.65")
STABLE = Decimal("0.35")


class Pair(BaseModel):
    month: str
    previous_month: str | None = None
    x: str
    y: str


class Group(BaseModel):
    months: list[str]
    x_mean: str
    y_mean: str


class Evolution(BaseModel):
    earlier_months: list[str]
    recent_months: list[str]
    earlier_direction: Literal["together", "opposite", "not_clear"]
    recent_direction: Literal["together", "opposite", "not_clear"]


class Relationship(BaseModel):
    code: str
    x_label: str
    y_label: str
    direction: Literal["together", "opposite"]
    interpretation: str
    caveat: str
    months: list[str]
    sample_count: int
    coefficient: str
    median_x: str
    higher: Group
    other: Group
    points: list[Pair]
    evolution: Evolution | None = None


class Screening(BaseModel):
    code: str
    sample_count: int
    state: Literal["insufficient_history", "limited_variation", "not_clear", "supported"]


class RelationshipCurrency(BaseModel):
    currency: str
    state: Literal["available", "insufficient_history", "no_clear_relationship", "no_activity"]
    observed_months: list[str]
    missing_months: list[str]
    items: list[Relationship]
    screening: list[Screening]


class RelationshipsReport(BaseModel):
    month: str | None
    window_start: str | None
    available_months: list[str]
    currencies: list[RelationshipCurrency]
    methodology_version: Literal["relationships-v1"] = "relationships-v1"
    minimum_observations: int = MIN_MONTHS
    coverage_note: str = (
        "Associations in finalized imported activity, not causes or predictions. "
        "Partial months, overlapping imports, shared arithmetic and changing income can "
        "influence patterns. Missing months stay missing; currencies are never combined."
    )


def correlation(points: list[Pair]) -> Decimal | None:
    """Centered Pearson correlation; Decimal values, no financial float conversion."""
    if len(points) < 2:
        return None
    with localcontext() as context:
        context.prec = 60
        x = [Decimal(p.x) for p in points]
        y = [Decimal(p.y) for p in points]
        mx, my = sum(x, ZERO) / len(x), sum(y, ZERO) / len(y)
        dx, dy = [v - mx for v in x], [v - my for v in y]
        xx, yy = sum((v * v for v in dx), ZERO), sum((v * v for v in dy), ZERO)
        if not xx or not yy:
            return None
        numerator = sum((a * b for a, b in zip(dx, dy, strict=True)), ZERO)
        return max(Decimal(-1), min(Decimal(1), numerator / (xx * yy).sqrt()))


def stable_direction(points: list[Pair]) -> Literal["together", "opposite", "not_clear"]:
    if len(points) < MIN_MONTHS:
        return "not_clear"
    coefficient = correlation(points)
    if coefficient is None or abs(coefficient) < STRONG:
        return "not_clear"
    sign = Decimal(1) if coefficient > 0 else Decimal(-1)
    for index in range(len(points)):
        reduced = correlation(points[:index] + points[index + 1 :])
        if reduced is None or reduced * sign < STABLE:
            return "not_clear"
    return "together" if coefficient > 0 else "opposite"


def assess(
    code: str, x_label: str, y_label: str, points: list[Pair], caveat: str
) -> tuple[Screening, Relationship | None]:
    screening = Screening(code=code, sample_count=len(points), state="insufficient_history")
    if len(points) < MIN_MONTHS:
        return screening, None
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        midpoint = median([Decimal(p.x) for p in points])
        higher = [p for p in points if Decimal(p.x) > midpoint]
        other = [p for p in points if Decimal(p.x) <= midpoint]
        coefficient = correlation(points)
        if coefficient is None or min(len(higher), len(other)) < 3:
            screening.state = "limited_variation"
            return screening, None
        direction = stable_direction(points)
        if direction == "not_clear":
            screening.state = "not_clear"
            return screening, None
        screening.state = "supported"

        def group(values: list[Pair]) -> Group:
            return Group(
                months=[p.month for p in values],
                x_mean=money(sum((Decimal(p.x) for p in values), ZERO) / len(values)),
                y_mean=money(sum((Decimal(p.y) for p in values), ZERO) / len(values)),
            )

        upper, lower = group(higher), group(other)
        # Avoid contradictory copy if an unusual distribution reverses the group comparison.
        delta = Decimal(upper.y_mean) - Decimal(lower.y_mean)
        if delta == 0 or (delta > 0) != (direction == "together"):
            screening.state = "not_clear"
            return screening, None
        evolution = None
        if len(points) >= 12:
            earlier, recent = points[:-6], points[-6:]
            evolution = Evolution(
                earlier_months=[p.month for p in earlier],
                recent_months=[p.month for p in recent],
                earlier_direction=stable_direction(earlier),
                recent_direction=stable_direction(recent),
            )
        return screening, Relationship(
            code=code,
            x_label=x_label,
            y_label=y_label,
            direction=direction,
            interpretation=f"Higher {x_label.lower()} tended to coincide with "
            f"{'higher' if direction == 'together' else 'lower'} {y_label.lower()}.",
            caveat=caveat,
            months=[p.month for p in points],
            sample_count=len(points),
            coefficient=format(coefficient, ".3f"),
            median_x=money(midpoint),
            higher=upper,
            other=lower,
            points=points,
            evolution=evolution,
        )


def evaluate_relationships(
    rows: list[Observation], selected: date, currency: str
) -> RelationshipCurrency:
    start = shift_month(selected, -12)
    # Fact identifiers are counted once; joins or overlapping views cannot multiply them.
    unique = {
        r.identifier: r
        for r in rows
        if r.currency == currency
        and shift_month(start, -2) <= r.day
        and month_name(r.day) <= month_name(selected)
    }
    rows = sorted(unique.values(), key=lambda r: (r.day, r.identifier))
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        grouped: dict[str, list[Observation]] = defaultdict(list)
        for row in rows:
            if row.day >= start:
                grouped[month_name(row.day)].append(row)
        buckets: dict[str, Bucket] = {}
        weekends: dict[str, str] = {}
        commitments: dict[str, str] = {}
        for month, monthly in sorted(grouped.items()):
            bucket = Bucket()
            for row in monthly:
                bucket.add(
                    Activity(
                        month, currency, row.category, row.merchant, row.amount, 1, row.day, row.day
                    )
                )
            buckets[month] = bucket
            day = date.fromisoformat(month + "-01")
            weekends[month] = behaviour(monthly, day).weekday_weekend[1].amount
            patterns = recurring(rows, day)
            if patterns.state == "likely_recurring":
                commitments[month] = patterns.monthly_estimate

        points: dict[str, list[Pair]] = defaultdict(list)
        for month, bucket in buckets.items():
            points["spending_net"].append(
                Pair(month=month, x=money(bucket.spending), y=money(bucket.net))
            )
            points["weekend_outflow"].append(
                Pair(month=month, x=weekends[month], y=money(bucket.outflow))
            )
            points["cash_spending"].append(
                Pair(month=month, x=money(bucket.cash_out), y=money(bucket.spending))
            )
            if month in commitments:
                points["recurring_net"].append(
                    Pair(month=month, x=commitments[month], y=money(bucket.net))
                )
            previous = month_name(shift_month(date.fromisoformat(month + "-01"), -1))
            if previous in buckets and previous != month:
                before = buckets[previous]
                change = (
                    bucket.categories.get("Food & Dining", (ZERO, 0))[0]
                    - before.categories.get("Food & Dining", (ZERO, 0))[0]
                )
                points["dining_change_net"].append(
                    Pair(
                        month=month,
                        previous_month=previous,
                        x=money(change),
                        y=money(bucket.net - before.net),
                    )
                )

        definitions = [
            (
                "spending_net",
                "Monthly spending",
                "Net cash flow",
                "Spending is part of outflow, which is subtracted in net cash flow. "
                "This arithmetic overlap can explain the association; income also matters.",
            ),
            (
                "weekend_outflow",
                "Weekend spending",
                "Monthly outflow",
                "Weekend means Saturday/Sunday. Weekend spending is part of outflow, "
                "so these dimensions are not independent.",
            ),
            (
                "cash_spending",
                "Cash withdrawals",
                "Monthly spending",
                "Cash / ATM is excluded from spending. Withdrawals do not reveal "
                "where cash was spent; partial statement coverage can influence both totals.",
            ),
            (
                "recurring_net",
                "Likely recurring monthly amount",
                "Net cash flow",
                "Estimated patterns are not contracts or available balances. Only months with "
                "qualified patterns are compared; missing qualification is not zero. "
                "The set of qualifying merchants may change, "
                "and their charges contribute to outflow.",
            ),
            (
                "dining_change_net",
                "Food & Dining change",
                "Net cash-flow change",
                "Each point compares adjacent observed calendar months using absolute changes. "
                "Gaps are not bridged. Dining contributes to outflow; shared arithmetic and "
                "overlapping month pairs limit interpretation.",
            ),
        ]
        screenings: list[Screening] = []
        items: list[Relationship] = []
        for code, x_label, y_label, caveat in definitions:
            screening, item = assess(code, x_label, y_label, points[code], caveat)
            screenings.append(screening)
            if item:
                items.append(item)
        items.sort(
            key=lambda item: (-abs(Decimal(item.coefficient)), -item.sample_count, item.code)
        )
        months = sorted(buckets)
        expected = sorted({month_name(shift_month(selected, -i)) for i in range(13)})
        return RelationshipCurrency(
            currency=currency,
            observed_months=months,
            missing_months=[m for m in expected if m not in buckets],
            items=items,
            screening=screenings,
            state="no_activity"
            if not months
            else "insufficient_history"
            if len(months) < MIN_MONTHS
            else "available"
            if items
            else "no_clear_relationship",
        )


def relationships(db: Session, principal: Principal, month: str | None) -> RelationshipsReport:
    # Two additional warm-up months support the existing recurring detector.
    selected, available, observations = load_history(db, principal, month, history_months=14)
    day = date.fromisoformat(selected + "-01") if selected else None
    return RelationshipsReport(
        month=selected,
        available_months=available,
        window_start=month_name(shift_month(day, -12)) if day else None,
        currencies=[
            evaluate_relationships(rows, day, currency)
            for currency, rows in sorted(observations.items())
        ]
        if day
        else [],
    )
