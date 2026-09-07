from datetime import date
from decimal import Decimal, localcontext

import pytest

from ledgerx.modules.imports.normalization import normalize
from ledgerx.modules.imports.parser import Candidate


@pytest.mark.parametrize("currency", ["AED", "USD", "EUR", "GBP"])
@pytest.mark.parametrize("amount", ["1", "+12.34", "-0.0001", "9999999999999999.9999"])
def test_exact_money_and_currencies(currency: str, amount: str) -> None:
    with localcontext() as context:
        context.prec = 2  # Construction and validation must not round under ambient precision.
        row = normalize(Candidate(2, ("2024-02-29", " Synthetic description ", amount, currency)))
    assert row.errors == ()
    assert row.amount == Decimal(amount)
    assert row.transaction_date == date(2024, 2, 29)
    assert row.description == " Synthetic description "
    assert row.currency == currency


@pytest.mark.parametrize(
    "amount",
    [
        "0",
        "-0.0000",
        "1.00000",
        "1.23456",
        "10000000000000000",
        "NaN",
        "Infinity",
        "1e2",
        " 1.00",
        "1,000",
        ".5",
        "1.",
        "--1",
        "١٢",
        "",
        "9" * 4096,
    ],
)
def test_invalid_money_is_not_coerced(amount: str) -> None:
    row = normalize(Candidate(2, ("2026-09-01", "Synthetic", amount, "AED")))
    assert row.errors == ("AMOUNT_INVALID",)
    assert row.amount is None and row.description is None


@pytest.mark.parametrize(
    "date_text",
    [
        "2026-02-29",
        "2026-13-01",
        "2026-9-1",
        "01/09/2026",
        "20260901",
        "0000-01-01",
        "2026-09-01T00:00:00Z",
    ],
)
def test_invalid_dates(date_text: str) -> None:
    assert normalize(Candidate(2, (date_text, "Synthetic", "1", "AED"))).errors == ("DATE_INVALID",)


def test_multiple_errors_and_occurrence_fingerprints() -> None:
    row = normalize(Candidate(2, ("bad", " ", "NaN", "aed")))
    assert row.errors == (
        "DATE_INVALID",
        "DESCRIPTION_INVALID",
        "AMOUNT_INVALID",
        "CURRENCY_UNSUPPORTED",
    )
    values = ("2026-09-01", "=SUM(1,2)", "-12", "AED")
    first = normalize(Candidate(2, values))
    assert first.description == "=SUM(1,2)"  # Text only; never evaluated or exported as a formula.
    assert first.fingerprint == normalize(Candidate(2, values)).fingerprint
    assert first.fingerprint != normalize(Candidate(3, values)).fingerprint
