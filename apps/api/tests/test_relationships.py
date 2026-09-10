"""Synthetic descriptive relationships and their limits."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from ledgerx.modules.analytics.calculations import month_name, shift_month
from ledgerx.modules.analytics.intelligence import Observation
from ledgerx.modules.analytics.relationships import (
    Pair,
    assess,
    correlation,
    evaluate_relationships,
)

SELECTED = date(2026, 9, 1)


def history(count: int = 13, currency: str = "AED") -> list[Observation]:
    rows = []
    for index in range(count):
        month = shift_month(SELECTED, index - count + 1)
        weekend = month + timedelta(days=(5 - month.weekday()) % 7)
        values = [
            (month, "Income", "Salary", Decimal(10000)),
            (weekend, "Food & Dining", "Dining", -Decimal((index + 1) ** 2 * 10)),
            (month, "Cash / ATM", "ATM", -Decimal((index + 1) * 20)),
            (month.replace(day=5), "Entertainment", "Streaming", -Decimal(50 + index)),
        ]
        for j, (day, category, merchant, value) in enumerate(values):
            rows.append(
                Observation(
                    str(UUID(int=(index + 1) * 10 + j)), day, currency, category, merchant, value
                )
            )
    return rows


def pairs(x: list[int], y: list[int]) -> list[Pair]:
    return [
        Pair(month=f"2026-{i + 1:02d}", x=str(a), y=str(b))
        for i, (a, b) in enumerate(zip(x, y, strict=True))
    ]


def test_correct_pearson_groups_direction_and_no_causal_claims() -> None:
    data = pairs([1, 2, 3, 4, 5, 6], [12, 10, 8, 6, 4, 2])
    assert correlation(data) == -1
    screening, item = assess("test", "Spending", "Net cash flow", data, "Shared arithmetic.")
    assert screening.state == "supported" and item is not None
    assert item.direction == "opposite" and item.sample_count == 6
    assert item.higher.y_mean == "4.0000" and item.other.y_mean == "10.0000"
    assert item.median_x == "3.5000"
    assert item.higher.months == ["2026-04", "2026-05", "2026-06"]
    assert "tended to coincide with" in item.interpretation
    assert "caus" not in item.interpretation.lower()
    assert correlation(pairs([1, 2, 3], [2, 4, 6])) == 1
    assert correlation(pairs([1, 1, 1], [2, 4, 6])) is None


def test_minimum_history_constant_and_outlier_driven_patterns_are_not_surfaced() -> None:
    assert (
        assess("x", "X", "Y", pairs([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]), "")[0].state
        == "insufficient_history"
    )
    assert (
        assess("x", "X", "Y", pairs([0, 0, 0, 0, 0, 9], [1, 2, 3, 4, 5, 9]), "")[0].state
        == "limited_variation"
    )
    data = pairs([1, 2, 3, 4, 5, 100], [4, 2, 5, 1, 3, 100])
    value = correlation(data)
    assert value is not None and value > Decimal("0.9")
    assert assess("x", "X", "Y", data, "")[1] is None
    result = evaluate_relationships(history(5), SELECTED, "AED")
    assert result.state == "insufficient_history" and not result.items


def test_all_five_focused_relationships_reuse_exact_monthly_values() -> None:
    result = evaluate_relationships(history(), SELECTED, "AED")
    items = {i.code: i for i in result.items}
    assert set(items) == {
        "spending_net",
        "weekend_outflow",
        "cash_spending",
        "recurring_net",
        "dining_change_net",
    }
    assert items["spending_net"].points[-1].x == "1752.0000"
    assert items["spending_net"].points[-1].y == "7988.0000"
    assert items["cash_spending"].points[-1].x == "260.0000"
    assert items["dining_change_net"].sample_count == 12
    assert items["recurring_net"].sample_count == 11
    assert items["spending_net"].evolution is not None
    assert items["spending_net"].evolution.recent_direction == "opposite"
    assert all("caus" not in i.interpretation.lower() for i in items.values())


def test_missing_months_are_not_zero_and_changes_never_bridge_gaps() -> None:
    rows = [r for r in history() if month_name(r.day) != "2026-03"]
    result = evaluate_relationships(rows, SELECTED, "AED")
    assert "2026-03" in result.missing_months
    item = next(i for i in result.items if i.code == "spending_net")
    assert item.sample_count == 12 and "2026-03" not in item.months
    changes = next(i for i in result.items if i.code == "dining_change_net")
    assert changes.sample_count == 10
    assert "2026-04" not in changes.months
    # Missing qualification is not a zero recurring commitment.
    recurring = next(s for s in result.screening if s.code == "recurring_net")
    assert recurring.sample_count == 8


def test_currency_isolation_duplicate_fact_ids_and_window_boundaries() -> None:
    own = history()
    foreign = [replace(r, currency="USD", amount=r.amount * 1000) for r in own]
    expected = evaluate_relationships(own, SELECTED, "AED")
    assert evaluate_relationships(own + foreign + own, SELECTED, "AED") == expected
    assert evaluate_relationships(own, SELECTED, "USD").state == "no_activity"
    future = replace(own[-1], identifier="future", day=date(2026, 10, 1), amount=Decimal(-9999))
    assert evaluate_relationships(own + [future], SELECTED, "AED") == expected
    for end in (date(1, 1, 1), date(9999, 12, 1)):
        assert evaluate_relationships([], end, "AED").state == "no_activity"


def test_no_clear_relationship_for_constant_months_and_insufficient_evolution() -> None:
    rows = [replace(r, amount=Decimal(1000) if r.amount > 0 else Decimal(-10)) for r in history(6)]
    result = evaluate_relationships(rows, SELECTED, "AED")
    assert result.state == "no_clear_relationship" and not result.items
    result = evaluate_relationships(history(6), SELECTED, "AED")
    assert result.items and all(i.evolution is None for i in result.items)


def test_earlier_and_recent_relationship_directions_can_differ() -> None:
    data = pairs(list(range(1, 13)), [1, 2, 3, 4, 5, 6, 20, 19, 18, 17, 16, 15])
    _, item = assess("test", "X", "Y", data, "Descriptive split only.")
    assert item is not None and item.evolution is not None
    assert item.evolution.earlier_direction == "together"
    assert item.evolution.recent_direction == "opposite"
    assert len(item.evolution.earlier_months) == len(item.evolution.recent_months) == 6
