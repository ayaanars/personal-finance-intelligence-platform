"""Pure deterministic arithmetic. No I/O, float money, or inferred missing periods."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from ledgerx.modules.analytics.schemas import (
    Breakdown,
    Change,
    Comparison,
    CurrencyOverview,
    Insight,
    Totals,
    TrendPoint,
)

ZERO = Decimal(0)


def shift_month(month: date, offset: int) -> date:
    index = (month.year - 1) * 12 + month.month - 1 + offset
    index = max(0, min(index, 9999 * 12 - 1))
    return date(index // 12 + 1, index % 12 + 1, 1)


def month_name(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def money(value: Decimal) -> str:
    return format(value if value else ZERO, ".4f")


def prose_money(value: Decimal) -> str:
    whole, fraction = money(value).split(".")
    return f"{int(whole):,}.{fraction.rstrip('0').ljust(2, '0')}"


def percent(numerator: Decimal, denominator: Decimal) -> str | None:
    if not denominator:
        return None
    return format(
        (numerator / denominator * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), ".2f"
    )


@dataclass(frozen=True)
class Activity:
    month: str
    currency: str
    category: str
    merchant: str | None
    amount: Decimal
    count: int
    first: date
    last: date


@dataclass
class Bucket:
    inflows: Decimal = ZERO
    income: Decimal = ZERO
    outflow: Decimal = ZERO
    transfers_out: Decimal = ZERO
    cash_out: Decimal = ZERO
    count: int = 0
    categories: dict[str, tuple[Decimal, int]] = field(default_factory=dict)
    merchants: dict[str | None, tuple[Decimal, int]] = field(default_factory=dict)
    first: date | None = None
    last: date | None = None

    @property
    def spending(self) -> Decimal:
        return sum((value[0] for value in self.categories.values()), ZERO)

    @property
    def net(self) -> Decimal:
        return self.inflows - self.outflow

    def add(self, row: Activity) -> None:
        self.count += row.count
        self.first = min(self.first, row.first) if self.first else row.first
        self.last = max(self.last, row.last) if self.last else row.last
        if row.amount > 0:
            self.inflows += row.amount
            if row.category == "Income":
                self.income += row.amount
            return
        amount = -row.amount
        self.outflow += amount
        previous, count = self.merchants.get(row.merchant, (ZERO, 0))
        self.merchants[row.merchant] = (previous + amount, count + row.count)
        if row.category == "Transfers":
            self.transfers_out += amount
        elif row.category == "Cash / ATM":
            self.cash_out += amount
        else:
            category = "Other" if row.category == "Income" else row.category
            previous, count = self.categories.get(category, (ZERO, 0))
            self.categories[category] = (previous + amount, count + row.count)

    def totals(self) -> Totals:
        return Totals(
            inflows=money(self.inflows),
            income=money(self.income),
            other_inflows=money(self.inflows - self.income),
            outflow=money(self.outflow),
            net_cash_flow=money(self.net),
            spending=money(self.spending),
            transfers_out=money(self.transfers_out),
            cash_out=money(self.cash_out),
            transaction_count=self.count,
        )


def change(name: str, current: Decimal, previous: Decimal) -> Change:
    return Change(
        name=name,
        current=money(current),
        previous=money(previous),
        delta=money(current - previous),
        percent=None if name == "net_cash_flow" else percent(current - previous, previous),
    )


def changes(current: Bucket, previous: Bucket, previous_month: str) -> Comparison:
    state = (
        "available"
        if current.count and previous.count
        else ("no_activity" if not current.count else "insufficient_history")
    )
    metrics: list[Change] = []
    categories: list[Change] = []
    if state == "available":
        metrics = [
            change(name, a, b)
            for name, a, b in (
                ("income", current.income, previous.income),
                ("outflow", current.outflow, previous.outflow),
                ("net_cash_flow", current.net, previous.net),
                ("spending", current.spending, previous.spending),
            )
        ]
        categories = [
            change(
                name,
                current.categories.get(name, (ZERO, 0))[0],
                previous.categories.get(name, (ZERO, 0))[0],
            )
            for name in sorted(current.categories.keys() | previous.categories.keys())
        ]
        categories.sort(key=lambda row: (-abs(Decimal(row.delta)), row.name))
        maximum = max((abs(Decimal(row.delta)) for row in categories), default=ZERO)
        for row in categories:
            row.scale_percent = percent(abs(Decimal(row.delta)), maximum) or "0.00"
    return Comparison(
        state=state, previous_month=previous_month, metrics=metrics, categories=categories
    )


def explanations(
    current: Bucket, previous: Bucket, comparison: Comparison, currency: str
) -> list[Insight]:
    if comparison.state != "available":
        return []
    result: list[Insight] = []
    for row in comparison.metrics[:3]:
        if row.name == "income" or Decimal(row.delta) == 0:
            continue
        delta = Decimal(row.delta)
        label = "Outflow" if row.name == "outflow" else "Net cash flow"
        direction = (
            ("increased" if delta > 0 else "decreased")
            if row.name == "outflow"
            else ("improved" if delta > 0 else "worsened")
        )
        result.append(
            Insight(
                code=f"{row.name}_change",
                metric=row.name,
                subject=None,
                text=(
                    f"{label} {direction} by {currency} {prose_money(abs(delta))} "
                    f"compared with {comparison.previous_month}."
                ),
                current=row.current,
                previous=row.previous,
                delta=row.delta,
            )
        )
    # Category and merchant insights are separate views of activity, never added together.
    for kind, candidates, total_delta in (
        ("category", comparison.categories, current.spending - previous.spending),
        (
            "merchant",
            [
                change(
                    name or "Unknown merchant",
                    current.merchants.get(name, (ZERO, 0))[0],
                    previous.merchants.get(name, (ZERO, 0))[0],
                )
                for name in current.merchants.keys() | previous.merchants.keys()
            ],
            current.outflow - previous.outflow,
        ),
    ):
        nonzero = [row for row in candidates if Decimal(row.delta)]
        if not nonzero:
            continue
        # Prefer a contributor in the total's direction; otherwise describe the largest offset.
        aligned = [row for row in nonzero if Decimal(row.delta) * total_delta > 0]
        row = sorted(aligned or nonzero, key=lambda item: (-abs(Decimal(item.delta)), item.name))[0]
        delta = Decimal(row.delta)
        contribution = percent(delta, total_delta) if delta * total_delta > 0 else None
        supported = bool(total_delta and Decimal("0.5") < delta / total_delta <= 1)
        label = "spending" if kind == "category" else "outflow"
        direction = "increased" if delta > 0 else "decreased"
        text = f"{row.name} {label} {direction} by {currency} {prose_money(abs(delta))}."
        if supported:
            direction_label = "increase" if total_delta > 0 else "decrease"
            text += f" It accounted for {contribution}% of the {label} {direction_label}."
        result.append(
            Insight(
                code=f"{kind}_change",
                metric=label,
                subject=row.name,
                text=text,
                current=row.current,
                previous=row.previous,
                delta=row.delta,
                total_delta=money(total_delta),
                contribution_percent=contribution,
            )
        )
    return result


def build_currencies(rows: Iterable[Activity], selected: date) -> list[CurrencyOverview]:
    with localcontext() as context:
        context.prec = 60
        buckets: dict[tuple[str, str], Bucket] = {}
        for row in rows:
            buckets.setdefault((row.currency, row.month), Bucket()).add(row)
        output = []
        selected_month = month_name(selected)
        prior = month_name(shift_month(selected, -1))
        for currency in sorted({key[0] for key in buckets}):
            current = buckets.get((currency, selected_month), Bucket())
            previous = (
                buckets.get((currency, prior), Bucket()) if prior != selected_month else Bucket()
            )
            comparison = changes(current, previous, prior)
            history = sorted(
                (month, bucket) for (code, month), bucket in buckets.items() if code == currency
            )
            maximum = max((bucket.spending for _, bucket in history), default=ZERO)
            income_max = max((bucket.income for _, bucket in history), default=ZERO)
            outflow_max = max((bucket.outflow for _, bucket in history), default=ZERO)
            output.append(
                CurrencyOverview(
                    currency=currency,
                    totals=current.totals(),
                    categories=[
                        Breakdown(
                            name=name,
                            amount=money(amount),
                            transaction_count=count,
                            share_percent=percent(amount, current.spending),
                        )
                        for name, (amount, count) in sorted(
                            current.categories.items(), key=lambda item: (-item[1][0], item[0])
                        )
                    ],
                    top_merchants=[
                        Breakdown(
                            name=name,
                            amount=money(amount),
                            transaction_count=count,
                            share_percent=percent(amount, current.outflow),
                        )
                        for name, (amount, count) in sorted(
                            current.merchants.items(), key=lambda item: (-item[1][0], item[0] or "")
                        )[:5]
                    ],
                    comparison=comparison,
                    insights=explanations(current, previous, comparison, currency),
                    trend=[
                        TrendPoint(
                            month=month,
                            totals=bucket.totals(),
                            spending_scale_percent=percent(bucket.spending, maximum) or "0.00",
                            income_scale_percent=percent(bucket.income, income_max) or "0.00",
                            outflow_scale_percent=percent(bucket.outflow, outflow_max) or "0.00",
                        )
                        for month, bucket in history
                    ],
                    observed_start=current.first.isoformat() if current.first else None,
                    observed_end=current.last.isoformat() if current.last else None,
                )
            )
        return output
