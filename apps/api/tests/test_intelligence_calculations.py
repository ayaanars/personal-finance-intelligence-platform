from datetime import date
from decimal import Decimal, localcontext

import pytest

from ledgerx.modules.analytics.calculations import Activity, build_currencies


def row(
    amount: str,
    category: str = "Groceries",
    month: str = "2026-09",
    currency: str = "AED",
    merchant: str | None = "Carrefour",
) -> Activity:
    day = date.fromisoformat(month + "-01")
    return Activity(month, currency, category, merchant, Decimal(amount), 1, day, day)


def test_exact_summary_transfer_cash_refunds_and_unclassified() -> None:
    result = build_currencies(
        [
            row("2000", "Income"),
            row("35.1234"),
            row("20", "Other"),
            row("-100.1234"),
            row("-200", "Transfers"),
            row("-50", "Cash / ATM"),
            row("-12", "Other", merchant=None),
            row("-10", "Income"),
        ],
        date(2026, 9, 1),
    )[0]
    assert result.totals.model_dump() == {
        "income": "2000.0000",
        "inflows": "2055.1234",
        "other_inflows": "55.1234",
        "outflow": "372.1234",
        "net_cash_flow": "1683.0000",
        "spending": "122.1234",
        "transfers_out": "200.0000",
        "cash_out": "50.0000",
        "transaction_count": 8,
    }
    assert [(item.name, item.amount) for item in result.categories] == [
        ("Groceries", "100.1234"),
        ("Other", "22.0000"),
    ]
    assert result.top_merchants[0].amount == "360.1234"
    assert result.top_merchants[0].transaction_count == 4
    assert result.top_merchants[1].name is None
    assert result.comparison.state == "insufficient_history"
    assert result.insights == []


@pytest.mark.parametrize(
    "current,delta,direction", [("-400", "300.0000", "increased"), ("-25", "-75.0000", "decreased")]
)
def test_comparisons_and_supported_explanations(current: str, delta: str, direction: str) -> None:
    data = build_currencies([row("-100", month="2026-08"), row(current)], date(2026, 9, 1))[0]
    assert data.comparison.state == "available"
    assert data.comparison.metrics[1].delta == delta
    assert direction in data.insights[0].text
    category = next(item for item in data.insights if item.code == "category_change")
    assert category.delta == category.total_delta == delta
    assert category.contribution_percent == "100.00"
    assert "accounted for 100.00%" in category.text
    assert Decimal(category.current) - Decimal(category.previous) == Decimal(category.delta)


def test_offsetting_categories_do_not_overclaim_causality() -> None:
    data = build_currencies(
        [
            row("-100", month="2026-08"),
            row("-100", "Shopping", "2026-08", merchant="Amazon"),
            row("-250"),
            row("-50", "Shopping", merchant="Amazon"),
        ],
        date(2026, 9, 1),
    )[0]
    category = next(item for item in data.insights if item.code == "category_change")
    assert category.delta == "150.0000" and category.total_delta == "100.0000"
    assert "accounted for" not in category.text


def test_zero_denominator_and_negative_net_baseline() -> None:
    data = build_currencies([row("-50", month="2026-08"), row("100", "Income")], date(2026, 9, 1))[
        0
    ]
    assert data.comparison.metrics[0].percent is None
    assert data.comparison.metrics[2].percent is None
    assert data.comparison.metrics[2].delta == "150.0000"
    assert "improved" in data.insights[1].text


def test_missing_prior_currency_and_periods_are_not_zero_filled() -> None:
    result = build_currencies(
        [
            row("-10", month="2026-07"),
            row("-20"),
            row("-30", month="2026-08", currency="USD"),
        ],
        date(2026, 9, 1),
    )
    assert len(result) == 2
    assert result[0].totals.outflow == "20.0000"
    assert result[0].comparison.state == "insufficient_history"
    assert [point.month for point in result[0].trend] == ["2026-07", "2026-09"]
    assert result[1].comparison.state == "no_activity"
    assert result[1].totals.outflow == "0.0000"
    assert result[1].insights == []


def test_empty_and_unchanged_history() -> None:
    assert build_currencies([], date(2026, 9, 1)) == []
    result = build_currencies([row("-10", month="2026-08"), row("-10")], date(2026, 9, 1))[0]
    assert result.insights == []
    assert all(item.delta == "0.0000" for item in result.comparison.metrics)


def test_large_aggregates_preserve_four_decimal_places_and_context() -> None:
    with localcontext() as context:
        context.prec = 10
        result = build_currencies(
            [row("9999999999999999.9999", "Income") for _ in range(10)], date(2026, 9, 1)
        )[0]
        assert result.totals.income == "99999999999999999.9990"
        assert context.prec == 10


def test_top_five_merchants_counts_ties_and_unknown() -> None:
    result = build_currencies(
        [row("-10", merchant=name) for name in ["F", "E", "D", "C", "B", "A", None, None]],
        date(2026, 9, 1),
    )[0]
    assert [item.name for item in result.top_merchants] == [None, "A", "B", "C", "D"]
    assert result.top_merchants[0].transaction_count == 2
    assert result.top_merchants[0].share_percent == "25.00"


def test_earliest_month_does_not_compare_with_itself() -> None:
    result = build_currencies([row("-1", month="0001-01")], date(1, 1, 1))[0]
    assert result.comparison.state == "insufficient_history"


def test_chart_scales_are_metric_specific_and_zero_safe() -> None:
    result = build_currencies(
        [
            row("100", "Income", "2026-08"),
            row("200", "Income"),
            row("-20", month="2026-08"),
            row("-10"),
            row("-70", "Transfers"),
        ],
        date(2026, 9, 1),
    )[0]
    previous, current = result.trend
    assert previous.income_scale_percent == "50.00"
    assert current.spending_scale_percent == "50.00"
    assert previous.outflow_scale_percent == "25.00"
    assert current.outflow_scale_percent == "100.00"
    assert result.comparison.categories[0].scale_percent == "100.00"
    empty_income = build_currencies([row("-1")], date(2026, 9, 1))[0]
    assert empty_income.trend[0].income_scale_percent == "0.00"
