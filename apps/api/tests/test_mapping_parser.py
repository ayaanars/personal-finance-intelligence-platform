from decimal import Decimal

import pytest

from ledgerx.modules.imports.errors import ImportFailure
from ledgerx.modules.imports.mapping import (
    ColumnMapping,
    MappedCSV,
    read_mapping,
    read_table,
    suggest,
    validate_mapping,
)
from ledgerx.modules.imports.normalization import normalize


def mapping(**changes: object) -> ColumnMapping:
    return ColumnMapping.model_validate(
        {
            "transaction_date": "Date",
            "description": "Details",
            "amount": "Amount",
            "currency": "CCY",
            "date_format": "YYYY-MM-DD",
            **changes,
        }
    )


@pytest.mark.parametrize(
    "date_format,value,expected",
    [
        ("YYYY-MM-DD", "2026-04-03", "2026-04-03"),
        ("DD/MM/YYYY", "03/04/2026", "2026-04-03"),
        ("MM/DD/YYYY", "03/04/2026", "2026-03-04"),
        ("DD-MM-YYYY", "03-04-2026", "2026-04-03"),
    ],
)
def test_renamed_reordered_columns_exact_money(date_format: str, value: str, expected: str) -> None:
    content = (
        f"CCY,Amount,Details,Date,Ignored\nAED,-9999999999999999.1234,Synthetic,{value},x\n"
    ).encode()
    row = normalize(next(MappedCSV(mapping(date_format=date_format)).candidates(content)))
    assert not row.errors and row.transaction_date is not None
    assert row.transaction_date.isoformat() == expected
    assert row.amount == Decimal("-9999999999999999.1234")
    assert row.currency == "AED" and row.description == "Synthetic"


@pytest.mark.parametrize(
    "debit,credit,amount,code",
    [
        ("12.1234", "", "-12.1234", None),
        ("", "12.1234", "12.1234", None),
        ("-12", "", None, "DEBIT_CREDIT_INVALID"),
        ("", "+12", None, "DEBIT_CREDIT_INVALID"),
        ("12", "1", None, "DEBIT_CREDIT_BOTH"),
        ("12", "0", None, "DEBIT_CREDIT_BOTH"),
        ("", "", None, "DEBIT_CREDIT_INVALID"),
        ("0", "", None, "AMOUNT_INVALID"),
        ("1.00001", "", None, "DEBIT_CREDIT_INVALID"),
    ],
)
def test_debit_credit(debit: str, credit: str, amount: str | None, code: str | None) -> None:
    content = f"Date,Details,Debit,Credit\n2026-04-03,Synthetic,{debit},{credit}\n".encode()
    config = mapping(
        amount_mode="debit_credit",
        amount=None,
        debit="Debit",
        credit="Credit",
        currency=None,
        fixed_currency="USD",
    )
    row = normalize(next(MappedCSV(config).candidates(content)))
    assert row.errors == ((code,) if code else ())
    assert row.amount == (Decimal(amount) if amount else None)
    if not code:
        assert row.currency == "USD"


@pytest.mark.parametrize(
    "changes",
    [
        {"transaction_date": "Details"},
        {"amount": "Unknown"},
        {"amount": None},
        {"fixed_currency": "AED"},
        {"currency": None},
        {"debit": "Date"},
        {"amount_mode": "debit_credit", "amount": None, "debit": "Amount", "credit": "Amount"},
    ],
)
def test_invalid_mapping(changes: dict[str, object]) -> None:
    with pytest.raises(ImportFailure, match="MAPPING_INVALID"):
        validate_mapping(["Date", "Details", "Amount", "CCY"], mapping(**changes))


def test_date_confirmation_required_and_suggestions_only() -> None:
    table = read_table(b"Date,Details,Amount,CCY\n03/04/2026,Synthetic,1,AED\n")
    suggestions, formats = suggest(table)
    assert suggestions == {
        "transaction_date": "Date",
        "description": "Details",
        "amount": "Amount",
        "currency": "CCY",
    }
    assert formats == ["DD/MM/YYYY", "MM/DD/YYYY"]
    with pytest.raises(ImportFailure, match="MAPPING_INVALID"):
        read_mapping('{"transaction_date":"Date","description":"Details","amount":"Amount"}')
    unambiguous = read_table(b"Date,Details,Amount,CCY\n13/04/2026,Synthetic,1,AED\n")
    assert suggest(unambiguous)[1] == ["DD/MM/YYYY"]
    multiple = read_table(b"Date,Posting Date,Amount,CCY\n2026-01-01,2026-01-02,1,AED\n")
    assert "transaction_date" not in suggest(multiple)[0]


@pytest.mark.parametrize("header", [b"Date,Date", b"Date, date ", b",Details"])
def test_duplicate_and_blank_headers(header: bytes) -> None:
    with pytest.raises(ImportFailure, match="CSV_HEADERS_INVALID"):
        read_table(header + b"\nx,y\n")


@pytest.mark.parametrize(
    "row,code",
    [
        ("2026-02-30,Synthetic,1,AED", "DATE_INVALID"),
        ("2026-02-03,,1,AED", "DESCRIPTION_INVALID"),
        ("2026-02-03,Synthetic,NaN,AED", "AMOUNT_INVALID"),
        ("2026-02-03,Synthetic,1,JPY", "CURRENCY_UNSUPPORTED"),
        ("2026-02-03,Synthetic,1", "COLUMN_COUNT_INVALID"),
        ("2026-02-03," + "x" * 4097 + ",1,AED", "FIELD_TOO_LONG"),
    ],
)
def test_invalid_rows_remain_invalid_without_retaining_values(row: str, code: str) -> None:
    result = normalize(
        next(MappedCSV(mapping()).candidates(("Date,Details,Amount,CCY\n" + row).encode()))
    )
    assert result.errors == (code,)
    assert result.description is None
    assert result.amount is None
    assert result.currency is None
