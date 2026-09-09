from datetime import date
from decimal import Decimal, localcontext

import pytest

from ledgerx.modules.analytics.baselines import baselines
from ledgerx.modules.analytics.intelligence import Observation, behaviour
from ledgerx.modules.analytics.recurring import recurring


def observation(
    amount: str,
    day: str = "2026-09-05",
    category: str = "Groceries",
    merchant: str | None = "Carrefour",
    returned: bool = False,
) -> Observation:
    return Observation(
        f"synthetic-{merchant}-{day}-{amount}",
        date.fromisoformat(day),
        "AED",
        category,
        merchant,
        Decimal(amount),
        returned,
    )


def test_behaviour_exact_exclusions_patterns_and_return_evidence() -> None:
    rows = [
        observation("-12.3456"),
        observation("-20", "2026-09-21"),
        observation("-100", category="Transfers"),
        observation("-50", category="Cash / ATM"),
        observation("25", returned=True),
        observation("10", category="Transfers"),
        observation("90", category="Other"),
        observation("-10", "2026-08-05"),
    ]
    with localcontext() as context:
        context.prec = 8
        result = behaviour(rows, date(2026, 9, 1))
        assert context.prec == 8
    assert result.spending_count == 2
    assert result.average_purchase == "16.1728"
    assert result.return_inflows == "25.0000"
    assert result.transfer_inflows == "10.0000"
    assert result.active_spending_days == 2
    assert [row.amount for row in result.weekday_weekend] == ["20.0000", "12.3456"]
    assert [row.amount for row in result.month_parts] == ["12.3456", "0.0000", "20.0000"]
    assert result.top_five_merchant_share == "100.00"
    assert result.merchant_changes[0].delta == "22.3456"
    assert result.newly_observed_merchants == []
    assert result.largest_purchases[0].amount == "20.0000"


def test_empty_history_and_unknown_merchants_never_invent_novelty() -> None:
    result = behaviour([observation("-5", merchant=None)], date(2026, 9, 1))
    assert result.newly_observed_merchants == []
    assert result.merchant_changes == []
    assert result.top_spending_merchants[0].name is None
    empty = behaviour([], date(2026, 9, 1))
    assert empty.average_purchase is None and empty.top_five_category_share is None
    assert empty.largest_purchases == []


def test_merchant_change_ranking_and_window_novelty_are_deterministic() -> None:
    rows = [
        observation("-20", merchant="B"),
        observation("-20", merchant="A"),
        observation("-5", "2026-08-05", merchant="C"),
    ]
    result = behaviour(rows, date(2026, 9, 1))
    assert [r.name for r in result.merchant_changes] == ["A", "B", "C"]
    assert [r.name for r in result.newly_observed_merchants] == ["A", "B"]
    assert behaviour(list(reversed(rows)), date(2026, 9, 1)) == result


def test_baseline_excludes_selected_month_and_calculates_three_six_and_range() -> None:
    rows = [observation(str(-month * 10), f"2026-{month:02d}-05") for month in range(3, 9)]
    rows.append(observation("-900"))
    report = baselines(rows, date(2026, 9, 1))
    result = report.metrics[0]
    assert result.state == "available" and result.position == "above"
    assert result.mean == "55.0000"
    assert (result.low, result.high) == ("30.0000", "80.0000")
    assert result.average_three == "70.0000" and result.average_six == "55.0000"
    assert result.delta == "845.0000"
    assert result.months == [f"2026-{month:02d}" for month in range(3, 9)]
    assert report.observed_months == 7
    assert report.categories[0].state == "available"
    assert Decimal(result.current_scale or "0") > Decimal(result.high_scale or "0")


def test_baseline_gap_breaks_run_and_new_category_has_no_fake_zero_normal() -> None:
    rows = [observation("-100", f"2026-{month:02d}-05") for month in (3, 4, 5, 7, 8, 9)]
    report = baselines(rows, date(2026, 9, 1))
    assert report.prior_months == ["2026-07", "2026-08"]
    assert report.metrics[0].mean is None
    rows.append(observation("-100", "2026-06-05"))
    rows.append(observation("-500", category="Housing"))
    report = baselines(rows, date(2026, 9, 1))
    housing = next(row for row in report.categories if row.name == "Housing")
    assert housing.state == "insufficient_history" and housing.mean is None
    assert report.metrics[0].mean == "100.0000"


