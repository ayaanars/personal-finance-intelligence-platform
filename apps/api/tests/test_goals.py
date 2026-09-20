from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ledgerx.modules.analytics.intelligence import Observation
from ledgerx.modules.goals.forecast import forecast, goal_status
from ledgerx.modules.goals.service import GoalInput


def row(
    day: str,
    amount: str,
    merchant: str | None = None,
    currency: str = "AED",
    category: str = "Other",
) -> Observation:
    return Observation(
        day + amount + str(merchant),
        date.fromisoformat(day),
        currency,
        category,
        merchant,
        Decimal(amount),
    )


def test_pace_fallback_currency_and_duplicates() -> None:
    a = row("2026-09-02", "-150")
    result = forecast(
        [a, a, row("2026-09-03", "-900", currency="USD"), row("2026-09-25", "-900")],
        date(2026, 9, 1),
        date(2026, 9, 15),
        "AED",
    )
    assert result.actual_spending == "150.0000"
    assert result.projected_spending == "300.0000"
    assert result.projected_net_cash_flow == "-300.0000"
    assert result.quality == "Early estimate"
    assert result.history_months == 0
    assert "current pace only" in result.explanation


def test_recurring_remaining_observed_and_overdue() -> None:
    history = [row(f"2026-{m:02d}-20", "-100", "Netflix") for m in (6, 7, 8)]
    current = row("2026-09-02", "-150")
    result = forecast(history + [current], date(2026, 9, 1), date(2026, 9, 15), "AED")
    assert result.remaining_recurring == "100.0000"
    assert result.projected_spending == "400.0000"
    paid = forecast(
        history + [current, row("2026-09-14", "-100", "Netflix")],
        date(2026, 9, 1),
        date(2026, 9, 15),
        "AED",
    )
    assert paid.remaining_recurring == "0.0000"
    assert paid.projected_spending == "400.0000"
    assert paid.commitments[0].state == "observed"
    overdue = forecast(history + [current], date(2026, 9, 1), date(2026, 9, 21), "AED")
    assert overdue.remaining_recurring == "0.0000"
    assert overdue.commitments[0].state == "overdue"
    insufficient = forecast(history[1:] + [current], date(2026, 9, 1), date(2026, 9, 15), "AED")
    assert insufficient.commitments == []


def test_history_blend_quality_and_outflow_semantics() -> None:
    rows = [row(f"2026-{m:02d}-{d:02d}", "-150") for m in (6, 7, 8) for d in (1, 25)]
    rows += [
        row("2026-09-01", "1000", category="Income"),
        row("2026-09-02", "-100"),
        row("2026-09-03", "-50", category="Transfers"),
    ]
    result = forecast(rows, date(2026, 9, 1), date(2026, 9, 21), "AED")
    assert result.history_months == 3
    assert result.quality == "Early estimate"
    fresh = forecast(rows + [row("2026-09-21", "-1")], date(2026, 9, 1), date(2026, 9, 21), "AED")
    assert fresh.quality == "Stronger estimate"
    assert result.actual_spending == "100.0000"
    assert result.actual_outflow == "150.0000"
    assert result.actual_net_cash_flow == "850.0000"
    expected = (
        Decimal(100)
        + ((Decimal(100) / 21 + (Decimal(300) / 30 + Decimal(300) / 31 * 2) / 3) / 2) * 9
    )
    assert result.projected_spending == format(expected, ".4f")
    early = forecast(rows, date(2026, 9, 1), date(2026, 9, 5), "AED")
    assert early.quality == "Early estimate"
    developing = forecast(
        rows + [row("2026-09-10", "-1")], date(2026, 9, 1), date(2026, 9, 10), "AED"
    )
    assert developing.quality == "Developing estimate"


def test_selected_month_past_future_empty_and_leap_year() -> None:
    rows = [row("2024-02-02", "-29"), row("2024-03-02", "-900")]
    past = forecast(rows, date(2024, 2, 1), date(2026, 9, 15), "AED")
    assert past.projected_spending == "29.0000" and past.days_in_month == 29
    assert past.state == "historical"
    future = forecast(rows, date(2026, 10, 1), date(2026, 9, 15), "AED")
    assert future.projected_spending is None and future.elapsed_days == 0
    empty = forecast([], date(2026, 9, 1), date(2026, 9, 15), "AED")
    assert empty.state == "unavailable" and empty.projected_spending is None


def test_stable_income_does_not_predict_a_second_salary() -> None:
    rows = [row(f"2026-{m:02d}-01", "9000", category="Income") for m in (6, 7, 8)]
    rows += [row(f"2026-{m:02d}-25", "-300") for m in (6, 7, 8)]
    rows += [row("2026-09-01", "9000", category="Income"), row("2026-09-15", "-150")]
    result = forecast(rows, date(2026, 9, 1), date(2026, 9, 15), "AED")
    assert Decimal(result.projected_net_cash_flow or "0") + Decimal(
        result.projected_outflow or "0"
    ) == Decimal(9000)
    assert "less income already observed" in result.explanation
    # An unpaid stable pattern can contribute the outstanding amount, once.
    unpaid = forecast(rows[:-2] + rows[-1:], date(2026, 9, 1), date(2026, 9, 15), "AED")
    assert unpaid.projected_net_cash_flow == result.projected_net_cash_flow
    # No income is promised after the selected month has ended.
    past = forecast(rows[:-2] + rows[-1:], date(2026, 9, 1), date(2026, 10, 1), "AED")
    assert past.projected_net_cash_flow == "-150.0000"


@pytest.mark.parametrize(
    "kind,actual,projection,status",
    [
        ("spending", "40", "90", "On track"),
        ("spending", "40", "110", "Watch closely"),
        ("spending", "60", "110", "Off track"),
        ("spending", "101", "90", "Off track"),
        ("net_cash_flow", "60", "110", "On track"),
        ("net_cash_flow", "40", "110", "Watch closely"),
        ("net_cash_flow", "40", "90", "Off track"),
        ("net_cash_flow", "50", "100", "On track"),
    ],
)
def test_status(kind: str, actual: str, projection: str, status: str) -> None:
    assert goal_status(kind, Decimal(100), Decimal(actual), Decimal(projection), 15, 30) == status
    assert goal_status(kind, Decimal(100), Decimal(0), None, 15, 30) == "Awaiting activity"


@pytest.mark.parametrize("target", ["0", "-1", "NaN", "Infinity", "1.00001", 1.5])
def test_target_validation(target: object) -> None:
    with pytest.raises(ValidationError):
        GoalInput.model_validate(
            dict(month="2026-09", currency="AED", kind="spending", target=target, active=True)
        )
