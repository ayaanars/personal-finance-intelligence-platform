"""Display labels must never become risk/recurrence identities."""

from datetime import date
from decimal import Decimal

import pytest

from ledgerx.modules.analytics.intelligence import Observation, behaviour
from ledgerx.modules.analytics.recurring import recurring
from ledgerx.modules.transactions.understanding import activity_label


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("RENT PAYMENT REF 123456", "Rent"),
        ("WATER BILL", "Water payment"),
        ("DEWA PAYMENT", "DEWA"),
        ("EMIRATES NBD PAYMENT", "Emirates NBD"),
        ("POS PURCHASE CEDAR MARKET", "Cedar Market"),
        ("UNIDENTIFIED PAYMENT", None),
        ("RENTAL CAR", None),
        ("NETFLIX SPOTIFY", None),
    ],
)
def test_activity_labels(description: str, expected: str | None) -> None:
    assert activity_label(description) == expected
    assert activity_label(description, "Existing identity") == "Existing identity"


def test_rent_composition_does_not_infer_landlord_or_recurring_identity() -> None:
    rows = [
        Observation(
            str(m), date(2026, m, 1), "AED", "Housing", None, Decimal("-1000"), entity_label="Rent"
        )
        for m in (7, 8, 9)
    ]
    result = behaviour(rows, date(2026, 9, 1))
    assert result.top_spending_merchants[0].name == "Rent"
    assert result.largest_purchases[0].merchant == "Rent"
    assert result.newly_observed_merchants == []
    assert recurring(rows, date(2026, 9, 1)).payments == []
    assert all(r.merchant is None for r in rows)


def test_transaction_view_exposes_label_without_changing_identity_or_facts() -> None:
    from uuid import uuid4

    from ledgerx.modules.transactions.models import ImportedTransaction
    from ledgerx.modules.transactions.service import view

    fact = ImportedTransaction(
        id=uuid4(),
        transaction_date=date(2026, 9, 1),
        amount=Decimal("-1000.0000"),
        currency="AED",
        description="RENT PAYMENT",
    )
    result = view(fact, None)
    assert result.display_name == "Rent"
    assert result.merchant is None
    assert result.merchant_code is None
    assert result.raw_description == "RENT PAYMENT"
    assert result.amount == "-1000.0000"
    assert not result.enrichment_persisted
