"""Date-level, deterministic views of imported activity; no persistence or inference of time."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from pydantic import BaseModel

from ledgerx.modules.analytics.calculations import ZERO, money, percent
from ledgerx.modules.analytics.schemas import Breakdown, Change


@dataclass(frozen=True)
class Observation:
    identifier: str
    day: date
    currency: str
    category: str
    merchant: str | None
    amount: Decimal
    return_signal: bool = False

    @property
    def spending(self) -> bool:
        return self.amount < 0 and self.category not in {"Transfers", "Cash / ATM"}


class Pattern(BaseModel):
    name: str
    amount: str
    transaction_count: int
    share_percent: str | None


class LargeTransaction(BaseModel):
    identifier: str
    day: str
    merchant: str | None
    category: str
    amount: str


class Behaviour(BaseModel):
    spending_count: int
    average_purchase: str | None
    active_spending_days: int
    weekday_weekend: list[Pattern]
    month_parts: list[Pattern]
    top_spending_merchants: list[Breakdown]
    top_five_category_share: str | None
    top_five_merchant_share: str | None
    largest_purchases: list[LargeTransaction]
    merchant_changes: list[Change]
    newly_observed_merchants: list[Breakdown]
    return_inflows: str
    transfer_inflows: str


def behaviour(rows: list[Observation], selected: date) -> Behaviour:
    """Totals describe observed dates only; weekend explicitly means Saturday/Sunday."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        current = [
            row for row in rows if (row.day.year, row.day.month) == (selected.year, selected.month)
        ]
        purchases = [row for row in current if row.spending]
        total = sum((-row.amount for row in purchases), ZERO)
        merchants: dict[str | None, Decimal] = defaultdict(Decimal)
        counts: dict[str | None, int] = defaultdict(int)
        categories: dict[str, Decimal] = defaultdict(Decimal)
        for row in purchases:
            merchants[row.merchant] -= row.amount
            counts[row.merchant] += 1
            categories[row.category] -= row.amount

        def breakdown(names: Sequence[str | None]) -> list[Breakdown]:
            return [
                Breakdown(
                    name=name,
                    amount=money(merchants[name]),
                    transaction_count=counts[name],
                    share_percent=percent(merchants[name], total),
                )
                for name in names
            ]

        ranked = sorted(merchants, key=lambda name: (-merchants[name], name or ""))
        known_before = {row.merchant for row in rows if row.day < selected and row.merchant}
        new_names = [name for name in ranked if name and name not in known_before]
        # No previous observations means there is no evidence of newly appearing activity.
        if not any(row.day < selected for row in rows):
            new_names = []

        def pattern(name: str, subset: list[Observation]) -> Pattern:
            value = sum((-row.amount for row in subset), ZERO)
            return Pattern(
                name=name,
                amount=money(value),
                transaction_count=len(subset),
                share_percent=percent(value, total),
            )

        from ledgerx.modules.analytics.calculations import change, shift_month

        prior = shift_month(selected, -1)
        previous = [row for row in rows if prior <= row.day < selected]
        before: dict[str | None, Decimal] = defaultdict(Decimal)
        for row in previous:
            if row.spending:
                before[row.merchant] -= row.amount
        changes = (
            [
                change(
                    name or "Unknown merchant", merchants.get(name, ZERO), before.get(name, ZERO)
                )
                for name in merchants.keys() | before.keys()
            ]
            if previous and current
            else []
        )
        changes.sort(key=lambda item: (-abs(Decimal(item.delta)), item.name))
        maximum = max((abs(Decimal(item.delta)) for item in changes), default=ZERO)
        for item in changes:
            item.scale_percent = percent(abs(Decimal(item.delta)), maximum) or "0.00"
        return Behaviour(
            spending_count=len(purchases),
            average_purchase=money(total / len(purchases)) if purchases else None,
            active_spending_days=len({row.day for row in purchases}),
            weekday_weekend=[
                pattern("Monday-Friday", [r for r in purchases if r.day.weekday() < 5]),
                pattern("Saturday-Sunday", [r for r in purchases if r.day.weekday() >= 5]),
            ],
            month_parts=[
                pattern(label, [r for r in purchases if lower <= r.day.day <= upper])
                for label, lower, upper in [
                    ("Days 1-10", 1, 10),
                    ("Days 11-20", 11, 20),
                    ("Days 21-31", 21, 31),
                ]
            ],
            top_spending_merchants=breakdown(ranked[:5]),
            top_five_category_share=percent(
                sum(sorted(categories.values(), reverse=True)[:5], ZERO), total
            ),
            top_five_merchant_share=percent(
                sum((merchants[name] for name in ranked[:5]), ZERO), total
            ),
            largest_purchases=[
                LargeTransaction(
                    identifier=r.identifier,
                    day=r.day.isoformat(),
                    merchant=r.merchant,
                    category=r.category,
                    amount=money(-r.amount),
                )
                for r in sorted(purchases, key=lambda r: (r.amount, r.day, r.identifier))[:5]
            ],
            merchant_changes=changes[:10],
            newly_observed_merchants=breakdown(new_names[:5]),
            return_inflows=money(
                sum((r.amount for r in current if r.amount > 0 and r.return_signal), ZERO)
            ),
            transfer_inflows=money(
                sum((r.amount for r in current if r.amount > 0 and r.category == "Transfers"), ZERO)
            ),
        )
