from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from ledgerx.modules.analytics.intelligence import Observation, behaviour
from ledgerx.modules.analytics.recurring import recurring
from ledgerx.modules.analytics.unusual import evaluate
from ledgerx.modules.goals.forecast import forecast


def purchases() -> list[Observation]:
    return [
        Observation(
            str(UUID(int=i)),
            date(2026, 9, i),
            "AED",
            "Groceries",
            "Synthetic shop",
            -Decimal("100" if i == 6 else "10"),
        )
        for i in range(1, 7)
    ]


def test_first_month_peer_signal_is_explicit_and_currency_isolated() -> None:
    rows = purchases()
    result = evaluate(rows, date(2026, 9, 1), "AED")
    assert result.state == "insufficient_history" and result.historical_purchases == 0
    assert len(result.items) == 1
    item = result.items[0]
    assert item.basis == "current_month" and item.severity == "Notable" and not item.ml_supported
    assert item.evidence[0].code == "current_month_large_purchase"
    assert item.evidence[0].reference == "10.0000"
    assert item.transaction_ids == [rows[-1].identifier]
    assert (
        evaluate(
            rows + [replace(r, currency="USD", amount=Decimal("-0.01")) for r in rows],
            date(2026, 9, 1),
            "AED",
        )
        == result
    )
    assert not evaluate(rows[1:], date(2026, 9, 1), "AED").items
    assert not evaluate(
        [replace(r, amount=Decimal("-10")) for r in rows], date(2026, 9, 1), "AED"
    ).items
    assert not evaluate(
        [replace(r, category="Transfers") for r in rows], date(2026, 9, 1), "AED"
    ).items


def test_current_metrics_and_recurring_candidates_do_not_invent_history() -> None:
    rows = purchases()
    current = behaviour(rows, date(2026, 9, 1))
    assert current.spending_count == 6 and current.average_purchase == "25.0000"
    assert current.largest_purchases[0].amount == "100.0000"
    assert not current.merchant_changes and not current.newly_observed_merchants
    patterns = recurring(rows, date(2026, 9, 1))
    assert not patterns.payments and patterns.monthly_estimate == "0.0000"
    candidate = patterns.candidates[0]
    assert candidate.observed_months == 1 and candidate.current_amount == "150.0000"
    assert len(candidate.evidence) == 5  # Bounded examples, not fabricated future charges.


def test_first_month_forecast_uses_current_pace_and_no_candidate_commitments() -> None:
    result = forecast(purchases(), date(2026, 9, 1), date(2026, 9, 15), "AED")
    assert result.history_months == 0 and result.state == "estimate"
    assert result.actual_spending == "150.0000" and result.projected_spending == "300.0000"
    assert result.quality == "Early estimate" and "current pace only" in result.explanation
    assert not result.commitments and result.remaining_recurring == "0.0000"
