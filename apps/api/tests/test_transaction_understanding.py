"""Synthetic description rules and regression examples."""

from decimal import Decimal

import pytest

from ledgerx.modules.transactions.understanding import (
    MERCHANTS,
    Category,
    merchant_match,
    normalize_description,
    understand,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("nEtFlIx.CoM", "NETFLIX.COM"),
        ("  cafe\t  24 \n ", "CAFE 24"),
        ("SHOP***ABC|||XYZ---42...", "SHOP*ABC|XYZ-42."),
        ("SHOP REF: 123456", "SHOP"),
        ("SHOP REFERENCE 123456 TXN ID 987654", "SHOP"),
        ("ENOC STATION 123", "ENOC STATION 123"),
        ("SHOP 123456", "SHOP 123456"),
        ("SHOP REF 123", "SHOP REF 123"),
        ("7-ELEVEN STORE 24/7", "7-ELEVEN STORE 24/7"),
        ("SHOP REF: ABC123456", "SHOP REF: ABC123456"),
        ("SHOP 12.50 - 2026/09/01", "SHOP 12.50 - 2026/09/01"),
    ],
)
def test_normalization(raw: str, expected: str) -> None:
    assert normalize_description(raw) == expected
    assert normalize_description(normalize_description(raw)) == expected


@pytest.mark.parametrize("rule", MERCHANTS, ids=lambda rule: rule.code)
def test_merchant_aliases(rule: object) -> None:
    from ledgerx.modules.transactions.understanding import MerchantRule

    assert isinstance(rule, MerchantRule)
    for alias in rule.aliases:
        normalized = normalize_description(alias.lower() + " AE 12345")
        assert merchant_match(normalized) == rule
        assert merchant_match(normalized) == merchant_match(normalized)


@pytest.mark.parametrize(
    "description", ["UNKNOWN SHOP", "DUBAI SHOP", "UBERXYZ", "NETFLIX CARREFOUR"]
)
def test_unknown_or_ambiguous_merchant(description: str) -> None:
    assert merchant_match(description) is None


@pytest.mark.parametrize(
    "description,amount,category",
    [
        ("Salary credit", "100", Category.INCOME),
        ("Freelance payment", "100", Category.INCOME),
        ("Interest credit", "100", Category.INCOME),
        ("Income credit", "100", Category.INCOME),
        ("salary", "-100", Category.OTHER),
        ("Talabat AE 12345", "-10", Category.DINING),
        ("Deliveroo", "-10", Category.DINING),
        ("Carrefour MOE", "-10", Category.GROCERIES),
        ("Lulu", "-10", Category.GROCERIES),
        ("Local supermarket", "-10", Category.GROCERIES),
        ("Local restaurant", "-10", Category.DINING),
        ("Local cafe", "-10", Category.DINING),
        ("ENOC station 123", "-10", Category.TRANSPORT),
        ("ADNOC fuel", "-10", Category.TRANSPORT),
        ("Careem ride", "-10", Category.TRANSPORT),
        ("Uber", "-10", Category.TRANSPORT),
        ("Uber Eats", "-10", Category.DINING),
        ("Public transport", "-10", Category.TRANSPORT),
        ("Parking", "-10", Category.TRANSPORT),
        ("Toll", "-10", Category.TRANSPORT),
        ("Vehicle repair", "-10", Category.TRANSPORT),
        ("Amazon", "-10", Category.SHOPPING),
        ("Electronics", "-10", Category.SHOPPING),
        ("Clothing", "-10", Category.SHOPPING),
        ("Home goods", "-10", Category.SHOPPING),
        ("Netflix.com", "-10", Category.ENTERTAINMENT),
        ("Spotify", "-10", Category.ENTERTAINMENT),
        ("Cinema", "-10", Category.ENTERTAINMENT),
        ("Gaming", "-10", Category.ENTERTAINMENT),
        ("DEWA", "-10", Category.UTILITIES),
        ("Du", "-10", Category.UTILITIES),
        ("Etisalat", "-10", Category.UTILITIES),
        ("Electricity", "-10", Category.UTILITIES),
        ("Software subscription", "-10", Category.UTILITIES),
        ("Insurance premium", "-10", Category.UTILITIES),
        ("Rent", "-10", Category.HOUSING),
        ("Pharmacy", "-10", Category.HEALTH),
        ("Hospital", "-10", Category.HEALTH),
        ("Clinic", "-10", Category.HEALTH),
        ("Gym", "-10", Category.HEALTH),
        ("University", "-10", Category.EDUCATION),
        ("Course", "-10", Category.EDUCATION),
        ("Emirates airline", "-10", Category.TRAVEL),
        ("Etihad airways", "-10", Category.TRAVEL),
        ("Booking.com", "-10", Category.TRAVEL),
        ("Hotel", "-10", Category.TRAVEL),
        ("Account transfer", "100", Category.TRANSFERS),
        ("Account transfer", "-100", Category.TRANSFERS),
        ("Credit card payment", "-100", Category.TRANSFERS),
        ("ATM withdrawal", "-100", Category.CASH),
        ("ATM withdrawal", "100", Category.OTHER),
        ("Bank fee", "-10", Category.FEES),
        ("Government fee", "-10", Category.OTHER),
        ("Donation", "-10", Category.OTHER),
        ("Business expense", "-10", Category.OTHER),
        ("Mystery", "-10", Category.OTHER),
        ("Mystery", "100", Category.OTHER),
        ("Salary reversal", "100", Category.OTHER),
        ("Refund", "100", Category.OTHER),
        ("Reimbursement", "100", Category.OTHER),
        ("Amazon refund", "100", Category.SHOPPING),
        ("Carrefour restaurant", "-10", Category.GROCERIES),
        ("Netflix account transfer", "-10", Category.TRANSFERS),
        ("Restaurant pharmacy", "-10", Category.OTHER),
    ],
)
def test_category_coverage(description: str, amount: str, category: Category) -> None:
    value = understand(description, Decimal(amount))
    assert value.category == category
    assert value.source in {"merchant_rule", "description_rule", "fallback"}
    assert value.reason and value.rule_id
    assert understand(description, Decimal(amount)) == value


def test_order_independence(monkeypatch: pytest.MonkeyPatch) -> None:
    from ledgerx.modules.transactions import understanding as rules

    examples = ["UBER EATS", "RESTAURANT PHARMACY", "CARREFOUR RESTAURANT", "ACCOUNT TRANSFER"]
    before = [understand(example, Decimal("-1")) for example in examples]
    monkeypatch.setattr(rules, "MERCHANTS", tuple(reversed(rules.MERCHANTS)))
    monkeypatch.setattr(rules, "KEYWORDS", tuple(reversed(rules.KEYWORDS)))
    monkeypatch.setattr(rules, "MOVEMENTS", tuple(reversed(rules.MOVEMENTS)))
    assert [understand(example, Decimal("-1")) for example in examples] == before
