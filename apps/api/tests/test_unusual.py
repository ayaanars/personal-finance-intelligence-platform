"""Synthetic boundary, fallback and currency tests for advisory observations."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

from ledgerx.modules.analytics.intelligence import Observation
from ledgerx.modules.analytics.unusual import evaluate
from ledgerx.modules.analytics.unusual_ml import ml_support

SELECTED = date(2026, 9, 1)


def row(
    month: int,
    day: int,
    value: str = "10",
    merchant: str = "Grocer",
    currency: str = "AED",
    index: int = 0,
) -> Observation:
    return Observation(
        str(UUID(int=month * 10000 + day * 100 + index)),
        date(2026, month, day),
        currency,
        "Groceries",
        merchant,
        -Decimal(value),
    )


def history(count: int = 10) -> list[Observation]:
    return [row(m, i % 28 + 1, str(10 + i % 3), index=i) for m in (6, 7, 8) for i in range(count)]


def codes(rows: list[Observation]) -> set[str]:
    return {e.code for i in evaluate(rows, SELECTED, "AED").items for e in i.evidence}


def test_large_novel_purchase_merges_evidence_and_transparent_severity() -> None:
    report = evaluate(history() + [row(9, 2, "100", "New shop")], SELECTED, "AED")
    item = report.items[0]
    assert {e.code for e in item.evidence} == {"large_purchase", "first_observed_merchant"}
    assert item.severity == "High"
    assert item.evidence[0].reference == "11.0000"
    assert item.evidence[0].ratio == "9.09"
    assert report.ml_state == "insufficient_history"
    assert "large_purchase" not in codes(history() + [row(9, 2, "32")])


def test_category_merchant_and_frequency_spikes() -> None:
    findings = codes(history() + [row(9, i % 28 + 1, index=i) for i in range(35)])
    assert {"category_spike", "merchant_spike", "frequency_spike"} <= findings


def test_normal_and_insufficient_history_do_not_fabricate_anomalies() -> None:
    assert codes(history() + [row(9, i + 1, str(10 + i % 3)) for i in range(10)]) == set()
    report = evaluate([row(8, 2), row(9, 2, "999", "New shop")], SELECTED, "AED")
    assert report.state == "insufficient_history" and not report.items
    assert evaluate(history(), SELECTED, "AED").state == "no_activity"
    assert not codes([r for r in history() if r.day.month != 7] + [row(9, 2, "999")])


def test_recurring_change_uses_prior_qualified_pattern_and_timing() -> None:
    previous = [row(m, 5, "50", "Streaming") for m in (6, 7, 8)]
    assert "recurring_amount_change" in codes(previous + [row(9, 5, "60", "Streaming")])
    assert "recurring_amount_change" in codes(previous + [row(9, 5, "40", "Streaming")])
    assert "recurring_amount_change" not in codes(previous + [row(9, 5, "59", "Streaming")])
    assert "recurring_amount_change" not in codes(previous + [row(9, 25, "60", "Streaming")])
    assert "recurring_amount_change" not in codes(
        previous + [row(9, 5, "60", "Streaming"), row(9, 6, "60", "Streaming")]
    )


def test_currency_and_exclusions_and_selected_month_training_boundary() -> None:
    own = history() + [row(9, 2, "100")]
    foreign = [replace(r, currency="USD", amount=r.amount * 1000) for r in history(40)]
    assert evaluate(own + foreign, SELECTED, "AED") == evaluate(own, SELECTED, "AED")
    assert not codes(history() + [replace(row(9, 2, "999"), category="Transfers")])
    assert not codes(history() + [replace(row(9, 2, "999"), category="Cash / ATM")])
    assert (
        evaluate(history() + [row(9, 2, index=i) for i in range(150)], SELECTED, "AED").ml_state
        == "insufficient_history"
    )


def test_ml_threshold_determinism_and_no_cross_request_fitted_state() -> None:
    current = [row(9, 5, "1000", "New shop")]
    assert ml_support(history(33), current, 3)[0] == "insufficient_history"
    assert ml_support(history(40), current, 2)[0] == "insufficient_history"
    first = ml_support(history(40), current, 3)
    assert first[0] == "active"
    assert first[1] == {current[0].identifier}
    ml_support([replace(r, amount=r.amount * 1000) for r in history(50)], current, 3)
    assert ml_support(history(40), current, 3) == first


def test_model_unavailable_keeps_deterministic_evidence() -> None:
    rows = history(40) + [row(9, 5, "1000", "New shop")]
    working = evaluate(rows, SELECTED, "AED")
    with patch("sklearn.ensemble.IsolationForest.fit", side_effect=RuntimeError("unavailable")):
        fallback = evaluate(rows, SELECTED, "AED")
    assert fallback.ml_state == "unavailable"
    assert {e.code for i in fallback.items for e in i.evidence} == {
        e.code for i in working.items for e in i.evidence
    }
    assert {i.identifier: i.severity for i in fallback.items} == {
        i.identifier: i.severity for i in working.items
    }
    with patch.dict("sys.modules", {"sklearn.ensemble": None}):
        assert evaluate(rows, SELECTED, "AED").ml_state == "unavailable"


def test_merged_recurring_and_large_purchase_keeps_reference_links() -> None:
    rows = history() + [row(m, 5, "50", "Streaming", index=99) for m in (6, 7, 8)]
    current = row(9, 5, "200", "Streaming")
    report = evaluate(rows + [current], SELECTED, "AED")
    item = next(i for i in report.items if i.identifier == current.identifier)
    assert {e.code for e in item.evidence} == {"large_purchase", "recurring_amount_change"}
    assert len(item.transaction_ids) == 4
