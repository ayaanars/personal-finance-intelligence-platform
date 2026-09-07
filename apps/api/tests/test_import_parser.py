from unittest.mock import patch

import pytest

from ledgerx.modules.imports.errors import ImportFailure
from ledgerx.modules.imports.parser import CanonicalCSV, select_adapter

HEADER = b"transaction_date,description,amount,currency\n"


@pytest.mark.parametrize(
    "content,code",
    [
        (b"", "CSV_EMPTY"),
        (HEADER, "CSV_EMPTY"),
        (b"date,description,amount,currency\n", "CSV_HEADERS_INVALID"),
        (b"transaction_date,amount,amount,currency\n", "CSV_HEADERS_INVALID"),
        (HEADER + b'2026-09-01,"unterminated,1,AED', "CSV_MALFORMED"),
        (HEADER + b"\xff", "ENCODING_INVALID"),
        (HEADER + b"\x00", "CSV_CONTROL_CHARACTER"),
    ],
)
def test_file_rejections(content: bytes, code: str) -> None:
    with pytest.raises(ImportFailure, match=code):
        list(CanonicalCSV().candidates(content))


def test_header_reordering_bom_quotes_and_record_numbers() -> None:
    rows = list(
        CanonicalCSV().candidates(
            b"\xef\xbb\xbfcurrency,amount,description,transaction_date\r\n"
            b'AED,-1.23,"Synthetic, description\nsecond line",2026-09-01\r\n'
            b'USD,+3.4,"Synthetic ""quote""",2026-09-02\r\n'
        )
    )
    assert [row.source_row_number for row in rows] == [2, 3]
    assert rows[0].values == ("2026-09-01", "Synthetic, description\nsecond line", "-1.23", "AED")
    assert rows[1].values == ("2026-09-02", 'Synthetic "quote"', "+3.4", "USD")


def test_structural_row_errors_have_no_raw_values() -> None:
    rows = list(CanonicalCSV().candidates(HEADER + b"a,b\n" + b"a," + b"x" * 4097 + b",1,AED\n"))
    assert [row.error_code for row in rows] == ["COLUMN_COUNT_INVALID", "FIELD_TOO_LONG"]
    assert all(row.values is None for row in rows)


def test_adapter_is_explicit() -> None:
    assert select_adapter("ledgerx-canonical").version == "1"
    with pytest.raises(ImportFailure, match="PARSER_UNSUPPORTED"):
        select_adapter("invented-bank")


@pytest.mark.parametrize(
    "row", [b'2026-09-01,unquoted"quote,1,AED\n', b'2026-09-01,"closed"trailer,1,AED\n']
)
def test_stray_quotes_are_not_silently_accepted(row: bytes) -> None:
    with pytest.raises(ImportFailure, match="CSV_MALFORMED"):
        list(CanonicalCSV().candidates(HEADER + row))


def test_parser_budget_fails_closed() -> None:
    with patch("ledgerx.modules.imports.parser.monotonic", side_effect=[0, 16]):
        with pytest.raises(ImportFailure, match="PARSE_TIMEOUT"):
            list(CanonicalCSV().candidates(HEADER + b"2026-09-01,Synthetic,1,AED\n"))