@pytest.mark.parametrize(
    "current,position", [("-50", "below"), ("-100", "within"), ("-101", "above")]
)
def test_baseline_range_boundaries(current: str, position: str) -> None:
    rows = [observation("-100", f"2026-{month:02d}-05") for month in (6, 7, 8)]
    rows.append(observation(current))
    result = baselines(rows, date(2026, 9, 1)).metrics[0]
    assert result.position == position
    assert result.average_six is None


def test_baseline_zero_missing_current_and_rounding_are_explicit() -> None:
    rows = [observation("100", f"2026-{month:02d}-05", category="Income") for month in (6, 7, 8, 9)]
    result = baselines(rows, date(2026, 9, 1)).metrics[0]
    assert result.mean == "0.0000" and result.relative_percent is None
    assert result.current_scale == "0.00" and result.position == "within"
    missing = baselines(rows[:-1], date(2026, 9, 1)).metrics[0]
    assert missing.state == "no_activity" and missing.current is None and missing.delta is None
    tiny = [
        observation(value, f"2026-{month:02d}-05")
        for month, value in [(5, "-0.0001"), (6, "-0.0001"), (7, "1"), (8, "1"), (9, "-0.0001")]
    ]
    with localcontext() as context:
        context.prec = 8
        result = baselines(tiny, date(2026, 9, 1)).metrics[0]
        assert context.prec == 8
    assert result.mean == "0.0000"
    assert result.delta == "0.0001"


def test_recurring_exact_median_tolerance_annualization_and_actual_composition() -> None:
    rows = [
        observation(amount, day, merchant="Netflix")
        for amount, day in [("-95", "2026-07-05"), ("-100", "2026-08-05"), ("-105", "2026-09-05")]
    ]
    rows += [
        observation("-20", category="Other", merchant=None),
        observation("-900", category="Transfers"),
        observation("-500", category="Cash / ATM"),
    ]
    result = recurring(rows, date(2026, 9, 1))
    assert result.state == "likely_recurring"
    assert result.monthly_estimate == "100.0000" and result.annual_estimate == "1200.0000"
    assert result.matched_spending == "105.0000" and result.other_spending == "20.0000"
    assert result.payments[0].newly_qualified is None
    assert len(result.payments[0].evidence) == 3
    assert recurring(list(reversed(rows)), date(2026, 9, 1)) == result


@pytest.mark.parametrize(
    "days,amounts,reason",
    [
        (["2026-07-05", "2026-08-05", "2026-09-05"], ["-94.99", "-100", "-105"], "amounts_vary"),
        (["2026-07-30", "2026-08-01", "2026-09-01"], ["-100"] * 3, "timing_not_regular"),
        (["2026-06-05", "2026-08-05", "2026-09-05"], ["-100"] * 3, "fewer_than_three_months"),
    ],
)
def test_recurring_rejects_weak_patterns(days: list[str], amounts: list[str], reason: str) -> None:
    rows = [
        observation(amount, day, merchant="Netflix")
        for day, amount in zip(days, amounts, strict=True)
    ]
    result = recurring(rows, date(2026, 9, 1))
    assert result.payments == [] and result.monthly_estimate == "0.0000"
    assert result.candidates[0].reason == reason


def test_recurring_duplicate_month_exclusions_and_newly_qualified() -> None:
    rows = [observation("-49", f"2026-{month:02d}-05", merchant="Netflix") for month in (7, 8, 9)]
    context = [observation("1000", "2026-06-01", category="Income")]
    assert recurring(rows + context, date(2026, 9, 1)).payments[0].newly_qualified is True
    four = rows + [observation("-49", "2026-06-05", merchant="Netflix")]
    assert recurring(four, date(2026, 9, 1)).payments[0].newly_qualified is False
    doubled = recurring(
        rows + [observation("-49", "2026-08-06", merchant="Netflix")], date(2026, 9, 1)
    )
    assert doubled.payments == [] and doubled.candidates[0].reason == "multiple_charges"
    for category in ("Transfers", "Cash / ATM"):
        excluded = [
            observation("-49", f"2026-{month:02d}-05", category=category, merchant="Netflix")
            for month in (7, 8, 9)
        ]
        assert recurring(excluded, date(2026, 9, 1)).payments == []
    returned = [observation("-49", f"2026-{month:02d}-05", returned=True) for month in (7, 8, 9)]
    assert recurring(returned, date(2026, 9, 1)).payments == []
    assert recurring(rows, date(2026, 10, 1)).state == "no_activity"


def test_earliest_year_never_duplicates_history_or_recurring_evidence() -> None:
    rows = [observation("-10", "0001-01-05")]
    assert baselines(rows, date(1, 1, 1)).prior_months == []
    assert recurring(rows, date(1, 1, 1)).payments == []
